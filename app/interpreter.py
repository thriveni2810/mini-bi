"""Turn a natural-language question into an intent + parameters.

Default: deterministic keyword rules (works offline).
Optional: if ANTHROPIC_API_KEY is set and USE_LLM=1, an LLM classifies the question into
one of the SAME fixed intents (it never writes SQL). Output is validated against the
whitelist, and any failure falls back to the rules. So unsupported questions are refused
either way.
"""
import json
import os
import re

from .guard import FORBIDDEN

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
MONTH_RE = re.compile(
    r"\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|"
    r"sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b(?:\s*,?\s*(20\d\d))?", re.I)

INTENTS = ["total_revenue", "top_product", "monthly_trend", "top_region", "month_change"]


def find_months(q):
    """Return list of (month_number, year_or_None) in order of appearance."""
    return [(MONTHS[m.group(1)[:3].lower()], int(m.group(2)) if m.group(2) else None)
            for m in MONTH_RE.finditer(q)]


def rule_based(question):
    q = question.lower()
    if FORBIDDEN.search(q) or ";" in q:  # SQL write keywords / multi-statement -> refuse
        return None
    months = find_months(q)
    direction = "ASC" if re.search(r"\b(lowest|least|worst|minimum|smallest)\b", q) else "DESC"
    if len(months) >= 2 or re.search(r"\b(change|changed|compare|comparison|growth|difference|vs|versus)\b", q) \
            and re.search(r"\b(revenue|sales)\b", q) and "trend" not in q:
        return {"intent": "month_change", "months": months[:2]}
    if re.search(r"\b(trend|monthly|month by month|per month|each month|by month)\b", q):
        return {"intent": "monthly_trend"}
    if re.search(r"\bregions?\b", q):
        return {"intent": "top_region", "direction": direction}
    if re.search(r"\b(products?|items?)\b", q):
        return {"intent": "top_product", "direction": direction}
    if re.search(r"\b(total|overall|sum)\b", q) and re.search(r"\b(revenue|sales)\b", q):
        return {"intent": "total_revenue"}
    if re.search(r"\b(revenue|sales)\b", q) and len(q.split()) <= 4:
        return {"intent": "total_revenue"}
    return None


def llm_based(question):  # pragma: no cover - needs network + API key
    try:
        import anthropic
        client = anthropic.Anthropic()
        msg = client.messages.create(
            model=os.getenv("LLM_MODEL", "claude-haiku-5-5"), max_tokens=200,
            system=("Classify the sales question into JSON. Allowed intents: " + ", ".join(INTENTS)
                    + ', or "unsupported". For month_change include "months":[[month_number,year_or_null],[..]]. '
                    'For top_product/top_region include "direction":"DESC" or "ASC". Reply with JSON only.'),
            messages=[{"role": "user", "content": question}])
        data = json.loads(msg.content[0].text)
        if data.get("intent") in INTENTS:
            return data
    except Exception:
        pass
    return None


def interpret(question):
    if os.getenv("USE_LLM") == "1" and os.getenv("ANTHROPIC_API_KEY"):
        result = llm_based(question)
        if result:
            return result
    return rule_based(question)
