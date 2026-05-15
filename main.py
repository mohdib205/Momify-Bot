from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager

import psycopg2
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

qa_data = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    global qa_data
    app_logger.info("Momify API starting up...")
    qa_data = load_qa(QA_FILE)
    app_logger.info(f"Loaded {len(qa_data)} Q&A pairs from {QA_FILE}")
    yield
    app_logger.info("Momify API shutting down.")


app = FastAPI(title="Momify API", lifespan=lifespan)


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    try:
        reply, mode, score = get_response(req.message, qa_data, req.history)
        return ChatResponse(reply=reply, mode=mode, score=score)

    except Exception as e:
        app_logger.error(f"Unhandled error in /chat: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/submit_feedback", response_model=FeedbackResponse)
def submit_feedback(req: FeedbackRequest):

    db_url = os.environ.get("DB_URL")

    if not db_url:
        raise HTTPException(status_code=500, detail="DB_URL not configured")

    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO doctor_feedback
            (
                query,
                bot_response,
                mode,
                score,
                verdict,
                failure_reason,
                doctor_notes,
                reviewed_by,
                reviewed_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            req.query,
            req.bot_response,
            req.mode,
            req.score,
            req.verdict,
            req.failure_reason,
            req.doctor_notes,
            req.reviewed_by,
            datetime.now()
        ))

        conn.commit()

        cur.close()
        conn.close()

        return FeedbackResponse(
            success=True,
            message="Feedback submitted successfully"
        )

    except Exception as e:
        app_logger.error(f"Error in /submit_feedback: {e}")

        raise HTTPException(
            status_code=500,
            detail="Could not save feedback"
        )


@app.get("/health")
def health():
    return {
        "status": "ok",
        "qa_pairs_loaded": len(qa_data)
    }