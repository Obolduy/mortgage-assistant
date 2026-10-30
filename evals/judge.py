from agents import Agent, AgentsException, ModelSettings
from openai import APIError
from pydantic import BaseModel

from app.core.config import settings
from app.llm.client import run_agent

JUDGE_INSTRUCTIONS = """Ты – судья. Проверяешь ответ ассистента ипотечного банка по рубрике.
Суммы и факты сверяй с результатами инструментов: только они – правда.
passed = true, только если выполнены все пункты рубрики.
rationale – одно-два предложения: что выполнено, что нет.
"""


class Verdict(BaseModel):
    rationale: str
    passed: bool


judge_agent = Agent(
    name="Judge",
    instructions=JUDGE_INSTRUCTIONS,
    model=settings.llm_small_model,
    model_settings=ModelSettings(temperature=0, max_tokens=2048),
    output_type=Verdict,
)


def judge_prompt(case: dict, reply) -> str:
    outputs = "\n".join(reply.outputs)[:4000] or "нет"
    return (f"== РУБРИКА ==\n{case['rubric']}\n\n== ВОПРОС КЛИЕНТА ==\n{case['input']}\n\n"
            f"== ВЫЗВАННЫЕ ИНСТРУМЕНТЫ ==\n{reply.tools or 'нет'}\n\n== РЕЗУЛЬТАТЫ ИНСТРУМЕНТОВ ==\n{outputs}\n\n"
            f"== ОТВЕТ АССИСТЕНТА ==\n{reply.answer.model_dump_json()}")


async def judge(case: dict, reply) -> dict:
    try:
        result = await run_agent(judge_agent, judge_prompt(case, reply))
    except (TimeoutError, APIError, AgentsException) as exc:
        return {"verdict": "judge_failed", "rationale": str(exc)[:200]}
    verdict = result.final_output
    if not isinstance(verdict, Verdict):
        return {"verdict": "judge_failed", "rationale": "судья вернул не вердикт"}
    return {"verdict": "pass" if verdict.passed else "fail", "rationale": verdict.rationale}
