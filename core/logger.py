import logging
import json
import os
from datetime import datetime

import psycopg2
from core.config import DB_URL

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

app_logger = logging.getLogger("babydoc.app")
app_logger.setLevel(logging.DEBUG)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(
    logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
)

file_handler = logging.FileHandler(
    os.path.join(LOG_DIR, "app.log"),
    encoding="utf-8"
)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(
    logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
)

if not app_logger.handlers:
    app_logger.addHandler(console_handler)
    app_logger.addHandler(file_handler)

chat_log_path = os.path.join(LOG_DIR, "chat.log")


def _log_to_file(record: dict):
    try:
        with open(chat_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        app_logger.error(f"File log failed: {e}")


def _log_to_db(record: dict):
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO chat_logs (
                query,
                reply,
                mode,
                score,
                response_time_ms,
                parent_id,
                baby_id,
                created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            record["query"],
            record["reply"],
            record["mode"],
            record["score"],
            record["response_time_ms"],
            record["parent_id"],
            record["baby_id"],
            record["timestamp"]
        ))

        conn.commit()
        cur.close()
        conn.close()

    except Exception as e:
        app_logger.error(f"DB log failed: {e}")


def log_chat(
    query: str,
    reply: str,
    mode: str,
    score: float,
    response_time_ms: float,
    parent_id: str | None = None,
    baby_id: str | None = None
):
    record = {
        "timestamp": datetime.utcnow(),
        "query": query,
        "reply": reply,
        "mode": mode,
        "score": score,
        "response_time_ms": round(response_time_ms, 2),
        "parent_id": parent_id,
        "baby_id": baby_id
    }

    _log_to_file({
        **record,
        "timestamp": record["timestamp"].isoformat()
    })

    _log_to_db(record)