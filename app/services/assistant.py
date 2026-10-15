from agents import MaxTurnsExceeded

from app.agents.prompts import assistant_agent
from app.agents.tools import ClientContext
from app.llm.client import run_agent
from app.schemas.assistant import AssistantAnswer
from app.services import loans

HANDOFF = AssistantAnswer(
    intent="other",
    answer="Не смог разобраться с вопросом, передаю его сотруднику банка.",
    needs_human=True,
    confidence=0,
)


async def ask(loan_id: int, question: str) -> AssistantAnswer | None:
    if loans.get_loan(loan_id) is None:
        return None
    try:
        result = await run_agent(assistant_agent, question, ClientContext(loan_id))
    except MaxTurnsExceeded:
        return HANDOFF
    return AssistantAnswer.model_validate_json(result.final_output)
