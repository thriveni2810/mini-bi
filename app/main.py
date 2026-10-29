import os
import sqlite3
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

from . import analytics, data
from .guard import UnsafeQuery
from .interpreter import interpret

ROOT = Path(__file__).resolve().parent.parent
SUPPORTED = ["What is the total revenue?", "Which product generated the highest revenue?",
             "What is the monthly revenue trend?", "Which region generated the highest sales?",
             "How did revenue change between February and March?"]


def create_app(csv_path=None, db_path=None):
    csv_path = csv_path or ROOT / "data" / "sales.csv"
    db_path = str(db_path or ROOT / "data" / "sales.db")
    loaded, rejected = data.build_db(csv_path, db_path)
    app = Flask(__name__)

    def conn():  # read-only connection: even a guard bug could not modify data
        return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)

    def err(msg, code=400, **extra):
        return jsonify({"error": msg, **extra}), code

    @app.get("/")
    def index():
        return send_from_directory(ROOT / "static", "index.html")

    @app.get("/health")
    def health():
        return jsonify(status="ok", valid_rows=loaded, rejected_rows=rejected)

    @app.get("/rejected")
    def rejected_rows():
        c = conn()
        try:
            return jsonify([{"transaction_id": t, "reason": r}
                            for t, r in c.execute("SELECT transaction_id, reason FROM rejected_rows")])
        finally:
            c.close()

    @app.post("/ask")
    def ask():
        body = request.get_json(silent=True)
        if not isinstance(body, dict) or not isinstance(body.get("question"), str):
            return err('Send JSON like {"question": "..."}.')
        q = body["question"].strip()
        if not q:
            return err("Question must not be empty.")
        if len(q) > 500:
            return err("Question is too long (max 500 characters).")
        spec = interpret(q)
        if spec is None:
            return err("Sorry, I can't answer that. I only answer questions about sales revenue "
                       "from the loaded data.", examples=SUPPORTED)
        c = conn()
        try:
            result = analytics.answer(c, spec)
        except analytics.QuestionError as e:
            return err(str(e))
        except UnsafeQuery as e:
            return err(f"Blocked unsafe query: {e}", 500)
        finally:
            c.close()
        return jsonify({"question": q, "intent": spec["intent"], **result})

    return app


app = create_app() if os.getenv("SKIP_APP_INIT") != "1" else None
