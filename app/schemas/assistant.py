import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

SOURCE_NUMBER = re.compile(r"\d+")


class AskRequest(BaseModel):
    loan_id: int
    question: str = Field(min_length=1, max_length=2000)


class AssistantAnswer(BaseModel):
    intent: Literal["schedule", "early_repayment", "payment_day", "policy", "other"]
    answer: str
    sources: list[int] = []
    needs_human: bool = False
    confidence: float = Field(ge=0, le=1)

    @field_validator("sources", mode="before")
    @classmethod
    def source_numbers(cls, value):
        if not isinstance(value, list):
            return value
        return [int(m.group()) if isinstance(v, str) and (m := SOURCE_NUMBER.search(v)) else v for v in value]
