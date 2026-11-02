"""
CustomerIQ Machine Learning & RFM Pipeline Module
=================================================
Core data loading, cleaning, RFM feature engineering, scaling,
K-Means clustering, silhouette/elbow evaluation, and segment profiling.

Preserves the exact mathematical pipeline and deterministic behavior
from the original segmentation implementation, with modular interfaces
for web application consumption and CLI execution.
"""

from pathlib import Path
import io
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

# Default pipeline constants
DEFAULT_N_CLUSTERS = 3
DEFAULT_RANDOM_STATE = 42
DEFAULT_MAX_QTY = 300
DEFAULT_MAX_PRICE = 50.0

SEGMENT_COLORS = {
    "VIP": "#10B981",       # Emerald green
    "Regular": "#3B82F6",   # Royal blue
    "Rare": "#F59E0B",      # Amber orange
    "Loyal": "#6366F1",     # Indigo
    "Promising": "#06B6D4", # Cyan
    "At-Risk": "#EC4899",   # Pink
    "Hibernating": "#8B5CF6",
    "Lost": "#EF4444"       # Red
}

# ---------------------------------------------------------------- 1. Load Data
def load_data(source):
    """
    Load raw transaction data from file path, buffer, or existing DataFrame.
    Supports CSV and Excel (.xlsx, .xls) formats.
    """
    if isinstance(source, pd.DataFrame):
        df = source.copy()
    elif isinstance(source, (str, Path)):
        p = Path(source)
        if not p.exists():
            raise FileNotFoundError(f"Input file not found: {p}")
        if p.suffix.lower() in (".xlsx", ".xls"):
            df = pd.read_excel(p)
        else:
            try:
                df = pd.read_csv(p, encoding="utf-8")
            except UnicodeDecodeError:
                df = pd.read_csv(p, encoding="latin1")
    elif hasattr(source, "read"):
        # File-like object (e.g., Flask request.files['file'].stream)
        content = source.read()
        try:
            df = pd.read_csv(io.BytesIO(content), encoding="utf-8")
        except Exception:
            try:
                df = pd.read_csv(io.BytesIO(content), encoding="latin1")
            except Exception:
                df = pd.read_excel(io.BytesIO(content))
    else:
        raise ValueError(f"Unsupported data source type: {type(source)}")

    if "InvoiceDate" in df.columns:
        df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"], errors="coerce")
    return df


# ---------------------------------------------------------------- 2. Validate Raw Data
def validate_raw_data(df):
    """
    Inspect raw DataFrame schema and provide data health diagnostics.
    """
    required_cols = ["InvoiceNo", "Quantity", "InvoiceDate", "UnitPrice", "CustomerID"]
    existing_cols = list(df.columns)
    missing_cols = [c for c in required_cols if c not in existing_cols]

    is_valid = len(missing_cols) == 0

    diagnostics = {
        "is_valid": is_valid,
        "total_rows": int(len(df)),
        "total_columns": int(len(existing_cols)),
        "columns": existing_cols,
        "required_columns": required_cols,
        "missing_columns": missing_cols,
        "null_counts": {c: int(df[c].isna().sum()) for c in existing_cols},
        "sample_preview": df.head(10).fillna("").to_dict(orient="records")
    }

    if is_valid:
        diagnostics["missing_customer_ids"] = int(df["CustomerID"].isna().sum())
        inv_str = df["InvoiceNo"].astype(str)
        diagnostics["cancellations"] = int(inv_str.str.startswith("C").sum())
        diagnostics["zero_or_negative_qty"] = int((pd.to_numeric(df["Quantity"], errors="coerce") <= 0).sum())
        diagnostics["zero_or_negative_price"] = int((pd.to_numeric(df["UnitPrice"], errors="coerce") <= 0).sum())

    return diagnostics


