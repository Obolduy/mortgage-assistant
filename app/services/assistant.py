from dataclasses import dataclass, field

from agents import AgentsException
from openai import APIError
from pydantic import ValidationError

from app.agents.prompts import assistant_agent
from app.agents.tools import ClientContext
from app.core.config import settings
from app.core.logging import get_logger
from app.domain.money import format_rub
from app.guardrails.pii import mask_pii
from app.llm.client import cloud_enabled, run_agent
from app.schemas.assistant import AssistantAnswer
from app.services import loans
from app.services.citations import citation_error, seen_sources
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
    tier: str = "local"


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
    error = citation_error(out.sources, seen_sources(outputs))
    if error:
        return None, error
    return out, None


async def try_model(reply: Reply, question: str, context: ClientContext, cloud: bool) -> None:
    prompt = question
    for attempt in range(1, settings.answer_max_attempts + 1):
        try:
            result = await run_agent(assistant_agent, prompt, context, cloud=cloud)
        except (AgentsException, TimeoutError, APIError) as exc:
            log.warning("model_failed", cloud=cloud, error=str(exc)[:200])
            return
        reply.tools += [i.raw_item.name for i in result.new_items if i.type == "tool_call_item"]
        reply.outputs += tool_outputs(result)
        answer, error = check_answer(result, question, reply.outputs)
        if error is None:
            if answer.confidence < settings.confidence_threshold:
                answer = answer.model_copy(update={"needs_human": True})
            reply.answer = answer
            return
        log.warning("answer_rejected", attempt=attempt, error=error)
        prompt = result.to_input_list() + [
            {"role": "user", "content": f"Твой ответ не прошел проверку: {error}. Перепиши свой ответ клиенту, "
             "исправив ошибку, и верни только JSON по формату. Не извиняйся."}
        ]


async def ask(loan_id: int, question: str) -> Reply | None:
    if loans.get_loan(loan_id) is None:
        return None
    context = ClientContext(loan_id)
    question = mask_pii(question)[0]
    reply = Reply(HANDOFF)
    await try_model(reply, question, context, cloud=False)
    if reply.answer is HANDOFF and cloud_enabled():
        log.info("escalated_to_cloud")
        reply.tier, reply.outputs = "cloud", []
        await try_model(reply, question, context, cloud=True)
    return reply
