from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager

from core.config import QA_FILE
from core.logger import app_logger
from models.schemas import ChatRequest, ChatResponse
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


@app.get("/health")
def health():
    return {"status": "ok", "qa_pairs_loaded": len(qa_data)}
