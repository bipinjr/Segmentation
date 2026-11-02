"""
CustomerIQ — Customer Segmentation & Intelligence Platform
Flask Web Application Backend
============================================================
Provides REST API endpoints for uploading transaction data, running the
RFM + K-Means pipeline, filtering customer segments, and generating reports.
"""

from pathlib import Path
import os
import tempfile
import io
import json
import numpy as np
import pandas as pd
from flask import Flask, request, jsonify, render_template, send_file, Response
from werkzeug.utils import secure_filename

from ml_pipeline import (
    load_data,
    validate_raw_data,
    clean_data,
    clean_dataset_only,
    run_pipeline,
    DEFAULT_N_CLUSTERS,
    DEFAULT_RANDOM_STATE,
    DEFAULT_MAX_QTY,
    DEFAULT_MAX_PRICE
)

# Base directories
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
# Vercel's filesystem is read-only except /tmp
WRITE_DIR = Path(tempfile.gettempdir()) if os.environ.get("VERCEL") else BASE_DIR
UPLOADS_DIR = WRITE_DIR / "data"
OUTPUTS_DIR = WRITE_DIR / "outputs"
DEFAULT_SAMPLE_PATH = DATA_DIR / "online_retail_sample.csv"
OUTPUT_SEGMENTS_CSV = OUTPUTS_DIR / "customer_segments.csv"
OUTPUT_CLEANED_CSV = OUTPUTS_DIR / "cleaned_transactions.csv"

OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__, static_folder="static", template_folder="templates")
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB max upload
app.config["UPLOAD_EXTENSIONS"] = [".csv", ".xlsx", ".xls"]

# In-memory application session store
current_session = {
    "data_source_path": str(DEFAULT_SAMPLE_PATH) if DEFAULT_SAMPLE_PATH.exists() else None,
    "data_filename": "online_retail_sample.csv" if DEFAULT_SAMPLE_PATH.exists() else None,
    "raw_df": None,
    "last_params": {
        "k": DEFAULT_N_CLUSTERS,
        "max_qty": DEFAULT_MAX_QTY,
        "max_price": DEFAULT_MAX_PRICE,
        "remove_cancellations": True,
        "random_state": DEFAULT_RANDOM_STATE
    },
    "results": None,
    "cleaned_only_df": None,
    "cleaned_only_report": None,
    "last_clean_params": {
        "max_qty": DEFAULT_MAX_QTY,
        "max_price": DEFAULT_MAX_PRICE,
        "remove_cancellations": True,
        "remove_duplicates": True
    }
}


def sanitize_for_json(obj):
    """
    Recursively convert NumPy data types to native Python types for JSON serialization.
    """
    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_for_json(v) for v in obj]
    elif isinstance(obj, (np.integer, np.int64, np.int32)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float64, np.float32)):
        return float(obj)
    elif isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    elif pd.isna(obj):
        return None
    return obj


# ---------------------------------------------------------------- Web Views
@app.route("/")
def index():
    """Serves the single-page CustomerIQ web application."""
    return render_template("index.html")


# ---------------------------------------------------------------- API Endpoints
@app.route("/api/status", methods=["GET"])
def get_status():
    """Check current dataset status and whether results have been computed."""
    has_data = current_session["data_source_path"] is not None or current_session["raw_df"] is not None
    has_results = current_session["results"] is not None

    return jsonify({
        "status": "online",
        "has_data": has_data,
        "filename": current_session["data_filename"],
        "has_results": has_results,
        "last_params": current_session["last_params"]
    })


@app.route("/api/load-sample", methods=["POST"])
def load_sample_dataset():
    """Load the built-in sample dataset directly."""
    try:
        if not DEFAULT_SAMPLE_PATH.exists():
            return jsonify({"error": "Sample dataset not found on server."}), 404

        raw_df = load_data(DEFAULT_SAMPLE_PATH)
        validation = validate_raw_data(raw_df)

        current_session["data_source_path"] = str(DEFAULT_SAMPLE_PATH)
        current_session["data_filename"] = "online_retail_sample.csv"
        current_session["raw_df"] = raw_df
        current_session["results"] = None

        return jsonify({
            "message": "Sample dataset loaded successfully.",
            "filename": "online_retail_sample.csv",
            "validation": sanitize_for_json(validation)
        })
    except Exception as e:
        return jsonify({"error": f"Failed to load sample dataset: {str(e)}"}), 500


