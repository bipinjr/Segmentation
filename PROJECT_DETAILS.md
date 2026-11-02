# Customer Segmentation using RFM Analysis and K-Means Clustering
*Project details - for presenting to the guide*

## 1. Problem statement
An online retailer has thousands of customers but treats them all the same. Marketing budget is
wasted on customers who will never return, and the most valuable customers get no special attention.
**Goal:** automatically divide customers into meaningful groups using only their purchase history,
so each group can get a different marketing strategy.

## 2. Objectives
1. Clean raw transaction data into a reliable customer-level dataset.
2. Describe every customer with three behavioural measures (RFM).
3. Use unsupervised machine learning (K-Means) to segregate customers into **three groups**.
4. Present the groups with graphs, and export one CSV listing each customer and their group.

## 3. Dataset
Transactional data of an online retailer (structure of the UCI *Online Retail* dataset: ~542k rows,
Dec 2010 - Dec 2011). Columns: `InvoiceNo, StockCode, Description, Quantity, InvoiceDate, UnitPrice, CustomerID, Country`.
The project runs on a generated sample with identical columns (and deliberate dirty data), and accepts the real
file via `--input`. *Note for the guide: figures below are from the sample data, not the real dataset.*

## 4. Methodology (step by step)
| Step | What is done | Why |
|---|---|---|
| 1. Load | Read CSV/XLSX, parse dates | - |
| 2. Clean | Remove rows without CustomerID, cancellations (invoice starts with "C"), Quantity outside 1-300, UnitPrice outside 0-50, duplicates | Can't segment unknown customers; returns and extreme outliers distort the result |
| 3. RFM features | Per customer: **Recency** = days since last purchase, **Frequency** = number of distinct invoices, **Monetary** = total spend | RFM is the standard marketing way to measure customer value |
| 4. Scale | `log1p` then `StandardScaler` | Spend and frequency are heavily right-skewed; K-Means uses distance, so features must be on the same scale and not dominated by a few huge buyers |
| 5. Choose k | Elbow (WCSS) and silhouette score for k = 2..10 | Evidence for the number of groups; k = 3 gave the highest silhouette (0.58) |
| 6. K-Means | k = 3, `k-means++` start, `n_init=10`, fixed random seed | Groups customers so that members of a group are close to each other in RFM space |
| 7. Name groups | Each cluster gets a value score = Frequency + Monetary - Recency (standardised); highest = **VIP**, middle = **Regular**, lowest = **Rare** | Names are assigned by the data, so they stay correct even if K-Means numbers its clusters differently |
| 8. Output | Segment summary, 6 graphs, `customer_segments.csv` | Deliverables |

## 5. Results (sample data)
| Segment | Customers | Avg recency | Avg orders | Avg spend | % customers | % revenue |
|---|---|---|---|---|---|---|
| VIP | 77 | 4 days | 56 | 29,055 | 1.8% | 64.7% |
| Regular | 2,247 | 40 days | 4.4 | 478 | 52.3% | 31.1% |
| Rare | 1,976 | 222 days | 1.1 | 74 | 46.0% | 4.2% |

**Insight:** under 2% of customers produce about two thirds of revenue (Pareto-style concentration).
Silhouette score 0.58 shows the groups are well separated.

## 6. Business actions per segment
- **VIP** - protect and reward: loyalty programme, early access, personal service.
- **Regular** - grow: cross-sell, bundles, nudges to increase order frequency and basket size.
- **Rare** - win back: re-engagement emails and discounts; low-cost channels only.

## 7. How this relates to the reference project
Same core idea (RFM -> standardise -> K-Means, k = 3, VIP/Regular/Rare, CSV export), rebuilt so that it runs from one command. Improvements:
- Single script instead of two notebooks with repeated code; no hard-coded local Windows paths.
- Cancellations (invoice "C...") are explicitly removed.
- `log1p` applied **before** clustering (the reference only used it in a side analysis).
- k chosen with elbow **and** silhouette, not elbow alone.
- Centroids computed from the model/data, not typed in by hand.
- Segment names assigned automatically by a value score, not a manual cluster-number map.
- More graphs (share of revenue, profile heatmap, 3D) and one clean output CSV.

## 8. Web Platform Architecture (CustomerIQ Upgrade)
The project now includes an enterprise-grade web application platform (**CustomerIQ**) built on Flask, Vanilla JS, and Plotly.js:
- **Interactive Single-Page Application (SPA):** Eliminates static Matplotlib windows in favor of interactive 3D/2D Plotly visualizations.
- **Dynamic Dataset Ingestion & Validation:** Live CSV/Excel upload with automated data health diagnostics and schema validation.
- **Interactive Hyperparameter Tuning:** Adjust cluster count $k$, outlier quantity and price thresholds with instant re-clustering.
- **Individual Customer Explorer:** Live search, segment filtering, multi-page pagination, and individual customer percentile radar.
- **Actionable Strategic Playbooks:** Marketing recommendations tailored to each behavioral segment.
- **Enterprise Reporting & Export:** Instant download of `customer_segments.csv`, summary benchmarks, and printable Executive Briefing reports.
- **Automated Test Suite:** 22 unit and integration tests covering the complete pipeline and REST API.

## 9. Limitations and future work
- Static snapshot of transactions; K-Means assumes roughly globular clusters in standardized log-RFM space.
- Features are currently behavioral RFM; could incorporate product category diversity, channel origin, and geographical demographics.
- Future enhancements: Dynamic customer churn prediction (e.g. XGBoost/Random Forest classification), Customer Lifetime Value (CLV) regression, and automated cohort transition tracking over time.

## 10. Likely questions from the guide
- **Why unsupervised?** There are no labels telling us who is VIP; the groups must be discovered.
- **Why RFM?** Simple, interpretable, widely used in marketing; three numbers capture engagement and value.
- **Why scale/log-transform?** K-Means is distance-based; spend (thousands) would swamp recency (days) and skew creates a few extreme points.
- **Why k = 3?** Silhouette is highest at 3, the elbow bends there, and three tiers are easy for a business to act on.
- **How do you know the clusters are good?** Silhouette score, clearly separated boxplots/scatter, and sensible business interpretation.
- **Why remove Quantity > 300 / price > 50?** Treated as bulk/outlier or data-entry errors; thresholds are configurable at the top of the script.
