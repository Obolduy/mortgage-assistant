from datetime import datetime

from pydantic import BaseModel


class Document(BaseModel):
    id: str
    filename: str
    status: str
    error: str | None
    chunks_count: int
    created_at: datetime
    updated_at: datetime


class Hit(BaseModel):
    id: int
    text: str
    filename: str
    section: str
    page: int | None
    sheet: str | None
    row_no: int | None
    program_code: str | None
    score: float
