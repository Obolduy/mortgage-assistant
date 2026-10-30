from fastapi import APIRouter, HTTPException
from pydantic import ValidationError

from app.schemas.assistant import AskRequest, AssistantAnswer
from app.services import assistant

router = APIRouter(tags=["assistant"])


@router.post("/ask", response_model=AssistantAnswer)
async def ask(body: AskRequest):
    try:
        reply = await assistant.ask(body.loan_id, body.question)
    except ValidationError as exc:
        raise HTTPException(502, "ответ модели не по формату") from exc
    if reply is None:
        raise HTTPException(404, "кредит не найден")
    return reply.answer
