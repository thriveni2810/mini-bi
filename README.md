# Mini AI Business Intelligence Assistant

A small web app where a business user types a question about sales in plain English
(e.g. *"Which region generated the highest sales?"*) and gets:

1. a clear **answer**,
2. the **supporting figures** (a table), and
3. the **exact SQL** that produced them.

Built with **Python, Flask and SQLite**. No API key is needed to run it.

---

## 1. Quick start

Requires Python 3.10+.

```bash
pip install -r requirements.txt     # installs flask and pytest
python -m pytest -q                 # run the automated tests (expect: 19 passed)
flask --app app.main run            # start the app
```

Then open **http://127.0.0.1:5000** in a browser.

> Run these commands from the folder that contains `app/`, `tests/` and `README.md`.

### Try these questions
| Question | What it does |
|---|---|
| What is the total revenue? | Total revenue, number of transactions, units, discounts |
| Which product generated the highest revenue? | Revenue per product, ranked |
| What is the monthly revenue trend? | Revenue for each month Jan–Jun 2026 |
| Which region generated the highest sales? | Revenue per region, ranked |
| How did revenue change between February and March? | Both months' revenue, difference, % change |

Also works: "lowest revenue product", "compare Jan vs Feb", and "how did revenue change" (compares the last two months).

### API
| Endpoint | Purpose |
|---|---|
| `POST /ask` with `{"question": "..."}` | Returns `answer`, `intent`, `sql`, `columns`, `rows` (or `{"error": ...}` with HTTP 400) |
| `GET /health` | Number of valid and rejected rows |
| `GET /rejected` | The rows that were excluded and why |

---

## 2. How it works (architecture)

```
 Browser (static/index.html)
        │  POST /ask {"question": "..."}
        ▼
 Flask API (app/main.py)
        │  checks input: not empty, not too long, valid JSON
        ▼
 Interpreter (app/interpreter.py)
        │  question  ->  intent + parameters
        │  unknown / unsafe question  ->  refused with example questions
        ▼
 Analytics (app/analytics.py)
        │  one fixed, parameterised SQL query per intent
        ▼
 SQL Guard (app/guard.py)
        │  only a single SELECT on table `sales` is allowed
        ▼
 SQLite database (read-only connection)
        ▲
        │  built once at startup from data/sales.csv by app/data.py
```

| File | Responsibility |
|---|---|
| `app/data.py` | Reads the CSV, cleans each row, loads SQLite |
| `app/interpreter.py` | Understands the question (keyword rules; optional LLM) |
| `app/analytics.py` | The SQL for each of the 5 question types, and answer text |
| `app/guard.py` | Blocks anything that is not a safe SELECT |
| `app/main.py` | Flask routes, input validation, error handling |
| `static/index.html` | Simple UI: input box, example buttons, answer, table, SQL |
| `tests/test_app.py` | 19 automated tests |

---

## 3. Data management

**Storage.** `data/sales.csv` is loaded into a SQLite table called `sales`
with typed columns and constraints (`quantity > 0`, `unit_price >= 0`, unique `transaction_id`).

**Transformations**
- Dates arrive as `DD-MM-YYYY`; they are stored as ISO `YYYY-MM-DD`, plus a `month` column (`2026-03`) for grouping.
- `revenue = quantity × unit_price − discount_amount` is calculated once and stored.

**Invalid records.** These rows are *not* used in any result. Each is saved in a `rejected_rows` table with its reason (see `/rejected`):

| Transaction | Problem | Why excluded |
|---|---|---|
| TXN0033 | Status is `Returned` | A returned order is not real revenue |
| TXN0034 | Quantity is 0 | Not a real sale |
| TXN0051 | Unit price is missing | Guessing a price would give a wrong revenue figure |

**Result:** 51 rows in the CSV → **48 valid**, 3 rejected. Total revenue = **₹14,39,200**.

**Querying.** Every question runs a SQL query against `sales`, so the numbers are exact and repeatable.

---

## 4. AI integration and preventing wrong answers

**How the AI part works.** The assistant turns free-text into one of five known *intents*
(total revenue, top product, monthly trend, top region, month change). This is the AI-assisted
interpretation step. The SQL for each intent is written and tested by me, so the LLM never
invents numbers or queries.

- **Default mode (offline):** keyword rules, no API key.
- **Optional LLM mode:** `USE_LLM=1` and `ANTHROPIC_API_KEY=...` lets an LLM classify the question into the *same five intents*.
  Its reply is checked against the allowed list and, if anything is wrong, the app falls back to the rules.
  **This mode is untested** because no API key was available while building.

**Why I chose "LLM picks an intent" instead of "LLM writes SQL".** It is safer and more
reliable for a small dataset: nothing the model says can change data or give an unverifiable number.

**How unsupported or incorrect answers are prevented**
1. A question that does not match a known intent is **refused**, with example questions. The app never guesses.
2. Questions containing SQL write words (`DROP`, `DELETE`, `UPDATE`...) or `;` are refused before anything runs.
3. `guard.py` checks every query before it executes: single statement only, must start with `SELECT`, no comments, no forbidden keywords, only the `sales` table.
4. The database connection is opened **read-only**, so even a bug in the guard could not modify data.
5. Months with no data (e.g. "December") give a clear error listing the available months.
6. Every answer shows its SQL and figures, so a user can check it.

---

## 5. Testing

`python -m pytest -q` runs 19 tests in `tests/test_app.py`:

- **Valid questions:** all five question types. Total revenue is compared with a separate Python calculation, not just the SQL.
- **Invalid questions:** off-topic question ("weather"), `DROP TABLE sales;`, empty question.
- **Edge cases:** a month with no data; the 3 bad CSV rows excluded with the right reasons.
- **Safety:** 7 unsafe SQL statements blocked by the guard; a plain SELECT allowed; the database really is read-only.

---

## 6. Known limitations
- Only five question types. No category/channel questions, no top-N, no date ranges.
- Keyword rules can refuse unusual phrasing (the user is shown example questions).
- Two months must be named for a comparison; if no year is given, the data's year (2026) is assumed.
- Bad rows are excluded, not repaired (e.g. no guessing the missing price in TXN0051).
- Currency assumed to be ₹. Single user, no login. The LLM mode is untested.
