from typing import Literal

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    loan_id: int
    question: str = Field(min_length=1, max_length=2000)


class AssistantAnswer(BaseModel):
    intent: Literal["schedule", "early_repayment", "payment_day", "other"]
    answer: str
    needs_human: bool = False
    confidence: float = Field(ge=0, le=1)
