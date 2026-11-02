Customer Segmentation Demo Data
================================

Files:
1. online_retail_demo.csv - transaction-level CSV compatible with the existing segmentation.py columns.
2. online_retail_demo.xlsx - same demo data in Excel format.
3. online_retail_demo_clean.csv - clean-only version for a first successful run.

Required columns in the existing script:
InvoiceNo, InvoiceDate, CustomerID, Quantity, UnitPrice
Description is an optional descriptive column and is ignored by the RFM calculation.

The raw CSV/XLSX intentionally includes examples for cleaning: a cancellation invoice,
a missing CustomerID, zero quantity, quantity above MAX_QTY=300, UnitPrice above
MAX_PRICE=50, and one duplicate row. These should be filtered by the current clean() function.

Suggested first run:
python segmentation.py --input data/online_retail_demo_clean.csv --no-show

If you copy a file into the project's data folder, adjust the path as needed.
This is synthetic demo data, not real customer information or actual company revenue.
