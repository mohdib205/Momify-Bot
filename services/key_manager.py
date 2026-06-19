"""
services/key_manager.py

Tracks which Groq API key is currently active (primary or secondary).
In-memory, single process — fine for your current single-instance deployment.

If you later run multiple uvicorn/gunicorn workers or multiple instances,
this state would need to move to Postgres or Redis so all workers agree
on which key is active. Right now, with a single process, in-memory is correct
and simplest.
"""

import threading
from core.config import GROQ_API_KEY_PRIMARY, GROQ_API_KEY_SECONDARY
from core.logger import app_logger

_lock = threading.Lock()
_state = {
    "active": "primary",
    "primary_dead": False,
    "secondary_dead": False,
}


def get_active_key() -> str:
    with _lock:
        return GROQ_API_KEY_SECONDARY if _state["active"] == "secondary" else GROQ_API_KEY_PRIMARY


def get_active_key_name() -> str:
    """Used to figure out which key just failed when handling an error."""
    with _lock:
        return _state["active"]


def mark_primary_dead():
    with _lock:
        _state["primary_dead"] = True
        if not _state["secondary_dead"]:
            _state["active"] = "secondary"
            app_logger.critical("GROQ KEY ROTATION: primary exhausted (daily limit) -> switched to secondary")


def mark_secondary_dead():
    with _lock:
        _state["secondary_dead"] = True
        app_logger.critical("GROQ KEY ROTATION: secondary also exhausted (daily limit)")


def both_dead() -> bool:
    with _lock:
        return _state["primary_dead"] and _state["secondary_dead"]


def get_status() -> dict:
    """Used by the admin endpoint to report current state."""
    with _lock:
        return dict(_state)


def reset():
    """
    Call manually once you've confirmed daily quotas have actually reset
    (e.g. via the admin endpoint, or simply by restarting the app).
    Does NOT auto-detect recovery — that's intentional, see chatbot.py notes.
    """
    with _lock:
        _state["active"] = "primary"
        _state["primary_dead"] = False
        _state["secondary_dead"] = False
        app_logger.info("GROQ KEY ROTATION: state reset to primary")