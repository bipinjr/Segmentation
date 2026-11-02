# CustomerIQ — Customer Segmentation & Intelligence Platform

CustomerIQ transforms customer transaction data into strategic business intelligence using **RFM (Recency, Frequency, Monetary) Analysis and K-Means Clustering**.

It segregates customers into actionable segments (**VIP Champions, Regular Shoppers, and Rare / At-Risk Buyers**) with interactive multi-dimensional dashboards, model tuning, individual customer exploration, and enterprise reporting.

---

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Launch the Web Application (CustomerIQ Platform)
```bash
python run.py
```
Open **[http://127.0.0.1:5000](http://127.0.0.1:5000)** in your browser.

- **Load Built-in Sample:** Click **"Load Sample Data"** in the top navigation bar to instantly analyze the 106k retail transactions.
- **Upload Your Data:** Click **"Upload Dataset"** to drag-and-drop CSV or Excel (`.xlsx`, `.xls`) transaction logs.
- **Dark Mode:** Toggle seamlessly between dark and light themes using the theme button.

---

## 🖥️ Command-Line Execution (CLI)

The original CLI pipeline is preserved and fully functional:

```bash
# Generate sample data (creates data/online_retail_sample.csv)
python generate_sample_data.py

# Run segmentation pipeline, print reports, save graphs, and open windows
python segmentation.py

# Run with custom input or headless (no pop-up windows)
python segmentation.py --input OnlineRetail.xlsx --no-show
```

---

## 🌟 Platform Operating Modes

CustomerIQ provides two distinct modes accessible via the top-bar switch:

### Mode 1: Customer Segmentation
- End-to-end unsupervised machine learning pipeline (RFM feature generation + K-Means clustering).
- Executive KPI cards, customer share vs. revenue share donut charts, and Pareto analysis.
- Multi-dimensional Plotly visualizations (3D RFM cloud, 2D Recency-Spend with centroids, box plots, normalized radar profile).
- Customer Explorer table with search, tier filtering, pagination, and percentile inspector.
- Strategic Segment Playbook and printable Executive Briefing document.

### Mode 2: Clean Data Only (Pure Cleansing & Export)
- Ingests CSV or Excel (`.xlsx`, `.xls`) transaction logs without calculating RFM or K-Means clusters.
- **Automated Anomaly Detection:** Identifies missing Customer IDs, cancellations (`InvoiceNo` starting with 'C'), invalid/unparseable timestamps, invalid quantities, invalid unit prices, and duplicate rows.
- **Configurable Raw Data Preview:** Inspect top 5, 10, 25, or 50 raw rows with schema health diagnostics.
- **Configurable Outlier Filtering:** Adjust maximum quantity (default 300) and maximum price (default $50.00) thresholds.
- **Cleaning Audit Waterfall Report:** Step-by-step accounting of original rows, cleaned rows, dropped rows, reasons for removal, and retention rate.
- **Cleaned Dataset Explorer:** Searchable, sortable, paginated table of verified records with computed `TotalAmount`.
- **Dual Export:** One-click downloads for **Cleaned CSV** (`cleaned_transactions.csv`) and **Cleaned Excel** (`cleaned_transactions.xlsx`).

### 1. Executive Intelligence Dashboard
- **KPI Metrics:** Total Analyzed Customers, Cleaned Revenue, Average Recency, Average Customer Spend, Silhouette Score.
- **Interactive Share Donut Charts:** Side-by-side comparison of **% of Customers vs. % of Revenue** across segments (uncovering Pareto revenue concentration).
- **Segment Matrix:** Tabular summary with average days since purchase, order frequency, spend per head, and gross revenue share.

### 2. Interactive Multi-Dimensional Visualizations
- **3D RFM Vector Space:** Interactive Plotly 3D scatter plot of Recency × $\log_{10}(\text{Frequency})$ × $\log_{10}(\text{Monetary})$ with 360° rotation and customer hover inspector.
- **2D Recency vs. Total Spend:** Log-scale scatter plot featuring calculated cluster **centroids** marked with gold stars.
- **RFM Distribution Boxplots:** Quartile spreads and median comparisons across tiers.
- **Relative Profile Z-Score Chart:** Standardized behavioral profiles highlighting relative strengths and weaknesses.

### 3. Customer Explorer & Detail Inspector
- Real-time search by `CustomerID`.
- Filter by segment tier (VIP, Regular, Rare, or custom clusters).
- Sort by any metric (Spend, Orders, Recency) with multi-page pagination.
- **Deep-Dive Customer Drawer:** Click **"Inspect"** on any customer to see their exact percentile rankings across the entire customer base, RFM statistics, and tailored marketing playbooks.

### 4. Segment Action Playbook
- Predefined strategic playbooks with customer personas, lifecycle stages, and concrete marketing tactics for VIP, Regular, and Rare tiers.

### 5. Model Evaluation & Hyperparameter Tuning
- **The Elbow Method (WCSS / Inertia):** Graphical proof for cluster selection.
- **Silhouette Analysis:** Cohesion and separation scores for $k = 2 \dots 10$.
- **Configurable Controls:** Adjust $k$ (cluster count), outlier limits (max quantity and max price), and cancellation filtering with live re-clustering.

### 6. Data Audit & Health
- Complete waterfall cascade showing records retained and excluded at each cleaning stage (missing Customer IDs, cancellations, quantity limits, price limits, and duplicates).
- Raw data schema validation and preview of the top 10 records.

### 7. Export Center
- **`customer_segments.csv`**: The exact customer segregation file (`CustomerID, Recency, Frequency, Monetary, Cluster, Segment`).
- **`customer_segment_summary.csv`**: Aggregated segment benchmark metrics.
- **Executive Briefing Report**: Formatted HTML briefing ready for PDF export or printing.

---

## 🧪 Automated Testing

CustomerIQ includes a comprehensive test suite covering the machine learning pipeline, data cleaning, RFM math, cluster naming, API endpoints, upload validation, and exports.

```bash
python -m pytest tests/
```

---

## 📁 Project Structure

```
customer_segmentation_project/
├── app.py                      # Flask backend REST API & server routes
├── ml_pipeline.py              # Modularized ML pipeline (RFM, Scaling, K-Means, Scoring)
├── segmentation.py             # CLI runner with Matplotlib & Seaborn plots
├── generate_sample_data.py     # Generates realistic synthetic retail data
├── run.py                      # Web application launcher
├── requirements.txt            # Python dependencies (Flask, scikit-learn, pandas, etc.)
├── static/
│   ├── css/styles.css          # Design system, CSS variables, dark mode styling
│   └── js/app.js               # Frontend controller, Plotly charts, API client
├── templates/
│   └── index.html              # Responsive single-page application template
├── tests/
│   ├── test_pipeline.py        # Unit tests for ML & data processing
│   └── test_api.py             # Integration tests for Flask endpoints
├── data/
│   └── online_retail_sample.csv# Default retail transaction dataset
├── outputs/
│   ├── customer_segments.csv   # Segmented customer output file
│   └── *.png                   # CLI-generated analytical chart figures
├── PROJECT_DETAILS.md          # Comprehensive technical report & viva preparation
└── README.md                   # This documentation guide
```