# ---------------------------------------------------------------- 3. Clean Data
def clean_data(df, max_qty=DEFAULT_MAX_QTY, max_price=DEFAULT_MAX_PRICE, remove_cancellations=True):
    """
    Clean raw transactions according to configured thresholds.
    Returns cleaned DataFrame and step-by-step audit trail.
    """
    steps = [{"step": "Raw rows", "count": int(len(df)), "dropped": 0}]

    # 1. Missing CustomerID
    df = df.dropna(subset=["CustomerID"])
    steps.append({"step": "Has CustomerID", "count": int(len(df)), "dropped": steps[-1]["count"] - int(len(df))})

    # 2. Cancellations
    if remove_cancellations:
        df = df[~df["InvoiceNo"].astype(str).str.startswith("C")]
        steps.append({"step": "Not a cancellation", "count": int(len(df)), "dropped": steps[-1]["count"] - int(len(df))})

    # 3. Valid InvoiceDate
    if "InvoiceDate" in df.columns:
        df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"], errors="coerce")
        df = df.dropna(subset=["InvoiceDate"])
        steps.append({"step": "Valid InvoiceDate", "count": int(len(df)), "dropped": steps[-1]["count"] - int(len(df))})

    # 4. Quantity filtering
    df["Quantity"] = pd.to_numeric(df["Quantity"], errors="coerce")
    df = df[(df["Quantity"] > 0) & (df["Quantity"] <= max_qty)]
    steps.append({"step": f"Quantity (1-{max_qty})", "count": int(len(df)), "dropped": steps[-1]["count"] - int(len(df))})

    # 5. Unit price filtering
    df["UnitPrice"] = pd.to_numeric(df["UnitPrice"], errors="coerce")
    df = df[(df["UnitPrice"] > 0) & (df["UnitPrice"] <= max_price)]
    steps.append({"step": f"Price (0-{max_price})", "count": int(len(df)), "dropped": steps[-1]["count"] - int(len(df))})

    # 6. Deduplication
    df = df.drop_duplicates()
    steps.append({"step": "No duplicates", "count": int(len(df)), "dropped": steps[-1]["count"] - int(len(df))})

    df = df.copy()
    df["CustomerID"] = df["CustomerID"].astype(float).astype(int).astype(str)
    df["TotalAmount"] = (df["Quantity"] * df["UnitPrice"]).round(2)

    return df, steps


