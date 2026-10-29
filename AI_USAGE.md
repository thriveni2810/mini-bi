# AI usage

**Tools used:** Claude (Claude Code session, Sonnet 5.5) to generate the code, tests and docs. No LLM runs inside the app by default.

**How AI was used:** I gave Claude the problem statement and the CSV. It proposed the design (cleaning step, fixed SQL per
intent, SQL guard, read-only DB) and wrote the code and tests. I reviewed the data issues it found (returned order, zero
quantity, missing price, DD-MM-YYYY dates) and the design decisions.

**Problems encountered and how they were debugged**
1. *FastAPI could not be installed* (sandbox had no package access) -> switched the API layer to Flask, which was available; logic and tests unchanged.
2. *Test failure:* the question `DROP TABLE sales;` was answered as "total revenue" because a short-question rule matched the word "sales". Found by the destructive-input test; fixed by refusing any question containing SQL write keywords or `;` before interpretation.
3. *Data quality:* identified 3 bad rows by reading the CSV; tests assert exactly which rows are rejected and why.

**Verification:** total revenue is checked in tests by an independent calculation in Python, separate from the SQL.

**With another day:** real LLM-based interpretation tested end to end, more question types (category, channel, top-N, date ranges), a RAG/semantic layer over a data dictionary, logging, Docker, CI.

> Note to self before submitting: update this file to describe your own experience and be ready to explain every module (see README architecture).
