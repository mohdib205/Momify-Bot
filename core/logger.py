import logging
import json
import os
from datetime import datetime

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


def log_chat(
    query: str,
    reply: str,
    mode: str,
    score: float,
    response_time_ms: float,
    parent_id: str | None = None,
    baby_id: str | None = None,
    query_subject: str = "baby"
):
    record = {
        "timestamp": datetime.utcnow().isoformat(),
        "query": query,
        "reply": reply,
        "mode": mode,
        "score": score,
        "response_time_ms": round(response_time_ms, 2),
        "parent_id": parent_id,
        "baby_id": baby_id,
        "query_subject": query_subject
    }

    _log_to_file(record)