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
