from pydantic import BaseModel


class Message(BaseModel):
    role: str       # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[Message] = []


class ChatResponse(BaseModel):
    reply: str
    mode: str       # data / weak / fallback / emergency
    score: float

from pydantic import BaseModel


class FeedbackRequest(BaseModel):
    query: str
    bot_response: str
    mode: str
    score: float
    verdict: str
    failure_reason: str = ""
    doctor_notes: str = ""
    reviewed_by: str


class FeedbackResponse(BaseModel):
    success: bool
    message: str