@app.route("/api/upload", methods=["POST"])
def upload_file():
    """Upload CSV or Excel file, validate structure, and generate preview."""
    try:
        if "file" not in request.files:
            return jsonify({"error": "No file part in request."}), 400

        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "No selected file."}), 400

        filename = secure_filename(file.filename)
        ext = os.path.splitext(filename)[1].lower()

        if ext not in app.config["UPLOAD_EXTENSIONS"]:
            return jsonify({
                "error": f"Unsupported file extension '{ext}'. Please upload a CSV (.csv) or Excel (.xlsx, .xls) file."
            }), 400

        save_path = UPLOADS_DIR / f"uploaded_{filename}"
        file.save(save_path)

        # Parse and validate
        raw_df = load_data(save_path)
        validation = validate_raw_data(raw_df)

        current_session["data_source_path"] = str(save_path)
        current_session["data_filename"] = filename
        current_session["raw_df"] = raw_df
        current_session["results"] = None

        return jsonify({
            "message": "File uploaded and validated successfully.",
            "filename": filename,
            "validation": sanitize_for_json(validation)
        })
    except Exception as e:
        return jsonify({"error": f"File upload failed: {str(e)}"}), 500


@app.route("/api/run", methods=["POST"])
def run_segmentation():
    """Execute the ML pipeline with custom or default parameters."""
    try:
        if current_session["raw_df"] is None and current_session["data_source_path"] is None:
            if DEFAULT_SAMPLE_PATH.exists():
                current_session["raw_df"] = load_data(DEFAULT_SAMPLE_PATH)
                current_session["data_source_path"] = str(DEFAULT_SAMPLE_PATH)
                current_session["data_filename"] = "online_retail_sample.csv"
            else:
                return jsonify({"error": "No dataset loaded. Please upload or load a dataset first."}), 400

        payload = request.get_json(silent=True) or {}
        k = int(payload.get("k", DEFAULT_N_CLUSTERS))
        max_qty = int(payload.get("max_qty", DEFAULT_MAX_QTY))
        max_price = float(payload.get("max_price", DEFAULT_MAX_PRICE))
        remove_cancellations = bool(payload.get("remove_cancellations", True))
        random_state = int(payload.get("random_state", DEFAULT_RANDOM_STATE))

        if k < 2 or k > 10:
            return jsonify({"error": "Cluster count 'k' must be between 2 and 10."}), 400
        if max_qty <= 0 or max_price <= 0:
            return jsonify({"error": "Outlier limits for quantity and price must be greater than zero."}), 400

        data_source = current_session["raw_df"] if current_session["raw_df"] is not None else current_session["data_source_path"]

        # Run pipeline
        results = run_pipeline(
            data_source=data_source,
            n_clusters=k,
            max_qty=max_qty,
            max_price=max_price,
            remove_cancellations=remove_cancellations,
            random_state=random_state
        )

        # Save outputs/customer_segments.csv
        segments_df = results.pop("customer_segments_df")
        segments_df.to_csv(OUTPUT_SEGMENTS_CSV, index=False)

        # Cache results in memory
        current_session["results"] = results
        current_session["customer_segments_df"] = segments_df
        current_session["last_params"] = {
            "k": k,
            "max_qty": max_qty,
            "max_price": max_price,
            "remove_cancellations": remove_cancellations,
            "random_state": random_state
        }

        # Return sanitized results
        sanitized = sanitize_for_json(results)
        return jsonify(sanitized)
    except Exception as e:
        return jsonify({"error": f"Pipeline execution failed: {str(e)}"}), 500


