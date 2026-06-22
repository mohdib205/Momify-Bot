from pydantic import BaseModel
from typing import Optional


class Message(BaseModel):
    role:    str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[Message] = []
    baby_id: Optional[int] = None
    query_subject: Optional[str] = "baby"  # "baby" (default) or "mother" — when "mother", baby_context is not fetched/injected


class ChatResponse(BaseModel):
    reply:            str
    mode:             str
    score:            float
    response_time_ms: int     # Java backend uses this for async ML observability write
    query_subject:    str     # "baby" or "mother" — echoed back so Java can log it alongside mode/score


class FeedbackRequest(BaseModel):
    query:          str
    bot_response:   str
    mode:           str
    score:          float
    verdict:        str
    failure_reason: str = ""
    doctor_notes:   str = ""
    reviewed_by:    str


class FeedbackResponse(BaseModel):
    success: bool
    message: str