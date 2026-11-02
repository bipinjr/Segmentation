"""
Unit & Integration Tests for CustomerIQ ML Pipeline
"""

import pytest
import numpy as np
import pandas as pd
from pathlib import Path

from ml_pipeline import (
    load_data,
    validate_raw_data,
    clean_data,
    clean_dataset_only,
    build_rfm,
    scale_rfm,
    evaluate_k,
    name_clusters,
    run_pipeline,
    DEFAULT_N_CLUSTERS,
    DEFAULT_RANDOM_STATE
)

BASE_DIR = Path(__file__).resolve().parent.parent
SAMPLE_DATA_PATH = BASE_DIR / "data" / "online_retail_sample.csv"


def test_load_sample_data():
    """Verify that the sample dataset exists and loads correctly."""
    assert SAMPLE_DATA_PATH.exists(), "Sample dataset missing at data/online_retail_sample.csv"
    df = load_data(SAMPLE_DATA_PATH)
    assert len(df) > 0
    assert "InvoiceDate" in df.columns
    assert pd.api.types.is_datetime64_any_dtype(df["InvoiceDate"])


def test_validate_raw_data():
    """Test schema diagnostics on valid and invalid dataframes."""
    valid_df = pd.DataFrame({
        "InvoiceNo": ["536365", "C536366"],
        "Quantity": [6, -1],
        "InvoiceDate": ["2010-12-01 08:26:00", "2010-12-01 08:28:00"],
        "UnitPrice": [2.55, 3.00],
        "CustomerID": [12347.0, 12348.0]
    })
    diag = validate_raw_data(valid_df)
    assert diag["is_valid"] is True
    assert diag["total_rows"] == 2
    assert diag["cancellations"] == 1

    invalid_df = pd.DataFrame({"WrongColumn": [1, 2]})
    diag_invalid = validate_raw_data(invalid_df)
    assert diag_invalid["is_valid"] is False
    assert len(diag_invalid["missing_columns"]) > 0


def test_clean_data():
    """Test the cleaning waterfall: cancellations, outliers, null IDs, and deduplication."""
    df_raw = pd.DataFrame({
        "InvoiceNo": ["1001", "C1002", "1003", "1004", "1005", "1001"], # C1002 cancel, 1001 dup
        "Quantity": [10, -5, 500, 5, 2, 10],                             # 500 exceeds max_qty 300
        "InvoiceDate": pd.to_datetime(["2021-01-01"] * 6),
        "UnitPrice": [5.0, 5.0, 5.0, 100.0, 2.0, 5.0],                  # 100 exceeds max_price 50
        "CustomerID": [101.0, 102.0, 103.0, 104.0, np.nan, 101.0]       # NaN ID dropped
    })

    df_cleaned, steps = clean_data(df_raw, max_qty=300, max_price=50, remove_cancellations=True)

    # Only row 1001 with CustomerID 101 should survive
    assert len(df_cleaned) == 1
    assert df_cleaned.iloc[0]["CustomerID"] == "101"
    assert df_cleaned.iloc[0]["TotalAmount"] == 50.0 # 10 * 5.0
    assert len(steps) >= 5


def test_build_rfm_calculation():
    """Test RFM feature calculation accuracy."""
    df = pd.DataFrame({
        "CustomerID": ["101", "101", "102"],
        "InvoiceNo": ["INV1", "INV2", "INV3"],
        "InvoiceDate": pd.to_datetime(["2021-01-01 10:00:00", "2021-01-05 12:00:00", "2021-01-03 09:00:00"]),
        "TotalAmount": [100.0, 150.0, 75.0]
    })
    rfm = build_rfm(df)
    assert len(rfm) == 2
    assert "101" in rfm.index and "102" in rfm.index
    # Customer 101 bought on Jan 1 and Jan 5 -> 2 invoices, total spend = 250
    assert rfm.loc["101", "Frequency"] == 2
    assert rfm.loc["101", "Monetary"] == 250.0
    # Customer 101 bought Jan 5, Customer 102 bought Jan 3 -> 101 is more recent than 102
    assert rfm.loc["101", "Recency"] < rfm.loc["102", "Recency"]


def test_scale_rfm():
    """Verify log1p and standard scaling normalization."""
    rfm = pd.DataFrame({
        "Recency": [1, 10, 50, 100],
        "Frequency": [1, 2, 5, 20],
        "Monetary": [10.0, 50.0, 200.0, 5000.0]
    }, index=["c1", "c2", "c3", "c4"])

    scaled, scaler = scale_rfm(rfm)
    assert scaled.shape == (4, 3)
    # Means should be very close to 0, std ~1
    for col in ["Recency", "Frequency", "Monetary"]:
        assert abs(scaled[col].mean()) < 1e-6
        assert abs(scaled[col].std(ddof=0) - 1.0) < 1e-6


