import csv
import os
import sqlite3
from pathlib import Path

os.environ["SKIP_APP_INIT"] = "1"
import pytest

from app.main import create_app
from app.guard import validate_sql, UnsafeQuery
from app.data import clean_row

CSV = Path(__file__).resolve().parent.parent / "data" / "sales.csv"


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    db = tmp_path_factory.mktemp("db") / "t.db"
    return create_app(CSV, db).test_client()


def expected_rows():
    out = []
    for r in csv.DictReader(open(CSV, encoding="utf-8-sig")):
        c, reason = clean_row(r)
        if not reason:
            out.append(c)
    return out


def ask(client, q):
    return client.post("/ask", json={"question": q})


def test_total_revenue_matches_independent_calculation(client):
    expected = sum(r["quantity"] * r["unit_price"] - r["discount"] for r in expected_rows())
    r = ask(client, "What is the total revenue?")
    assert r.status_code == 200
    assert r.get_json()["rows"][0][0] == pytest.approx(expected)


def test_top_product(client):
    r = ask(client, "Which product generated the highest revenue?").get_json()
    totals = {}
    for x in expected_rows():
        totals[x["product"]] = totals.get(x["product"], 0) + x["revenue"]
    assert r["rows"][0][0] == max(totals, key=totals.get)


def test_monthly_trend_has_six_months_in_order(client):
    r = ask(client, "What is the monthly revenue trend?").get_json()
    assert [row[0] for row in r["rows"]] == [f"2026-0{i}" for i in range(1, 7)]


def test_top_region(client):
    r = ask(client, "Which region generated the highest sales?").get_json()
    assert r["intent"] == "top_region" and r["rows"][0][1] >= r["rows"][-1][1]


def test_month_change_between_two_months(client):
    r = ask(client, "How did revenue change between February and March?").get_json()
    by = {}
    for x in expected_rows():
        by[x["month"]] = by.get(x["month"], 0) + x["revenue"]
    assert r["intent"] == "month_change"
    assert dict(r["rows"]) == {k: pytest.approx(by[k]) for k in ("2026-02", "2026-03")}


def test_invalid_question_is_refused(client):
    r = ask(client, "What is the weather in Hyderabad?")
    assert r.status_code == 400 and "can't answer" in r.get_json()["error"]


def test_destructive_request_is_refused_and_data_intact(client):
    assert ask(client, "DROP TABLE sales;").status_code == 400
    assert client.get("/health").get_json()["valid_rows"] == 48


def test_empty_question_rejected(client):
    assert ask(client, "   ").status_code == 400


def test_edge_month_with_no_data(client):
    r = ask(client, "How did revenue change between December and January?")
    assert r.status_code == 400 and "No sales data" in r.get_json()["error"]


def test_edge_bad_rows_are_excluded_and_logged(client):
    rej = {x["transaction_id"]: x["reason"] for x in client.get("/rejected").get_json()}
    assert set(rej) == {"TXN0033", "TXN0034", "TXN0051"}
    assert "Returned" in rej["TXN0033"] and "quantity" in rej["TXN0034"] and "price" in rej["TXN0051"]


@pytest.mark.parametrize("sql", ["DROP TABLE sales", "DELETE FROM sales", "SELECT 1; DROP TABLE sales",
                                 "UPDATE sales SET revenue=0", "SELECT * FROM sqlite_master",
                                 "SELECT * FROM sales -- x", "PRAGMA table_info(sales)"])
def test_guard_blocks_unsafe_sql(sql):
    with pytest.raises(UnsafeQuery):
        validate_sql(sql)


def test_guard_allows_plain_select():
    assert validate_sql("SELECT SUM(revenue) FROM sales;").startswith("SELECT")


def test_database_connection_is_read_only(client, tmp_path):
    db = tmp_path / "ro.db"
    create_app(CSV, db)
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    with pytest.raises(sqlite3.OperationalError):
        c.execute("DELETE FROM sales")