@app.route("/api/results", methods=["GET"])
def get_results():
    """Retrieve currently computed pipeline results."""
    if current_session["results"] is None:
        return jsonify({"error": "No analysis results available. Run segmentation first."}), 404
    return jsonify(sanitize_for_json(current_session["results"]))


@app.route("/api/customers", methods=["GET"])
def get_customers():
    """
    Search, filter, sort, and paginate through customer segment records.
    """
    df = current_session.get("customer_segments_df")
    if df is None:
        if OUTPUT_SEGMENTS_CSV.exists():
            df = pd.read_csv(OUTPUT_SEGMENTS_CSV)
            current_session["customer_segments_df"] = df
        else:
            return jsonify({"error": "No segmented customers available. Run the analysis first."}), 404

    try:
        page = max(1, int(request.args.get("page", 1)))
        per_page = min(100, max(5, int(request.args.get("per_page", 20))))
        search = request.args.get("search", "").strip()
        segment = request.args.get("segment", "all").strip()
        sort_by = request.args.get("sort_by", "Monetary").strip()
        sort_order = request.args.get("sort_order", "desc").lower().strip()

        filtered = df.copy()

        # Filter by segment
        if segment != "all" and segment != "":
            filtered = filtered[filtered["Segment"].str.lower() == segment.lower()]

        # Search by CustomerID
        if search:
            filtered = filtered[filtered["CustomerID"].astype(str).str.contains(search, case=False, na=False)]

        total_records = len(filtered)

        # Sort
        if sort_by in filtered.columns:
            ascending = (sort_order == "asc")
            filtered = filtered.sort_values(by=sort_by, ascending=ascending)

        # Paginate
        total_pages = max(1, int(np.ceil(total_records / per_page)))
        if page > total_pages:
            page = total_pages

        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        page_records = filtered.iloc[start_idx:end_idx].to_dict(orient="records")

        return jsonify({
            "total": total_records,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
            "customers": sanitize_for_json(page_records)
        })
    except Exception as e:
        return jsonify({"error": f"Failed to retrieve customers: {str(e)}"}), 500


@app.route("/api/customer/<customer_id>", methods=["GET"])
def get_customer_detail(customer_id):
    """Retrieve in-depth profile, percentile rankings, and recommendations for a single customer."""
    df = current_session.get("customer_segments_df")
    if df is None:
        if OUTPUT_SEGMENTS_CSV.exists():
            df = pd.read_csv(OUTPUT_SEGMENTS_CSV)
            current_session["customer_segments_df"] = df
        else:
            return jsonify({"error": "No segmented customers available."}), 404

    match = df[df["CustomerID"].astype(str) == str(customer_id)]
    if match.empty:
        return jsonify({"error": f"Customer ID '{customer_id}' not found."}), 404

    row = match.iloc[0]

    # Calculate percentile rankings
    recency_pct = float(round((df["Recency"] < row["Recency"]).mean() * 100, 1)) # lower recency is better
    freq_pct = float(round((df["Frequency"] < row["Frequency"]).mean() * 100, 1))
    spend_pct = float(round((df["Monetary"] < row["Monetary"]).mean() * 100, 1))

    playbook = current_session.get("results", {}).get("playbook", {})
    segment_info = playbook.get(row["Segment"], {
        "title": f"Segment {row['Segment']}",
        "badge_color": "blue",
        "persona": "Standard customer profile.",
        "strategies": ["Tailor communications according to engagement history."]
    })

    return jsonify({
        "customer_id": str(row["CustomerID"]),
        "recency": int(row["Recency"]),
        "frequency": int(row["Frequency"]),
        "monetary": float(row["Monetary"]),
        "cluster": int(row["Cluster"]),
        "segment": str(row["Segment"]),
        "percentiles": {
            "recency_percentile": 100 - recency_pct, # Higher score = better / more recent
            "frequency_percentile": freq_pct,
            "monetary_percentile": spend_pct
        },
        "segment_info": segment_info
    })


