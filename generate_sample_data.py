"""
Generate a realistic sample of online-retail transactions.

It has the SAME columns as the public UCI "Online Retail" dataset
(InvoiceNo, StockCode, Description, Quantity, InvoiceDate, UnitPrice,
CustomerID, Country) and is deliberately a little "dirty" (cancellations,
missing CustomerID, duplicates, outliers) so the cleaning step has real work to do.

Usage:  python generate_sample_data.py
Output: data/online_retail_sample.csv
"""
import numpy as np
import pandas as pd
from pathlib import Path

rng = np.random.default_rng(42)

N_CUSTOMERS = 4300
START, END = pd.Timestamp("2010-12-01"), pd.Timestamp("2011-12-09")
DAYS = (END - START).days

PRODUCTS = [
    ("85123A", "WHITE HANGING HEART T-LIGHT HOLDER", 2.95),
    ("71053", "WHITE METAL LANTERN", 3.39),
    ("84406B", "CREAM CUPID HEARTS COAT HANGER", 2.75),
    ("84029G", "KNITTED UNION FLAG HOT WATER BOTTLE", 3.39),
    ("22752", "SET 7 BABUSHKA NESTING BOXES", 7.65),
    ("21730", "GLASS STAR FROSTED T-LIGHT HOLDER", 4.25),
    ("22633", "HAND WARMER UNION JACK", 1.85),
    ("22960", "JAM MAKING SET WITH JARS", 4.25),
    ("22086", "PAPER CHAIN KIT 50'S CHRISTMAS", 2.55),
    ("84879", "ASSORTED COLOUR BIRD ORNAMENT", 1.69),
    ("22423", "REGENCY CAKESTAND 3 TIER", 12.75),
    ("47566", "PARTY BUNTING", 4.95),
    ("23084", "RABBIT NIGHT LIGHT", 2.08),
    ("20725", "LUNCH BAG RED RETROSPOT", 1.65),
    ("21212", "PACK OF 72 RETROSPOT CAKE CASES", 0.55),
]
COUNTRIES = ["United Kingdom"] * 90 + ["Germany", "France", "EIRE", "Spain",
             "Netherlands", "Belgium", "Switzerland", "Portugal", "Australia", "Norway"]

# Hidden customer "personalities" -> the model has to rediscover them
# (share of customers, n_orders (mean), basket size, how recently they buy)
ARCHETYPES = {
    "vip":     dict(p=0.02, orders=(55, 20), items=(7, 4),  recent_days=25),
    "regular": dict(p=0.60, orders=(4.5, 2), items=(5, 3),  recent_days=140),
    "rare":    dict(p=0.38, orders=(1.3, 0.5), items=(3, 2), recent_days=None),  # long ago
}

rows, invoice = [], 536365
for cid in range(12347, 12347 + N_CUSTOMERS):
    kind = rng.choice(list(ARCHETYPES), p=[a["p"] for a in ARCHETYPES.values()])
    a = ARCHETYPES[kind]
    country = rng.choice(COUNTRIES)
    n_orders = max(1, int(rng.normal(*a["orders"])))
    for _ in range(n_orders):
        if kind == "rare":                     # bought once or twice, a long time ago
            day = rng.integers(0, int(DAYS * 0.65))
        else:                                  # active customers buy up to the end
            day = DAYS - int(rng.exponential(a["recent_days"] / 2)) - rng.integers(0, 60)
            day = int(np.clip(day, 0, DAYS))
        ts = START + pd.Timedelta(days=day, hours=int(rng.integers(8, 18)),
                                  minutes=int(rng.integers(0, 60)))
        inv = str(invoice); invoice += 1
        for _ in range(max(1, int(rng.normal(*a["items"])))):
            code, desc, price = PRODUCTS[rng.integers(len(PRODUCTS))]
            qty = int(rng.choice([1, 2, 3, 4, 6, 8, 12, 24], p=[.2, .15, .1, .1, .15, .1, .15, .05]))
            if kind == "vip":
                qty *= int(rng.integers(2, 6))
            rows.append([inv, code, desc, qty, ts, round(price * rng.uniform(.9, 1.1), 2),
                         float(cid), country])

df = pd.DataFrame(rows, columns=["InvoiceNo", "StockCode", "Description", "Quantity",
                                 "InvoiceDate", "UnitPrice", "CustomerID", "Country"])

# ---- make the data "dirty" like the real thing --------------------------------
n = len(df)
canc = df.sample(frac=0.02, random_state=1).copy()          # cancellations / returns
canc["InvoiceNo"] = "C" + canc["InvoiceNo"]; canc["Quantity"] = -canc["Quantity"]
guest = df.sample(frac=0.25, random_state=2).copy()         # guest checkouts, no ID
guest["CustomerID"] = np.nan
dups = df.sample(frac=0.01, random_state=3)                 # exact duplicate rows
bad = df.sample(frac=0.002, random_state=4).copy()          # absurd outliers
bad["Quantity"] = rng.choice([1000, 5000, 80995], len(bad)); bad["UnitPrice"] = 0.0
df = pd.concat([df, canc, guest, dups, bad]).sample(frac=1, random_state=5).reset_index(drop=True)

out = Path(__file__).parent / "data" / "online_retail_sample.csv"
df.to_csv(out, index=False)
print(f"Generated {len(df):,} rows (clean core was {n:,}) -> {out}")