def test_evaluate_k():
    """Test silhouette scores and inertia calculation across range of k."""
    # Synthetic 3 clusters
    rng = np.random.default_rng(42)
    c1 = rng.normal(loc=[-2, 2, 2], scale=0.3, size=(50, 3))
    c2 = rng.normal(loc=[0, 0, 0], scale=0.3, size=(50, 3))
    c3 = rng.normal(loc=[3, -2, -2], scale=0.3, size=(50, 3))
    X = pd.DataFrame(np.vstack([c1, c2, c3]), columns=["Recency", "Frequency", "Monetary"])

    ks, wcss, sil = evaluate_k(X, k_min=2, k_max=4, random_state=42)
    assert ks == [2, 3, 4]
    assert len(wcss) == 3
    assert len(sil) == 3
    # WCSS should decrease monotonically as k increases
    assert wcss[0] > wcss[1] > wcss[2]
    # k=3 should have high silhouette score (> 0.5)
    assert sil[1] > 0.5


def test_name_clusters_ranking():
    """Test that cluster naming assigns 'VIP' to highest value, 'Regular' to mid, 'Rare' to lowest."""
    rfm = pd.DataFrame({
        "Recency": [2, 50, 200],       # Cluster 0: recent, frequent, high spend (VIP)
        "Frequency": [20, 5, 1],
        "Monetary": [2000.0, 300.0, 50.0]
    }, index=["vip_cust", "reg_cust", "rare_cust"])

    labels = [0, 1, 2] # correspond to vip, reg, rare
    mapping, order = name_clusters(rfm, labels, n_clusters=3)
    assert mapping[0] == "VIP"
    assert mapping[1] == "Regular"
    assert mapping[2] == "Rare"
    assert order == ["VIP", "Regular", "Rare"]


def test_pipeline_determinism():
    """Ensure two consecutive pipeline executions with identical seed produce identical outputs."""
    res1 = run_pipeline(SAMPLE_DATA_PATH, n_clusters=3, random_state=42)
    res2 = run_pipeline(SAMPLE_DATA_PATH, n_clusters=3, random_state=42)

    assert res1["kpis"]["total_customers"] == res2["kpis"]["total_customers"]
    assert res1["kpis"]["total_revenue"] == res2["kpis"]["total_revenue"]
    assert res1["kpis"]["silhouette_score"] == res2["kpis"]["silhouette_score"]
    assert res1["segment_summary"] == res2["segment_summary"]


def test_clean_dataset_only():
    """Verify clean_dataset_only filters anomalies and generates audit report without ML."""
    df_dirty = pd.DataFrame({
        "InvoiceNo": ["1001", "C1002", "1003", "1004", "1005", "1006", "1001"], # C1002 cancel, 1001 dup
        "InvoiceDate": ["2021-01-01", "2021-01-02", "bad-date", "2021-01-04", "2021-01-05", "2021-01-06", "2021-01-01"], # bad-date invalid
        "Quantity": [5, -2, 10, 500, 4, 3, 5],                                    # 500 > max_qty (300)
        "UnitPrice": [10.0, 5.0, 2.0, 15.0, 150.0, 8.0, 10.0],                    # 150.0 > max_price (50)
        "CustomerID": [201.0, 202.0, 203.0, 204.0, 205.0, np.nan, 201.0]         # 206 NaN CustomerID
    })

    cleaned_df, report = clean_dataset_only(
        df_dirty,
        max_qty=300,
        max_price=50.0,
        remove_cancellations=True,
        remove_duplicates=True
    )

    # Only row 1001 with CustomerID 201 should remain
    assert len(cleaned_df) == 1
    assert cleaned_df.iloc[0]["CustomerID"] == "201"
    assert cleaned_df.iloc[0]["TotalAmount"] == 50.0 # 5 * 10.0

    # Verify audit report
    assert report["original_rows"] == 7
    assert report["cleaned_rows"] == 1
    assert report["removed_rows"] == 6
    assert len(report["audit_steps"]) >= 6

    # Verify NO RFM or ML clustering fields exist in report or DataFrame
    assert "Cluster" not in cleaned_df.columns
    assert "Segment" not in cleaned_df.columns
    assert "kpis" not in report
    assert "silhouette_score" not in report