def clean_dataset_only(
    df,
    max_qty=DEFAULT_MAX_QTY,
    max_price=DEFAULT_MAX_PRICE,
    remove_cancellations=True,
    remove_duplicates=True
):
    """
    Dedicated transaction-level data cleaning for 'Clean Data Only' mode.
    Validates schema, detects anomalies, applies outlier thresholds,
    and returns cleaned DataFrame with comprehensive audit metrics.
    Does NOT calculate RFM or perform K-Means clustering.
    """
    raw_count = int(len(df))
    existing_cols = list(df.columns)
    null_counts = {c: int(df[c].isna().sum()) for c in existing_cols}
    duplicate_count_raw = int(df.duplicated().sum())

    steps = [{
        "step": "Raw Input Records",
        "count": raw_count,
        "dropped": 0,
        "reason": "Initial transaction records received",
        "retention_pct": 100.0
    }]

    curr_df = df.copy()

    # 1. Missing CustomerID
    missing_cust_count = int(curr_df["CustomerID"].isna().sum())
    curr_df = curr_df.dropna(subset=["CustomerID"])
    steps.append({
        "step": "Customer ID Validation",
        "count": int(len(curr_df)),
        "dropped": missing_cust_count,
        "reason": "Removed rows without valid CustomerID (guest/anonymous orders)",
        "retention_pct": round((len(curr_df) / raw_count * 100), 1) if raw_count > 0 else 0.0
    })

    # 2. Cancellations (InvoiceNo starts with 'C')
    prev_count = len(curr_df)
    if remove_cancellations:
        canc_mask = curr_df["InvoiceNo"].astype(str).str.startswith("C")
        curr_df = curr_df[~canc_mask]
        steps.append({
            "step": "Cancellation / Return Filtering",
            "count": int(len(curr_df)),
            "dropped": prev_count - len(curr_df),
            "reason": "Filtered return orders and cancellation invoices (starting with 'C')",
            "retention_pct": round((len(curr_df) / raw_count * 100), 1) if raw_count > 0 else 0.0
        })

    # 3. Valid InvoiceDate
    prev_count = len(curr_df)
    if "InvoiceDate" in curr_df.columns:
        curr_df["InvoiceDate"] = pd.to_datetime(curr_df["InvoiceDate"], errors="coerce")
        curr_df = curr_df.dropna(subset=["InvoiceDate"])
        steps.append({
            "step": "Invoice Date Validation",
            "count": int(len(curr_df)),
            "dropped": prev_count - len(curr_df),
            "reason": "Removed records with invalid, corrupt, or unparseable timestamps",
            "retention_pct": round((len(curr_df) / raw_count * 100), 1) if raw_count > 0 else 0.0
        })

    # 4. Quantity bounds (1 to max_qty)
    prev_count = len(curr_df)
    curr_df["Quantity"] = pd.to_numeric(curr_df["Quantity"], errors="coerce")
    curr_df = curr_df[(curr_df["Quantity"] > 0) & (curr_df["Quantity"] <= max_qty)]
    steps.append({
        "step": f"Quantity Range Filter (1 to {max_qty:,})",
        "count": int(len(curr_df)),
        "dropped": prev_count - len(curr_df),
        "reason": f"Filtered zero/negative quantities and bulk outlier purchases exceeding {max_qty:,} units",
        "retention_pct": round((len(curr_df) / raw_count * 100), 1) if raw_count > 0 else 0.0
    })

    # 5. Price bounds (> 0 to max_price)
    prev_count = len(curr_df)
    curr_df["UnitPrice"] = pd.to_numeric(curr_df["UnitPrice"], errors="coerce")
    curr_df = curr_df[(curr_df["UnitPrice"] > 0) & (curr_df["UnitPrice"] <= max_price)]
    steps.append({
        "step": f"Unit Price Filter ($0.01 to ${max_price:,.2f})",
        "count": int(len(curr_df)),
        "dropped": prev_count - len(curr_df),
        "reason": f"Filtered zero/negative prices and extreme high-value price distortions exceeding ${max_price:,.2f}",
        "retention_pct": round((len(curr_df) / raw_count * 100), 1) if raw_count > 0 else 0.0
    })

    # 6. Deduplication
    prev_count = len(curr_df)
    if remove_duplicates:
        curr_df = curr_df.drop_duplicates()
        steps.append({
            "step": "Exact Duplicate Removal",
            "count": int(len(curr_df)),
            "dropped": prev_count - len(curr_df),
            "reason": "Eliminated identical duplicate transaction rows across all columns",
            "retention_pct": round((len(curr_df) / raw_count * 100), 1) if raw_count > 0 else 0.0
        })

    cleaned_df = curr_df.copy()
    cleaned_df["CustomerID"] = cleaned_df["CustomerID"].astype(float).astype(int).astype(str)
    cleaned_df["TotalAmount"] = (cleaned_df["Quantity"] * cleaned_df["UnitPrice"]).round(2)

    # Format datetime cleanly for tabular viewing & CSV export
    if pd.api.types.is_datetime64_any_dtype(cleaned_df["InvoiceDate"]):
        cleaned_df["InvoiceDate"] = cleaned_df["InvoiceDate"].dt.strftime("%Y-%m-%d %H:%M:%S")

    cleaned_count = int(len(cleaned_df))
    removed_count = raw_count - cleaned_count
    retention_rate = round((cleaned_count / raw_count * 100), 1) if raw_count > 0 else 0.0

    total_cleaned_spend = float(round(cleaned_df["TotalAmount"].sum(), 2))
    unique_customers = int(cleaned_df["CustomerID"].nunique())
    unique_invoices = int(cleaned_df["InvoiceNo"].nunique())

    report = {
        "original_rows": raw_count,
        "cleaned_rows": cleaned_count,
        "removed_rows": removed_count,
        "retention_rate": retention_rate,
        "audit_steps": steps,
        "diagnostics": {
            "null_counts": null_counts,
            "raw_duplicate_rows": duplicate_count_raw,
            "missing_customer_ids": missing_cust_count
        },
        "metrics": {
            "total_cleaned_spend": total_cleaned_spend,
            "unique_customers": unique_customers,
            "unique_invoices": unique_invoices,
            "columns": list(cleaned_df.columns)
        }
    }

    return cleaned_df, report


# ---------------------------------------------------------------- 4. RFM Features
def build_rfm(df):
    """
    Calculate customer-level RFM features:
    - Recency: Days since the snapshot date (max transaction date + 1 day)
    - Frequency: Count of distinct invoices
    - Monetary: Total spending rounded to 2 decimals
    """
    if len(df) == 0:
        raise ValueError("Cannot build RFM from an empty dataset after cleaning.")

    snapshot = df["InvoiceDate"].max().normalize() + pd.Timedelta(days=1)
    rfm = df.groupby("CustomerID").agg(
        Recency=("InvoiceDate", lambda s: int((snapshot - s.max()).days)),
        Frequency=("InvoiceNo", "nunique"),
        Monetary=("TotalAmount", "sum")
    )
    rfm["Monetary"] = rfm["Monetary"].round(2)
    return rfm


