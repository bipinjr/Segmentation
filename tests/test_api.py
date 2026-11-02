"""
Integration Tests for CustomerIQ Flask Application & REST Endpoints
"""

import io
import json
import pytest
from pathlib import Path

from app import app, current_session

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_index_page(client):
    """Verify that root page loads CustomerIQ application."""
    res = client.get("/")
    assert res.status_code == 200
    assert b"CustomerIQ" in res.data
    assert b"Executive Intelligence Dashboard" in res.data


def test_api_status(client):
    """Verify system status endpoint."""
    res = client.get("/api/status")
    assert res.status_code == 200
    data = res.get_json()
    assert "status" in data
    assert data["status"] == "online"


def test_api_load_sample(client):
    """Verify loading sample dataset."""
    res = client.post("/api/load-sample")
    assert res.status_code == 200
    data = res.get_json()
    assert "filename" in data
    assert data["filename"] == "online_retail_sample.csv"
    assert data["validation"]["is_valid"] is True


def test_api_run_pipeline(client):
    """Verify end-to-end execution of segmentation via POST /api/run."""
    res = client.post("/api/run", json={
        "k": 3,
        "max_qty": 300,
        "max_price": 50,
        "remove_cancellations": True,
        "random_state": 42
    })
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert "kpis" in data
    assert data["kpis"]["total_customers"] == 4300
    assert data["kpis"]["active_k"] == 3
    assert len(data["segment_summary"]) == 3
    assert "scatter_sample" in data
    assert "centroids" in data
    assert "evaluation" in data


def test_api_run_invalid_k(client):
    """Verify validation when k is outside supported bounds (2..10)."""
    res = client.post("/api/run", json={"k": 25})
    assert res.status_code == 400
    data = res.get_json()
    assert "error" in data


def test_api_results(client):
    """Verify retrieving results."""
    # Run once first
    client.post("/api/run", json={"k": 3})
    res = client.get("/api/results")
    assert res.status_code == 200
    data = res.get_json()
    assert "kpis" in data


def test_api_customers_pagination_and_search(client):
    """Verify customer explorer queries, searching, and pagination."""
    # Make sure data is loaded
    client.post("/api/run", json={"k": 3})

    # Default page 1
    res = client.get("/api/customers?page=1&per_page=10")
    assert res.status_code == 200
    data = res.get_json()
    assert len(data["customers"]) == 10
    assert data["total"] == 4300
    assert data["page"] == 1

    # Filter by segment VIP
    res_vip = client.get("/api/customers?segment=VIP")
    assert res_vip.status_code == 200
    data_vip = res_vip.get_json()
    assert data_vip["total"] == 77
    for c in data_vip["customers"]:
        assert c["Segment"] == "VIP"

    # Search by known CustomerID
    sample_id = data["customers"][0]["CustomerID"]
    res_search = client.get(f"/api/customers?search={sample_id}")
    assert res_search.status_code == 200
    data_search = res_search.get_json()
    assert any(str(c["CustomerID"]) == str(sample_id) for c in data_search["customers"])


def test_api_customer_detail(client):
    """Verify detailed customer profile endpoint."""
    client.post("/api/run", json={"k": 3})
    # Query customer 12347
    res = client.get("/api/customer/12347")
    assert res.status_code == 200
    data = res.get_json()
    assert data["customer_id"] == "12347"
    assert "percentiles" in data
    assert "recency" in data
    assert "monetary" in data
    assert "segment_info" in data


def test_api_customer_detail_not_found(client):
    """Verify 404 for non-existent customer."""
    client.post("/api/run", json={"k": 3})
    res = client.get("/api/customer/99999999")
    assert res.status_code == 404


def test_api_export_csv(client):
    """Verify customer_segments.csv file download."""
    client.post("/api/run", json={"k": 3})
    res = client.get("/api/export/csv")
    assert res.status_code == 200
    assert "text/csv" in res.content_type
    assert b"CustomerID,Recency,Frequency,Monetary,Cluster,Segment" in res.data


def test_api_export_summary(client):
    """Verify customer_segment_summary.csv download."""
    client.post("/api/run", json={"k": 3})
    res = client.get("/api/export/summary")
    assert res.status_code == 200
    assert "text/csv" in res.content_type
    assert b"Segment,Customers" in res.data


def test_api_export_report(client):
    """Verify printable HTML executive briefing report."""
    client.post("/api/run", json={"k": 3})
    res = client.get("/api/export/report")
    assert res.status_code == 200
    assert "text/html" in res.content_type
    assert b"Executive Customer Intelligence Report" in res.data
    assert b"VIP Champions" in res.data


