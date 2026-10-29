"""SQL safety guard. Every query is checked here before it is executed."""
import re

FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|replace|attach|detach|pragma|vacuum|reindex|truncate)\b",
    re.I)
ALLOWED_TABLES = {"sales"}


class UnsafeQuery(ValueError):
    pass


def validate_sql(sql: str) -> str:
    s = sql.strip().rstrip(";").strip()
    if not s:
        raise UnsafeQuery("empty query")
    if ";" in s:
        raise UnsafeQuery("multiple statements are not allowed")
    if "--" in s or "/*" in s:
        raise UnsafeQuery("comments are not allowed")
    if not re.match(r"^select\b", s, re.I):
        raise UnsafeQuery("only SELECT statements are allowed")
    if FORBIDDEN.search(s):
        raise UnsafeQuery("query contains a forbidden keyword")
    tables = {t.lower() for t in re.findall(r"\b(?:from|join)\s+([a-zA-Z_][\w]*)", s, re.I)}
    if not tables or not tables <= ALLOWED_TABLES:
        raise UnsafeQuery(f"query may only read from: {sorted(ALLOWED_TABLES)}")
    return s