# ---------------------------------------------------------------- 5. Scale Features
def scale_rfm(rfm):
    """
    Log1p transformation to handle right skew, followed by standard z-score normalization.
    """
    logged = np.log1p(rfm[["Recency", "Frequency", "Monetary"]])
    scaler = StandardScaler()
    scaled_array = scaler.fit_transform(logged)
    scaled_df = pd.DataFrame(scaled_array, index=rfm.index, columns=logged.columns)
    return scaled_df, scaler


# ---------------------------------------------------------------- 6. Evaluate K
def evaluate_k(X, k_min=2, k_max=10, random_state=DEFAULT_RANDOM_STATE):
    """
    Compute WCSS (inertia) and silhouette score for k in [k_min, k_max].
    """
    n_samples = len(X)
    actual_k_max = min(k_max, max(2, n_samples - 1))
    ks = list(range(k_min, actual_k_max + 1))
    wcss = []
    sil = []

    for k in ks:
        km = KMeans(n_clusters=k, init="k-means++", n_init=10, random_state=random_state)
        km.fit(X)
        wcss.append(float(round(km.inertia_, 2)))
        sample_sz = min(5000, n_samples)
        s_score = float(round(silhouette_score(X, km.labels_, sample_size=sample_sz, random_state=random_state), 3))
        sil.append(s_score)

    return ks, wcss, sil


# ---------------------------------------------------------------- 7. Name Clusters
def name_clusters(rfm, labels, n_clusters=3):
    """
    Rank clusters by standardized value score so labels are invariant to K-Means index.
    score = Frequency_z + Monetary_z - Recency_z (higher is better).
    """
    tmp = rfm.assign(Cluster=labels)
    grouped = tmp.groupby("Cluster")[["Recency", "Frequency", "Monetary"]].mean()

    # Standardize means
    z = grouped.apply(lambda c: (c - c.mean()) / (c.std(ddof=0) if c.std(ddof=0) > 0 else 1.0))
    score = z["Frequency"] + z["Monetary"] - z["Recency"]
    sorted_clusters = score.sort_values(ascending=False).index.tolist()

    if n_clusters == 2:
        names = ["VIP", "Standard"]
    elif n_clusters == 3:
        names = ["VIP", "Regular", "Rare"]
    elif n_clusters == 4:
        names = ["VIP", "Loyal", "Regular", "Rare"]
    elif n_clusters == 5:
        names = ["VIP", "Loyal", "Promising", "Regular", "At-Risk"]
    else:
        names = [f"Tier {i+1} ({'High' if i < n_clusters // 2 else 'Low'} Value)" for i in range(n_clusters)]

    cluster_name_map = {}
    for i, cid in enumerate(sorted_clusters):
        cluster_name_map[cid] = names[i] if i < len(names) else f"Cluster {cid}"

    return cluster_name_map, [cluster_name_map[c] for c in sorted_clusters]


# ---------------------------------------------------------------- 8. Segment Summary
def generate_segment_summary(rfm, order):
    """
    Produce business executive metrics per segment.
    """
    summary = rfm.groupby("Segment").agg(
        Customers=("Recency", "size"),
        Avg_Recency=("Recency", "mean"),
        Avg_Frequency=("Frequency", "mean"),
        Avg_Spend=("Monetary", "mean"),
        Total_Spend=("Monetary", "sum")
    )
    
    # Reindex to maintain segment ranking order
    existing_order = [s for s in order if s in summary.index]
    summary = summary.loc[existing_order]

    total_customers = summary["Customers"].sum()
    total_spend = summary["Total_Spend"].sum()

    summary["% Customers"] = (summary["Customers"] / total_customers * 100).round(1)
    summary["% Revenue"] = (summary["Total_Spend"] / (total_spend if total_spend > 0 else 1) * 100).round(1)
    summary["Avg_Recency"] = summary["Avg_Recency"].round(1)
    summary["Avg_Frequency"] = summary["Avg_Frequency"].round(1)
    summary["Avg_Spend"] = summary["Avg_Spend"].round(2)
    summary["Total_Spend"] = summary["Total_Spend"].round(2)

    return summary


