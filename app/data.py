"""Load the sales CSV into SQLite, cleaning it and recording rejected rows."""
import csv
import sqlite3
from datetime import datetime

SCHEMA = """
DROP TABLE IF EXISTS sales;
DROP TABLE IF EXISTS rejected_rows;
CREATE TABLE sales (
    transaction_id TEXT PRIMARY KEY,
    order_date     TEXT NOT NULL,      -- ISO YYYY-MM-DD
    month          TEXT NOT NULL,      -- YYYY-MM (for grouping)
    product        TEXT NOT NULL,
    category       TEXT NOT NULL,
    region         TEXT NOT NULL,
    sales_channel  TEXT NOT NULL,
    quantity       INTEGER NOT NULL CHECK (quantity > 0),
    unit_price     REAL NOT NULL CHECK (unit_price >= 0),
    discount       REAL NOT NULL DEFAULT 0,
    status         TEXT NOT NULL,
    revenue        REAL NOT NULL       -- quantity * unit_price - discount
);
CREATE TABLE rejected_rows (transaction_id TEXT, reason TEXT);
"""


def clean_row(row):
    """Return (clean_dict, None) or (None, reason)."""
    tid = (row.get("Transaction_Id") or "").strip()
    if not tid:
        return None, "missing transaction id"
    if (row.get("Status") or "").strip().lower() != "completed":
        return None, f"status is {row.get('Status')!r}, not Completed"
    try:
        d = datetime.strptime(row["Order_date"].strip(), "%d-%m-%Y")  # DD-MM-YYYY
    except (ValueError, AttributeError, KeyError):
        return None, "invalid order date"
    price_raw = (row.get("Unit_price") or "").strip()
    if price_raw == "":
        return None, "missing unit price"
    try:
        qty = int(row["Quantity"])
        price = float(price_raw)
        disc = float(row.get("Discount_amount") or 0)
    except (ValueError, TypeError):
        return None, "non-numeric quantity/price/discount"
    if qty <= 0:
        return None, "quantity is zero or negative"
    if price < 0 or disc < 0:
        return None, "negative price or discount"
    return {
        "transaction_id": tid, "order_date": d.strftime("%Y-%m-%d"),
        "month": d.strftime("%Y-%m"), "product": row["Product"].strip(),
        "category": row["Category"].strip(), "region": row["Region"].strip(),
        "sales_channel": row["Sales_channel"].strip(), "quantity": qty,
        "unit_price": price, "discount": disc, "status": "Completed",
        "revenue": qty * price - disc,
    }, None


def build_db(csv_path, db_path):
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    loaded = rejected = 0
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            clean, reason = clean_row(row)
            if reason:
                conn.execute("INSERT INTO rejected_rows VALUES (?, ?)",
                             (row.get("Transaction_Id"), reason))
                rejected += 1
                continue
            try:
                conn.execute(
                    "INSERT INTO sales VALUES (:transaction_id,:order_date,:month,:product,"
                    ":category,:region,:sales_channel,:quantity,:unit_price,:discount,:status,:revenue)",
                    clean)
                loaded += 1
            except sqlite3.IntegrityError:  # duplicate id
                conn.execute("INSERT INTO rejected_rows VALUES (?, ?)",
                             (clean["transaction_id"], "duplicate transaction id"))
                rejected += 1
    conn.commit()
    conn.close()
    return loaded, rejected
