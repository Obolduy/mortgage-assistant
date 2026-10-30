from types import SimpleNamespace
from uuid import uuid4

import pytest
from agents.models import _openai_shared

from app.core import db
from app.core.config import settings
from app.llm import client

USAGE = SimpleNamespace(requests=2, input_tokens=1200, output_tokens=150)


@pytest.mark.asyncio
async def test_run_agent_passes_budget_and_records_usage(monkeypatch):
    seen = {}

    async def fake_run(agent, prompt, *, context=None, max_turns=None):
        seen.update(context=context, max_turns=max_turns)
        return SimpleNamespace(new_items=[], context_wrapper=SimpleNamespace(usage=USAGE))

    monkeypatch.setattr(client.Runner, "run", fake_run)
    name = f"test-{uuid4().hex[:8]}"
    await client.run_agent(SimpleNamespace(name=name, model="gemma"), "вопрос", context="ctx")
    assert seen == {"context": "ctx", "max_turns": settings.agent_max_turns}
    with db.connection() as conn:
        row = conn.execute(
            "DELETE FROM llm_calls WHERE agent = %s RETURNING model, requests, input_tokens, output_tokens, cost_micros",
            (name,),
        ).fetchone()
    assert row == ("gemma", 2, 1200, 150, 0)


def test_retries_live_in_http_client():
    client.setup_llm()
    assert _openai_shared.get_default_openai_client().max_retries == settings.llm_max_retries