# ---------------------------------------------------------------- 9. Business Action Playbook
def get_segment_playbook():
    """
    Predefined strategic business recommendations for each customer segment.
    """
    return {
        "VIP": {
            "title": "VIP Champions",
            "badge_color": "emerald",
            "persona": "Top spenders who purchase frequently and recently. Highly profitable core.",
            "strategies": [
                "Enroll in exclusive VIP concierge or high-tier loyalty perks.",
                "Offer first access to new product releases and limited-edition items.",
                "Provide direct line to dedicated account managers / priority customer care.",
                "Avoid heavy discounting; emphasize exclusivity, quality, and personalized recognition."
            ]
        },
        "Regular": {
            "title": "Regular / Core Shoppers",
            "badge_color": "blue",
            "persona": "Steady, active customers with reliable order history and moderate transaction sizes.",
            "strategies": [
                "Cross-sell and recommend complementary products based on previous category purchases.",
                "Implement milestone threshold rewards (e.g., 'Spend $50 more for Gold status').",
                "Deploy periodic engagement nudges, bundle promotions, and cart-building incentives.",
                "Nurture loyalty to migrate high-potential shoppers into the VIP tier."
            ]
        },
        "Rare": {
            "title": "Rare / At-Risk Shoppers",
            "badge_color": "amber",
            "persona": "One-time or dormant shoppers with long gaps since their last purchase.",
            "strategies": [
                "Launch automated win-back email sequences with attractive reactivation discounts.",
                "Deliver customer satisfaction surveys to uncover friction or dissatisfaction reasons.",
                "Utilize low-cost marketing channels (email/push) rather than expensive paid ad retargeting.",
                "If non-responsive after 6 months, suppress from high-frequency outreach to safeguard sender reputation."
            ]
        },
        "Loyal": {
            "title": "Loyal Enthusiasts",
            "badge_color": "indigo",
            "persona": "Consistent repeat purchasers with moderate-to-high lifetime value.",
            "strategies": [
                "Offer referral bonuses and brand advocacy rewards.",
                "Introduce subscription or auto-replenishment options where relevant.",
                "Personalized product recommendations based on seasonal preferences."
            ]
        },
        "Promising": {
            "title": "Promising Newcomers",
            "badge_color": "cyan",
            "persona": "Recent buyers with promising basket sizes but low cumulative frequency.",
            "strategies": [
                "Deliver onboarding email journeys with usage tips and social proof.",
                "Provide a second-purchase time-limited coupon within 14 days of initial delivery."
            ]
        },
        "At-Risk": {
            "title": "At-Risk Dormant",
            "badge_color": "pink",
            "persona": "Formerly valuable customers who haven't made a transaction in a long time.",
            "strategies": [
                "Send high-impact 'We miss you' personalized offers.",
                "Highlight new products or significant store upgrades since their last visit."
            ]
        }
    }


