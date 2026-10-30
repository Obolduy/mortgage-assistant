from dataclasses import dataclass, field

from agents import MaxTurnsExceeded
from pydantic import ValidationError

from app.agents.prompts import assistant_agent
from app.agents.tools import ClientContext
from app.core.config import settings
from app.core.logging import get_logger
from app.domain.money import format_rub
from app.llm.client import run_agent
from app.schemas.assistant import AssistantAnswer
from app.services import loans
from app.services.figures import tool_outputs, unconfirmed_money
from app.services.json_utils import parse_llm_json

log = get_logger(__name__)

HANDOFF = AssistantAnswer(
    intent="other",
    answer="Не смог разобраться с вопросом, передаю его сотруднику банка.",
    needs_human=True,
    confidence=0,
)


@dataclass
class Reply:
    answer: AssistantAnswer
    tools: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)


def check_answer(result, question: str, outputs: list[str]) -> tuple[AssistantAnswer | None, str | None]:
    out = result.final_output
    if not isinstance(out, AssistantAnswer):
        try:
            out = AssistantAnswer.model_validate(parse_llm_json(str(out)))
        except (ValueError, ValidationError) as exc:
            return None, f"ответ не соответствует формату: {str(exc)[:400]}"
    bad = unconfirmed_money(out.answer, question, outputs)
    if bad:
        sums = ", ".join(format_rub(k) for k in sorted(bad))
        return None, f"суммы {sums} нет в результатах инструментов, бери цифры только оттуда"
    return out, None


async def ask(loan_id: int, question: str) -> Reply | None:
    if loans.get_loan(loan_id) is None:
        return None
    context = ClientContext(loan_id)
    prompt = question
    reply = Reply(HANDOFF)
    for attempt in range(1, settings.answer_max_attempts + 1):
        try:
            result = await run_agent(assistant_agent, prompt, context)
        except MaxTurnsExceeded:
            return reply
        reply.tools += [i.raw_item.name for i in result.new_items if i.type == "tool_call_item"]
        reply.outputs += tool_outputs(result)
        answer, error = check_answer(result, question, reply.outputs)
        if error is None:
            if answer.confidence < settings.confidence_threshold:
                answer = answer.model_copy(update={"needs_human": True})
            reply.answer = answer
            return reply
        log.warning("answer_rejected", attempt=attempt, error=error)
        prompt = result.to_input_list() + [
            {"role": "user", "content": f"Твой ответ не прошел проверку: {error}. Перепиши свой ответ клиенту, "
             "исправив ошибку, и верни только JSON по формату. Не извиняйся."}
        ]
    return reply
