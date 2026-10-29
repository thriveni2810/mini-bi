# Mini AI Business Intelligence Assistant

Ask sales questions in plain English; get an answer plus the SQL and the figures behind it.

## Setup & run
```bash
pip install -r requirements.txt
python -m pytest -q                 # run tests
flask --app app.main run            # open http://127.0.0.1:5000
```
API: `POST /ask` with `{"question": "What is the total revenue?"}`. Also `GET /health`, `GET /rejected`.

## Architecture
```
Browser UI ──POST /ask──> Flask (app/main.py)
                             │ validate input (empty / too long / bad JSON -> 400)
                             ▼
                  interpreter.py  question -> {intent, params}
                  (keyword rules; optional LLM classifier, same whitelist)
                             │ unknown intent -> refused, with examples
                             ▼
                  analytics.py   one fixed, parameterised SQL per intent
                             │
                  guard.py       SELECT-only check on EVERY query
                             ▼
                  SQLite (read-only connection)  <- built from CSV by data.py
```

## Data storage
`data.py` loads the CSV into SQLite table `sales` (typed columns, CHECK constraints). Dates are
converted from DD-MM-YYYY to ISO `YYYY-MM-DD` plus a `month` column. `revenue = quantity × unit_price − discount`.
Rows that cannot be trusted go to `rejected_rows` with a reason (visible at `/rejected`):
- TXN0033: status `Returned` (not a sale)
- TXN0034: quantity 0
- TXN0051: missing unit price (guessing a price would produce wrong revenue)

Result: 48 valid rows, 3 rejected. Total revenue = ₹14,39,200.

## AI integration & preventing wrong answers
- The question is mapped to one of 5 **known intents**; the SQL for each is written by me and fixed, so numbers are deterministic.
- **Default mode is offline rules** (no API key needed). Optional: `USE_LLM=1` + `ANTHROPIC_API_KEY` makes an LLM *classify* the question into the same intents (it never writes SQL). Its output is checked against the whitelist and falls back to the rules on any failure. **This LLM path is untested** (no key was available).
- Anything unrecognised is refused instead of guessed. Questions containing SQL write keywords or `;` are refused.
- `guard.py` allows only a single SELECT on table `sales` (no comments, no DROP/DELETE/UPDATE/PRAGMA etc.), and the DB connection is opened read-only as a second layer.

## Tests (`tests/test_app.py`, 19 cases)
Valid questions for all 5 intents (totals checked against an independent calculation), invalid and destructive
questions, empty input, month with no data, bad-row exclusion, SQL guard, read-only connection.

## Known limitations
- Rule-based interpreter: unusual phrasing may be refused. Only 5 question types (no category/channel questions).
- Two months must be named (or none, then the last two months are compared). Year defaults to the data's year.
- Rejected rows are excluded from revenue, not repaired. Currency assumed ₹. Single-user, no auth.
