from types import SimpleNamespace

import pytest
from agents.models import _openai_shared

from app.core.config import settings
from app.llm import client


@pytest.mark.asyncio
async def test_run_agent_passes_budget_and_context(monkeypatch):
    seen = {}

    async def fake_run(agent, prompt, *, context=None, max_turns=None):
        seen.update(context=context, max_turns=max_turns)
        return SimpleNamespace(new_items=[])

    monkeypatch.setattr(client.Runner, "run", fake_run)
    await client.run_agent(SimpleNamespace(name="A"), "вопрос", context="ctx")
    assert seen == {"context": "ctx", "max_turns": settings.agent_max_turns}


def test_retries_live_in_http_client():
    client.setup_llm()
    assert _openai_shared.get_default_openai_client().max_retries == settings.llm_max_retries