def test_api_upload_file(client):
    """Verify uploading a CSV file and validation."""
    csv_content = (
        b"InvoiceNo,StockCode,Description,Quantity,InvoiceDate,UnitPrice,CustomerID,Country\n"
        b"536365,85123A,WHITE HANGING HEART T-LIGHT HOLDER,6,2010-12-01 08:26:00,2.55,17850,United Kingdom\n"
        b"536366,71053,WHITE METAL LANTERN,6,2010-12-01 08:28:00,3.39,17850,United Kingdom\n"
    )
    data = {
        "file": (io.BytesIO(csv_content), "test_upload.csv")
    }
    res = client.post("/api/upload", data=data, content_type="multipart/form-data")
    assert res.status_code == 200
    resp_data = res.get_json()
    assert resp_data["validation"]["is_valid"] is True
    assert resp_data["validation"]["total_rows"] == 2


def test_api_upload_invalid_extension(client):
    """Verify rejection of non-CSV/Excel files."""
    data = {
        "file": (io.BytesIO(b"fake data"), "malicious.exe")
    }
    res = client.post("/api/upload", data=data, content_type="multipart/form-data")
    assert res.status_code == 400
    assert "Unsupported file extension" in res.get_json()["error"]


# ---------------------------------------------------------------- CLEAN DATA ONLY TESTS
def test_clean_only_preview(client):
    """Verify GET /api/clean-only/preview returns schema, diagnostics, and raw slice."""
    client.post("/api/load-sample")
    res = client.get("/api/clean-only/preview?limit=5")
    assert res.status_code == 200
    data = res.get_json()
    assert "total_rows" in data
    assert "columns" in data
    assert "anomalies" in data
    assert len(data["preview_rows"]) == 5


def test_clean_only_run(client):
    """Verify POST /api/clean-only/run executes transaction cleaning without RFM/ML."""
    client.post("/api/load-sample")
    res = client.post("/api/clean-only/run", json={
        "max_qty": 300,
        "max_price": 50,
        "remove_cancellations": True,
        "remove_duplicates": True
    })
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    report = data["report"]
    assert "original_rows" in report
    assert "cleaned_rows" in report
    assert "removed_rows" in report
    assert "retention_rate" in report
    assert len(report["audit_steps"]) > 0

    # Ensure no RFM or K-Means clustering was executed
    assert "kpis" not in data
    assert "silhouette_score" not in data
    assert "segment_order" not in data


def test_clean_only_run_invalid_outliers(client):
    """Verify server-side validation error when max_qty or max_price is non-positive."""
    res = client.post("/api/clean-only/run", json={"max_qty": -10, "max_price": 50})
    assert res.status_code == 400
    assert "greater than zero" in res.get_json()["error"]


def test_clean_only_rows_search_and_pagination(client):
    """Verify GET /api/clean-only/rows supports pagination, sorting, and search."""
    client.post("/api/load-sample")
    client.post("/api/clean-only/run", json={"max_qty": 300, "max_price": 50})

    # Page 1, 10 records
    res = client.get("/api/clean-only/rows?page=1&per_page=10&sort_by=TotalAmount&sort_dir=desc")
    assert res.status_code == 200
    data = res.get_json()
    assert len(data["rows"]) == 10
    assert data["page"] == 1
    assert data["total"] > 0
    # Sorted descending by TotalAmount
    assert data["rows"][0]["TotalAmount"] >= data["rows"][1]["TotalAmount"]

    # Search for known CustomerID
    sample_cid = data["rows"][0]["CustomerID"]
    res_search = client.get(f"/api/clean-only/rows?search={sample_cid}")
    assert res_search.status_code == 200
    data_search = res_search.get_json()
    assert all(str(sample_cid) in str(r["CustomerID"]) or str(sample_cid) in str(r.get("Description", "")) for r in data_search["rows"])


def test_clean_only_export_csv(client):
    """Verify downloading cleaned_transactions.csv."""
    client.post("/api/clean-only/run", json={"max_qty": 300, "max_price": 50})
    res = client.get("/api/clean-only/export/csv")
    assert res.status_code == 200
    assert "text/csv" in res.content_type
    assert b"InvoiceNo," in res.data
    assert b"TotalAmount" in res.data
    # Confirm no cluster columns
    assert b",Cluster," not in res.data
    assert b",Segment" not in res.data


def test_clean_only_export_excel(client):
    """Verify downloading cleaned_transactions.xlsx."""
    client.post("/api/clean-only/run", json={"max_qty": 300, "max_price": 50})
    res = client.get("/api/clean-only/export/excel")
    assert res.status_code == 200
    assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in res.content_type
    assert len(res.data) > 0


def test_clean_only_missing_columns_error(client):
    """Verify server-side validation error when uploaded file lacks required columns."""
    bad_csv = b"ColA,ColB,ColC\n1,2,3\n"
    data = {
        "file": (io.BytesIO(bad_csv), "incomplete_data.csv")
    }
    upload_res = client.post("/api/upload", data=data, content_type="multipart/form-data")
    assert upload_res.status_code == 200

    # Attempting to clean incomplete dataset should return 400 with understandable error
    clean_res = client.post("/api/clean-only/run", json={})
    assert clean_res.status_code == 400
    assert "missing required column" in clean_res.get_json()["error"]

