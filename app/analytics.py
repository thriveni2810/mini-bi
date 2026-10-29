"""Fixed, parameterised SQL for each supported intent. Results are deterministic."""
import sqlite3
from .guard import validate_sql, UnsafeQuery

MONTH_NAMES = ["", "January", "February", "March", "April", "May", "June", "July",
               "August", "September", "October", "November", "December"]


class QuestionError(ValueError):
    pass


def run(conn, sql, params=()):
    sql = validate_sql(sql)  # guard runs before EVERY execution
    cur = conn.execute(sql, params)
    cols = [c[0] for c in cur.description]
    return sql, cols, [list(r) for r in cur.fetchall()]


def fmt(x):
    return f"₹{x:,.2f}"


def total_revenue(conn, spec):
    sql, cols, rows = run(conn, "SELECT ROUND(SUM(revenue),2) AS total_revenue, COUNT(*) AS transactions, "
                                "SUM(quantity) AS units, ROUND(SUM(discount),2) AS total_discount FROM sales")
    if rows[0][0] is None:
        raise QuestionError("No valid sales data loaded.")
    return {"answer": f"Total revenue is {fmt(rows[0][0])} across {rows[0][1]} valid transactions "
                      f"(revenue = quantity × unit price − discount).",
            "sql": sql, "columns": cols, "rows": rows}


def ranked(conn, col, label, spec):
    order = "ASC" if spec.get("direction") == "ASC" else "DESC"
    sql, cols, rows = run(conn, f"SELECT {col}, ROUND(SUM(revenue),2) AS revenue, SUM(quantity) AS units, "
                                f"COUNT(*) AS transactions FROM sales GROUP BY {col} ORDER BY revenue {order}, {col}")
    if not rows:
        raise QuestionError("No valid sales data loaded.")
    word = "lowest" if order == "ASC" else "highest"
    return {"answer": f"{rows[0][0]} generated the {word} revenue: {fmt(rows[0][1])}.",
            "sql": sql, "columns": cols, "rows": rows}


def top_product(conn, spec):
    return ranked(conn, "product", "product", spec)


def top_region(conn, spec):
    return ranked(conn, "region", "region", spec)


def monthly_trend(conn, spec):
    sql, cols, rows = run(conn, "SELECT month, ROUND(SUM(revenue),2) AS revenue, COUNT(*) AS transactions "
                                "FROM sales GROUP BY month ORDER BY month")
    if not rows:
        raise QuestionError("No valid sales data loaded.")
    best = max(rows, key=lambda r: r[1])
    return {"answer": f"Monthly revenue from {rows[0][0]} to {rows[-1][0]}; peak month was {best[0]} "
                      f"at {fmt(best[1])}.", "sql": sql, "columns": cols, "rows": rows}


def month_change(conn, spec):
    _, _, avail = run(conn, "SELECT DISTINCT month FROM sales ORDER BY month")
    avail = [r[0] for r in avail]
    if not avail:
        raise QuestionError("No valid sales data loaded.")
    default_year = int(avail[-1][:4])
    picks = spec.get("months") or []
    if not picks:  # "how did revenue change" with no months -> last two months
        if len(avail) < 2:
            raise QuestionError("Need at least two months of data.")
        keys = avail[-2:]
    elif len(picks) < 2:
        raise QuestionError("Please name two months, e.g. 'revenue change between February and March'.")
    else:
        keys = [f"{(y or default_year)}-{int(m):02d}" for m, y in picks]
    if keys[0] == keys[1]:
        raise QuestionError("The two months are the same; please pick two different months.")
    missing = [k for k in keys if k not in avail]
    if missing:
        raise QuestionError(f"No sales data for {', '.join(missing)}. Available months: {', '.join(avail)}.")
    sql, cols, rows = run(conn, "SELECT month, ROUND(SUM(revenue),2) AS revenue FROM sales "
                                "WHERE month IN (?, ?) GROUP BY month ORDER BY month", keys)
    rev = {r[0]: r[1] for r in rows}
    a, b = keys  # a = from, b = to (as asked)
    diff = rev[b] - rev[a]
    pct = diff / rev[a] * 100 if rev[a] else None
    word = "increased" if diff > 0 else "decreased" if diff < 0 else "did not change"
    pct_txt = f" ({pct:+.1f}%)" if pct is not None else ""
    return {"answer": f"Revenue {word} from {fmt(rev[a])} in {a} to {fmt(rev[b])} in {b}: "
                      f"{'+' if diff >= 0 else '−'}{fmt(abs(diff))}{pct_txt}.",
            "sql": sql, "params": keys, "columns": cols, "rows": rows}


HANDLERS = {"total_revenue": total_revenue, "top_product": top_product, "top_region": top_region,
            "monthly_trend": monthly_trend, "month_change": month_change}


def answer(conn, spec):
    return HANDLERS[spec["intent"]](conn, spec)
