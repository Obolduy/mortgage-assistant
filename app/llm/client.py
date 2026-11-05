import asyncio
import time

import psycopg
from agents import (
    Agent,
    OpenAIChatCompletionsModel,
    Runner,
    RunResult,
    set_default_openai_api,
    set_default_openai_client,
    set_tracing_disabled,
)
from openai import AsyncOpenAI

from app.core import db
from app.core.config import settings
from app.core.logging import get_logger, request_id
from app.llm.cost import cost_micros
from app.repositories import llm_calls

log = get_logger(__name__)

_configured = False
_cloud_model: OpenAIChatCompletionsModel | None = None


def setup_llm() -> None:
    global _configured
    if _configured:
        return
    client = AsyncOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        timeout=settings.llm_timeout_s,
        max_retries=settings.llm_max_retries,
    )
    set_default_openai_client(client)
    set_default_openai_api("chat_completions")
    set_tracing_disabled(True)
    _configured = True


def cloud_enabled() -> bool:
    return bool(settings.cloud_base_url and settings.cloud_model)


def cloud_model() -> OpenAIChatCompletionsModel:
    global _cloud_model
    if _cloud_model is None:
        client = AsyncOpenAI(
            base_url=settings.cloud_base_url,
            api_key=settings.cloud_api_key,
            timeout=settings.llm_timeout_s,
            max_retries=settings.llm_max_retries,
        )
        _cloud_model = OpenAIChatCompletionsModel(settings.cloud_model, client)
    return _cloud_model


async def run_agent(agent: Agent, prompt: str | list, context=None, cloud: bool = False) -> RunResult:
    setup_llm()
    started = time.monotonic()
    tier, model = ("cloud", settings.cloud_model) if cloud else ("local", str(agent.model))
    result = await asyncio.wait_for(
        Runner.run(agent.clone(model=cloud_model()) if cloud else agent, prompt, context=context,
                   max_turns=settings.agent_max_turns),
        timeout=settings.agent_timeout_s,
    )
    duration_ms = int((time.monotonic() - started) * 1000)
    tools = [i.raw_item.name for i in result.new_items if i.type == "tool_call_item"]
    log.info("agent_run", agent=agent.name, tier=tier, tools=tools, latency_ms=duration_ms)
    record_usage(agent.name, model, tier, result.context_wrapper.usage, duration_ms)
    return result


def record_usage(agent: str, model: str, tier: str, usage, duration_ms: int) -> None:
    try:
        with db.connection() as conn:
            llm_calls.add(
                conn, request_id=request_id(), agent=agent, model=model, tier=tier, requests=usage.requests,
                input_tokens=usage.input_tokens, output_tokens=usage.output_tokens,
                cost_micros=cost_micros(model, usage.input_tokens, usage.output_tokens), duration_ms=duration_ms,
            )
    except psycopg.Error as exc:
        log.warning("llm_call_not_recorded", error=str(exc))
