from fastapi import FastAPI, HTTPException, Header, Request
from contextlib import asynccontextmanager
from typing import Optional

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

import os
from datetime import datetime

from core.config import QA_FILE
from core.logger import app_logger

from models.schemas import (
    ChatRequest,
    ChatResponse,
    FeedbackRequest,
    FeedbackResponse
)

from services.retriever import load_qa
from services.chatbot import get_response
from services.baby_context import get_baby_context_from_token, extract_user_id, fetch_all_babies

qa_data = []

limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global qa_data
    app_logger.info("Momify API starting up...")
    qa_data = load_qa(QA_FILE)
    app_logger.info(f"Loaded {len(qa_data)} Q&A pairs from {QA_FILE}")
    yield
    app_logger.info("Momify API shutting down.")


app = FastAPI(title="Momify API", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


from fastapi.middleware.cors import CORSMiddleware

ALLOWED_ORIGINS = [
    "https://himomify.com",
    "https://www.himomify.com",
    "https://api.himomify.com",
    "https://bot.himomify.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.post("/chat", response_model=ChatResponse)
@limiter.limit("20/minute")
def chat(
    request: Request,
    req: ChatRequest,
    authorization: Optional[str] = Header(default=None)
):
    try:
        baby_context = ""
        parent_id    = None
        baby_id_str  = None

        if authorization and authorization.startswith("Bearer "):
            token = authorization.removeprefix("Bearer ").strip()
            parent_id = extract_user_id(token)

            if req.query_subject != "mother":
                baby_context, parent_id, baby_id_str = get_baby_context_from_token(
                    token,
                    baby_id=req.baby_id
                )

        reply, mode, score, response_time_ms = get_response(
            message       = req.message,
            qa_data       = qa_data,
            history       = req.history,
            baby_context  = baby_context,
            parent_id     = parent_id,
            baby_id       = baby_id_str,
            query_subject = req.query_subject
        )
        return ChatResponse(
            reply=reply,
            mode=mode,
            score=score,
            response_time_ms=response_time_ms,
            query_subject=req.query_subject
        )

    except Exception as e:
        app_logger.error(f"Unhandled error in /chat: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/submit_feedback", response_model=FeedbackResponse)
def submit_feedback(req: FeedbackRequest):
    import psycopg2
    from core.config import DB_URL

    if not DB_URL:
        raise HTTPException(status_code=500, detail="DB_URL not configured")

    try:
        conn = psycopg2.connect(DB_URL)
        cur  = conn.cursor()
        cur.execute("""
            INSERT INTO doctor_feedback
            (query, bot_response, mode, score, verdict, failure_reason, doctor_notes, reviewed_by, reviewed_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            req.query, req.bot_response, req.mode, req.score,
            req.verdict, req.failure_reason, req.doctor_notes,
            req.reviewed_by, datetime.now()
        ))
        conn.commit()
        cur.close()
        conn.close()
        return FeedbackResponse(success=True, message="Feedback submitted successfully")

    except Exception as e:
        app_logger.error(f"Error in /submit_feedback: {e}")
        raise HTTPException(status_code=500, detail="Could not save feedback")


@app.get("/health")
def health():
    return {"status": "ok", "qa_pairs_loaded": len(qa_data)}


@app.get("/test_baby_context")
def test_baby_context(authorization: Optional[str] = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        return {"error": "No token provided"}
    token             = authorization.removeprefix("Bearer ").strip()
    user_id           = extract_user_id(token)
    babies            = fetch_all_babies(token)
    context, pid, bid = get_baby_context_from_token(token)
    return {
        "user_id_extracted": user_id,
        "babies_found":      len(babies),
        "babies":            babies,
        "auto_selected":     bid,
        "context_injected":  context
    }


# ============================================================

# A tiny admin endpoint to reset key rotation state without restarting
# the app, once you've manually rotated/refreshed a Groq key.
#
# IMPORTANT: this is unauthenticated as written — at minimum, protect it
# with a simple shared secret before exposing it publicly. Example below.
# ============================================================

import os
from fastapi import HTTPException
from services.key_manager import reset as reset_key_state, get_status

ADMIN_SECRET = os.getenv("ADMIN_SECRET", "")  # set a real value in .env


@app.post("/admin/reset-groq-keys")
def admin_reset_groq_keys(secret: str):
    if not ADMIN_SECRET or secret != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Invalid admin secret")
    reset_key_state()
    return {"status": "reset", "current_state": get_status()}


@app.get("/admin/groq-key-status")
def admin_groq_key_status(secret: str):
    if not ADMIN_SECRET or secret != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Invalid admin secret")
    return get_status()


# Usage once a key is rotated:
#   POST /admin/reset-groq-keys?secret=YOUR_ADMIN_SECRET
# Check current state any time:
#   GET /admin/groq-key-status?secret=YOUR_ADMIN_SECRET