from typing import Literal, Optional

from pydantic import BaseModel


class ChatRequest(BaseModel):
    mode: Literal["patient", "population"]
    question: str
    patient_id: Optional[str] = None


class RetrievedChunk(BaseModel):
    id: str
    record_type: str
    date: str
    patient_id: str
    score: float
    snippet: str


class ChatTrace(BaseModel):
    router_path: Literal["vector", "structured"]
    router_reason: str
    patient_id: Optional[str] = None
    retrieved: list[RetrievedChunk] = []
    cited_ids: list[str] = []
    sql: Optional[str] = None


class ChatResponse(BaseModel):
    answer: str
    trace: ChatTrace
