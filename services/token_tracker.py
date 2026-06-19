"""
services/token_tracker.py

Mirrors the exact pattern used in core/logger.py's _log_to_db():
- Synchronous psycopg2 (your codebase has no async DB layer)
- New connection per call, closed immediately after
- Never raises — a failed token log must never break get_response()
"""

import psycopg2
from datetime import datetime

from core.config import DB_URL
from core.logger import app_logger


def log_token_usage(
    model:             str,
    prompt_tokens:     int,
    completion_tokens: int,
    total_tokens:      int,
    mode:              str,                 # "data" | "weak" | "fallback" | "emergency"
    parent_id:         str | None = None,
    baby_id:           str | None = None,
):
    """
    Insert one row per Groq API call into token_usage.
    Called synchronously from chatbot.py right after the Groq response,
    same way log_chat() is called in logger.py.
    """
    try:
        conn = psycopg2.connect(DB_URL)
        cur  = conn.cursor()

        cur.execute("""
            INSERT INTO token_usage (
                parent_id, baby_id, model,
                prompt_tokens, completion_tokens, total_tokens,
                mode, created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            parent_id,
            baby_id,
            model,
            prompt_tokens,
            completion_tokens,
            total_tokens,
            mode,
            datetime.utcnow(),
        ))

        conn.commit()
        cur.close()
        conn.close()

    except Exception as e:
        app_logger.error(f"Token usage log failed: {e}")