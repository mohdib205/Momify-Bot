from pydantic import BaseModel
from typing import Optional


class Message(BaseModel):
    role:    str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[Message] = []
    baby_id: Optional[int] = None   # ← parent app sends selected baby ID


class ChatResponse(BaseModel):
    reply: str
    mode:  str
    score: float


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