# ---------------------------------------------------------------- 10. End-to-End Pipeline Execution
def run_pipeline(
    data_source,
    n_clusters=DEFAULT_N_CLUSTERS,
    max_qty=DEFAULT_MAX_QTY,
    max_price=DEFAULT_MAX_PRICE,
    remove_cancellations=True,
    random_state=DEFAULT_RANDOM_STATE
):
    """
    Executes the complete machine learning and customer segmentation pipeline.
    Returns comprehensive results payload for dashboard visualizations and exports.
    """
    # 1. Load data
    raw_df = load_data(data_source)
    validation = validate_raw_data(raw_df)
    if not validation["is_valid"]:
        raise ValueError(f"Uploaded dataset is missing required columns: {validation['missing_cols']}")

    # 2. Clean data
    cleaned_df, audit_steps = clean_data(
        raw_df,
        max_qty=max_qty,
        max_price=max_price,
        remove_cancellations=remove_cancellations
    )

    # 3. Build RFM features
    rfm = build_rfm(cleaned_df)
    n_customers = len(rfm)

    if n_customers < n_clusters:
        raise ValueError(
            f"Dataset has only {n_customers} unique customer(s) after cleaning, "
            f"which is less than the requested cluster count k={n_clusters}."
        )

    # 4. Scale RFM features
    scaled_df, scaler = scale_rfm(rfm)

    # 5. Evaluate K (2..10)
    ks, wcss, sil_scores = evaluate_k(scaled_df, k_min=2, k_max=10, random_state=random_state)

    # 6. Fit K-Means
    kmeans = KMeans(
        n_clusters=n_clusters,
        init="k-means++",
        n_init=10,
        random_state=random_state
    ).fit(scaled_df)

    cluster_names_map, ordered_segment_names = name_clusters(rfm, kmeans.labels_, n_clusters=n_clusters)
    rfm["Cluster"] = kmeans.labels_
    rfm["Segment"] = rfm["Cluster"].map(cluster_names_map)

    # Current model silhouette score
    sample_sz = min(5000, n_customers)
    current_silhouette = float(round(
        silhouette_score(scaled_df, kmeans.labels_, sample_size=sample_sz, random_state=random_state),
        3
    ))

    # 7. Segment summary
    summary_df = generate_segment_summary(rfm, ordered_segment_names)

    # 8. Sort customer dataset in official order
    rfm_sorted = (
        rfm.reset_index()
        .sort_values(
            ["Segment", "Monetary"],
            key=lambda c: c.map({n: i for i, n in enumerate(ordered_segment_names)}) if c.name == "Segment" else -c
        )
    )

    # 9. Overall KPIs
    total_revenue = float(round(rfm["Monetary"].sum(), 2))
    avg_customer_spend = float(round(rfm["Monetary"].mean(), 2))
    avg_customer_freq = float(round(rfm["Frequency"].mean(), 2))
    avg_customer_recency = float(round(rfm["Recency"].mean(), 1))

    # 10. Extract Centroids in original RFM space
    centroids_rfm = (
        rfm.groupby("Segment")[["Recency", "Frequency", "Monetary"]]
        .mean()
        .loc[[s for s in ordered_segment_names if s in rfm["Segment"].values]]
        .round(2)
        .reset_index()
        .to_dict(orient="records")
    )

    # 11. Profile Heatmap data (standardized z-scores of segment means)
    prof = rfm.groupby("Segment")[["Recency", "Frequency", "Monetary"]].mean()
    existing_order = [s for s in ordered_segment_names if s in prof.index]
    prof = prof.loc[existing_order]
    prof_std = prof.std(ddof=0).replace(0, 1.0)
    prof_z = ((prof - prof.mean()) / prof_std).round(3)

    profile_matrix = []
    for seg in existing_order:
        profile_matrix.append({
            "segment": seg,
            "recency_mean": float(round(prof.loc[seg, "Recency"], 1)),
            "frequency_mean": float(round(prof.loc[seg, "Frequency"], 1)),
            "monetary_mean": float(round(prof.loc[seg, "Monetary"], 2)),
            "recency_z": float(prof_z.loc[seg, "Recency"]),
            "frequency_z": float(prof_z.loc[seg, "Frequency"]),
            "monetary_z": float(prof_z.loc[seg, "Monetary"])
        })

    # 12. Downsampled points for high-performance interactive 2D/3D Plotly rendering
    max_plot_points = 2500
    if len(rfm_sorted) > max_plot_points:
        plot_sample_df = rfm_sorted.sample(n=max_plot_points, random_state=random_state)
    else:
        plot_sample_df = rfm_sorted

    scatter_points = [
        {
            "id": str(row["CustomerID"]),
            "r": int(row["Recency"]),
            "f": int(row["Frequency"]),
            "m": float(row["Monetary"]),
            "log_f": float(round(np.log10(max(1, row["Frequency"])), 3)),
            "log_m": float(round(np.log10(max(0.1, row["Monetary"])), 3)),
            "segment": row["Segment"],
            "cluster": int(row["Cluster"])
        }
        for _, row in plot_sample_df.iterrows()
    ]

    # Convert summary_df to records
    summary_records = summary_df.reset_index().to_dict(orient="records")

    return {
        "success": True,
        "kpis": {
            "total_customers": n_customers,
            "total_revenue": total_revenue,
            "avg_spend": avg_customer_spend,
            "avg_frequency": avg_customer_freq,
            "avg_recency": avg_customer_recency,
            "active_k": n_clusters,
            "silhouette_score": current_silhouette,
            "evaluation_verdict": "Strong Separation" if current_silhouette >= 0.5 else "Moderate Separation"
        },
        "audit_steps": audit_steps,
        "validation": validation,
        "evaluation": {
            "ks": ks,
            "wcss": wcss,
            "silhouette_scores": sil_scores,
            "chosen_k": n_clusters
        },
        "segment_order": ordered_segment_names,
        "segment_summary": summary_records,
        "centroids": centroids_rfm,
        "profile_matrix": profile_matrix,
        "scatter_sample": scatter_points,
        "playbook": get_segment_playbook(),
        "customer_segments_df": rfm_sorted
    }