@app.route("/api/export/csv", methods=["GET"])
def export_csv():
    """Download full customer segmentation result as CSV file."""
    if not OUTPUT_SEGMENTS_CSV.exists():
        return jsonify({"error": "No output file found. Run segmentation first."}), 404
    return send_file(
        OUTPUT_SEGMENTS_CSV,
        mimetype="text/csv",
        as_attachment=True,
        download_name="customer_segments.csv"
    )


@app.route("/api/export/summary", methods=["GET"])
def export_summary_csv():
    """Download segment summary as CSV file."""
    if current_session["results"] is None:
        return jsonify({"error": "No analysis results available."}), 404

    summary_records = current_session["results"]["segment_summary"]
    summary_df = pd.DataFrame(summary_records)

    buf = io.StringIO()
    summary_df.to_csv(buf, index=False)
    buf.seek(0)

    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=customer_segment_summary.csv"}
    )


@app.route("/api/export/report", methods=["GET"])
def export_executive_report():
    """Generate a high-fidelity executive HTML briefing report suitable for printing or PDF export."""
    if current_session["results"] is None:
        return jsonify({"error": "No analysis results available."}), 404

    results = current_session["results"]
    kpis = results["kpis"]
    summary = results["segment_summary"]
    playbook = results["playbook"]

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>CustomerIQ — Executive Customer Intelligence Report</title>
<style>
    @page {{ size: A4; margin: 20mm; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif; color: #1e293b; line-height: 1.5; margin: 0; padding: 24px; }}
    .header {{ border-bottom: 2px solid #2563eb; padding-bottom: 12px; margin-bottom: 24px; display: flex; justify-content: space-between; align-items: flex-end; }}
    .brand {{ font-size: 24px; font-weight: 800; color: #0f172a; }}
    .brand span {{ color: #2563eb; }}
    .subtitle {{ font-size: 13px; color: #64748b; }}
    .kpi-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }}
    .kpi-card {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; text-align: center; }}
    .kpi-title {{ font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; color: #64748b; font-weight: 600; margin-bottom: 6px; }}
    .kpi-val {{ font-size: 22px; font-weight: 700; color: #0f172a; }}
    table {{ width: 100%; border-collapse: collapse; margin-bottom: 30px; font-size: 13px; }}
    th, td {{ padding: 10px 14px; text-align: left; border-bottom: 1px solid #e2e8f0; }}
    th {{ background: #f1f5f9; color: #334155; font-weight: 600; }}
    .badge {{ display: inline-block; padding: 3px 8px; border-radius: 9999px; font-size: 11px; font-weight: 600; }}
    .badge-VIP {{ background: #d1fae5; color: #065f46; }}
    .badge-Regular {{ background: #dbeafe; color: #1e40af; }}
    .badge-Rare {{ background: #fef3c7; color: #92400e; }}
    .playbook-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-top: 20px; }}
    .playbook-card {{ border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; background: #fff; }}
    .playbook-card h4 {{ margin: 0 0 8px 0; font-size: 15px; color: #0f172a; }}
    .playbook-card p {{ font-size: 12px; color: #475569; margin-bottom: 10px; }}
    .playbook-card ul {{ margin: 0; padding-left: 18px; font-size: 12px; color: #334155; }}
    .playbook-card li {{ margin-bottom: 6px; }}
    .footer {{ margin-top: 40px; border-top: 1px solid #e2e8f0; padding-top: 12px; font-size: 11px; color: #94a3b8; text-align: center; }}
    @media print {{ body {{ padding: 0; }} button {{ display: none; }} }}
</style>
</head>
<body>
    <div style="text-align: right; margin-bottom: 10px;">
        <button onclick="window.print()" style="padding: 8px 16px; background: #2563eb; color: #fff; border: none; border-radius: 6px; cursor: pointer; font-weight: 600;">Print / Save PDF</button>
    </div>
    <div class="header">
        <div>
            <div class="brand">Customer<span>IQ</span></div>
            <div class="subtitle">Executive Customer Segmentation & RFM Intelligence Briefing</div>
        </div>
        <div style="text-align: right; font-size: 12px; color: #64748b;">
            Dataset: <strong>{current_session.get('data_filename', 'online_retail_sample.csv')}</strong><br>
            Active Clusters: <strong>k={kpis['active_k']}</strong> | Silhouette: <strong>{kpis['silhouette_score']}</strong>
        </div>
    </div>

    <div class="kpi-grid">
        <div class="kpi-card">
            <div class="kpi-title">Total Customers</div>
            <div class="kpi-val">{kpis['total_customers']:,}</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-title">Cleaned Revenue</div>
            <div class="kpi-val">${kpis['total_revenue']:,.2f}</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-title">Avg Spend / Customer</div>
            <div class="kpi-val">${kpis['avg_spend']:,.2f}</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-title">Avg Order Frequency</div>
            <div class="kpi-val">{kpis['avg_frequency']} orders</div>
        </div>
    </div>

    <h3>Customer Segment Performance Summary</h3>
    <table>
        <thead>
            <tr>
                <th>Segment</th>
                <th>Customers</th>
                <th>% Customers</th>
                <th>Avg Recency</th>
                <th>Avg Frequency</th>
                <th>Avg Spend</th>
                <th>Total Revenue</th>
                <th>% Revenue</th>
            </tr>
        </thead>
        <tbody>
"""

    for s in summary:
        seg = s["Segment"]
        html += f"""
            <tr>
                <td><span class="badge badge-{seg}">{seg}</span></td>
                <td>{s['Customers']:,}</td>
                <td><strong>{s['% Customers']}%</strong></td>
                <td>{s['Avg_Recency']} days</td>
                <td>{s['Avg_Frequency']} orders</td>
                <td>${s['Avg_Spend']:,.2f}</td>
                <td>${s['Total_Spend']:,.2f}</td>
                <td><strong>{s['% Revenue']}%</strong></td>
            </tr>
        """

    html += """
        </tbody>
    </table>

    <h3>Strategic Segment Playbook & Recommended Actions</h3>
    <div class="playbook-grid">
"""

    for s in summary:
        seg = s["Segment"]
        info = playbook.get(seg, {
            "title": f"Segment {seg}",
            "persona": "Customer segment group.",
            "strategies": ["Maintain active engagement."]
        })
        strategies_html = "".join([f"<li>{strat}</li>" for strat in info["strategies"]])
        html += f"""
        <div class="playbook-card">
            <h4>{info['title']}</h4>
            <p>{info['persona']}</p>
            <ul>{strategies_html}</ul>
        </div>
        """

    html += """
    </div>

    <div class="footer">
        Generated by CustomerIQ Platform — RFM + K-Means Clustering Machine Learning Engine. Confidential & Proprietary.
    </div>
</body>
</html>
"""
    return Response(html, mimetype="text/html")


# ================================================================
# CLEAN DATA ONLY MODE ENDPOINTS
# ================================================================

@app.route("/api/clean-only/preview", methods=["GET"])
def get_clean_only_preview():
    """
    Return configurable preview and column health statistics of the original raw data.
    """
    try:
        raw_df = current_session["raw_df"]
        if raw_df is None:
            if current_session["data_source_path"] and Path(current_session["data_source_path"]).exists():
                raw_df = load_data(current_session["data_source_path"])
                current_session["raw_df"] = raw_df
            elif DEFAULT_SAMPLE_PATH.exists():
                raw_df = load_data(DEFAULT_SAMPLE_PATH)
                current_session["raw_df"] = raw_df
                current_session["data_filename"] = "online_retail_sample.csv"
            else:
                return jsonify({"error": "No raw dataset loaded. Please upload a dataset first."}), 400

        limit = min(100, max(5, int(request.args.get("limit", 10))))
        existing_cols = list(raw_df.columns)
        null_counts = {c: int(raw_df[c].isna().sum()) for c in existing_cols}

        preview_slice = raw_df.head(limit).copy()
        # Convert datetime objects to string for JSON serialization
        for col in preview_slice.columns:
            if pd.api.types.is_datetime64_any_dtype(preview_slice[col]):
                preview_slice[col] = preview_slice[col].dt.strftime("%Y-%m-%d %H:%M:%S")

        preview_records = preview_slice.fillna("").to_dict(orient="records")

        # Basic anomaly detection in raw data
        total_rows = int(len(raw_df))
        cancellations = int(raw_df["InvoiceNo"].astype(str).str.startswith("C").sum()) if "InvoiceNo" in raw_df.columns else 0
        missing_customers = int(raw_df["CustomerID"].isna().sum()) if "CustomerID" in raw_df.columns else 0
        duplicates = int(raw_df.duplicated().sum())
        invalid_quantities = int((pd.to_numeric(raw_df["Quantity"], errors="coerce") <= 0).sum()) if "Quantity" in raw_df.columns else 0
        invalid_prices = int((pd.to_numeric(raw_df["UnitPrice"], errors="coerce") <= 0).sum()) if "UnitPrice" in raw_df.columns else 0

        return jsonify({
            "filename": current_session.get("data_filename", "dataset"),
            "total_rows": total_rows,
            "columns": existing_cols,
            "null_counts": null_counts,
            "limit": limit,
            "preview_rows": sanitize_for_json(preview_records),
            "anomalies": {
                "cancellations": cancellations,
                "missing_customers": missing_customers,
                "duplicates": duplicates,
                "invalid_quantities": invalid_quantities,
                "invalid_prices": invalid_prices
            }
        })
    except Exception as e:
        return jsonify({"error": f"Failed to generate raw data preview: {str(e)}"}), 500


@app.route("/api/clean-only/run", methods=["POST"])
def run_clean_only():
    """
    Execute transaction-level data cleaning strictly without RFM or K-Means clustering.
    Saves cleaned dataset for preview and export.
    """
    try:
        raw_df = current_session["raw_df"]
        if raw_df is None:
            if current_session["data_source_path"] and Path(current_session["data_source_path"]).exists():
                raw_df = load_data(current_session["data_source_path"])
                current_session["raw_df"] = raw_df
            elif DEFAULT_SAMPLE_PATH.exists():
                raw_df = load_data(DEFAULT_SAMPLE_PATH)
                current_session["raw_df"] = raw_df
                current_session["data_filename"] = "online_retail_sample.csv"
            else:
                return jsonify({"error": "No dataset loaded. Please upload a dataset first."}), 400

        # Server-side validation of required columns
        validation = validate_raw_data(raw_df)
        if not validation["is_valid"]:
            missing_str = ", ".join(validation["missing_columns"])
            return jsonify({
                "error": f"Dataset is missing required column(s): {missing_str}. Please ensure your file contains: InvoiceNo, Quantity, InvoiceDate, UnitPrice, CustomerID."
            }), 400

        payload = request.get_json(silent=True) or {}
        max_qty = int(payload.get("max_qty", DEFAULT_MAX_QTY))
        max_price = float(payload.get("max_price", DEFAULT_MAX_PRICE))
        remove_cancellations = bool(payload.get("remove_cancellations", True))
        remove_duplicates = bool(payload.get("remove_duplicates", True))

        if max_qty <= 0 or max_price <= 0:
            return jsonify({"error": "Outlier limits for quantity and price must be greater than zero."}), 400

        # Run pure data cleaning
        cleaned_df, report = clean_dataset_only(
            raw_df,
            max_qty=max_qty,
            max_price=max_price,
            remove_cancellations=remove_cancellations,
            remove_duplicates=remove_duplicates
        )

        # Cache in session
        current_session["cleaned_only_df"] = cleaned_df
        current_session["cleaned_only_report"] = report
        current_session["last_clean_params"] = {
            "max_qty": max_qty,
            "max_price": max_price,
            "remove_cancellations": remove_cancellations,
            "remove_duplicates": remove_duplicates
        }

        # Persist cleaned dataset to outputs/cleaned_transactions.csv
        cleaned_df.to_csv(OUTPUT_CLEANED_CSV, index=False)

        # Prepare top sample records for immediate view
        sample_rows = cleaned_df.head(10).fillna("").to_dict(orient="records")

        return jsonify({
            "success": True,
            "report": sanitize_for_json(report),
            "sample_rows": sanitize_for_json(sample_rows)
        })
    except Exception as e:
        return jsonify({"error": f"Data cleaning failed: {str(e)}"}), 500


@app.route("/api/clean-only/rows", methods=["GET"])
def get_clean_only_rows():
    """
    Search, filter, sort, and paginate through actual cleaned transaction records.
    """
    try:
        df = current_session.get("cleaned_only_df")
        if df is None:
            if OUTPUT_CLEANED_CSV.exists():
                df = pd.read_csv(OUTPUT_CLEANED_CSV)
                current_session["cleaned_only_df"] = df
            else:
                return jsonify({"error": "No cleaned transactions available. Run 'Clean Dataset' first."}), 404

        page = max(1, int(request.args.get("page", 1)))
        per_page = min(100, max(5, int(request.args.get("per_page", 15))))
        search = request.args.get("search", "").strip()
        sort_by = request.args.get("sort_by", "InvoiceDate").strip()
        sort_dir = request.args.get("sort_dir", "desc").lower().strip()

        filtered = df.copy()

        # Multi-column search across InvoiceNo, CustomerID, Description, StockCode, Country
        if search:
            mask = pd.Series(False, index=filtered.index)
            search_cols = [c for c in ["InvoiceNo", "CustomerID", "Description", "StockCode", "Country"] if c in filtered.columns]
            for col in search_cols:
                mask = mask | filtered[col].astype(str).str.contains(search, case=False, na=False)
            filtered = filtered[mask]

        total_records = len(filtered)

        # Sorting
        if sort_by in filtered.columns:
            ascending = (sort_dir == "asc")
            filtered = filtered.sort_values(by=sort_by, ascending=ascending)

        # Pagination
        total_pages = max(1, int(np.ceil(total_records / per_page)))
        if page > total_pages:
            page = total_pages

        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        page_records = filtered.iloc[start_idx:end_idx].fillna("").to_dict(orient="records")

        return jsonify({
            "total": total_records,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
            "columns": list(filtered.columns),
            "rows": sanitize_for_json(page_records)
        })
    except Exception as e:
        return jsonify({"error": f"Failed to fetch cleaned rows: {str(e)}"}), 500


@app.route("/api/clean-only/export/csv", methods=["GET"])
def export_clean_only_csv():
    """
    Download actual cleaned transaction dataset as CSV.
    """
    df = current_session.get("cleaned_only_df")
    if df is None:
        if OUTPUT_CLEANED_CSV.exists():
            return send_file(
                OUTPUT_CLEANED_CSV,
                mimetype="text/csv",
                as_attachment=True,
                download_name="cleaned_transactions.csv"
            )
        return jsonify({"error": "No cleaned transactions found. Clean a dataset first."}), 404

    buf = io.StringIO()
    df.to_csv(buf, index=False)
    buf.seek(0)

    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=cleaned_transactions.csv"}
    )


@app.route("/api/clean-only/export/excel", methods=["GET"])
def export_clean_only_excel():
    """
    Download actual cleaned transaction dataset as Excel (.xlsx).
    """
    try:
        df = current_session.get("cleaned_only_df")
        if df is None:
            if OUTPUT_CLEANED_CSV.exists():
                df = pd.read_csv(OUTPUT_CLEANED_CSV)
                current_session["cleaned_only_df"] = df
            else:
                return jsonify({"error": "No cleaned transactions found. Clean a dataset first."}), 404

        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Cleaned Transactions")
        buf.seek(0)

        return send_file(
            buf,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name="cleaned_transactions.xlsx"
        )
    except Exception as e:
        return jsonify({"error": f"Excel export failed: {str(e)}"}), 500


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
