from types import SimpleNamespace

import pytest
from agents import MaxTurnsExceeded
from fastapi.testclient import TestClient
from openai import APIConnectionError

from app.core.config import settings
from app.main import app
from app.services import assistant

client = TestClient(app)
GOOD = '{"intent": "other", "answer": "Здравствуйте", "confidence": 0.9}'


def ok(text=GOOD):
    return SimpleNamespace(final_output=text, new_items=[], to_input_list=lambda: [{"role": "user"}])


@pytest.fixture
def cloud_on(monkeypatch):
    monkeypatch.setattr(settings, "cloud_base_url", "http://cloud/v1")
    monkeypatch.setattr(settings, "cloud_model", "cloud-model")


def script(monkeypatch, *steps):
    calls = []
    steps = iter(steps)

    async def run(agent, prompt, context=None, cloud=False):
        calls.append({"cloud": cloud, "prompt": prompt})
        step = next(steps)
        if isinstance(step, Exception):
            raise step
        return step

    monkeypatch.setattr(assistant, "run_agent", run)
    return calls


def ask(question="Здравствуйте"):
    return client.post("/ask", json={"loan_id": 1, "question": question}).json()


def test_local_answer_stays_local(monkeypatch, cloud_on):
    calls = script(monkeypatch, ok())
    assert ask()["answer"] == "Здравствуйте"
    assert [c["cloud"] for c in calls] == [False]


def test_bad_format_twice_goes_to_cloud(monkeypatch, cloud_on):
    calls = script(monkeypatch, ok("не JSON"), ok("снова не JSON"), ok())
    assert ask()["needs_human"] is False
    assert [c["cloud"] for c in calls] == [False, False, True]


def test_turn_budget_goes_to_cloud(monkeypatch, cloud_on):
    calls = script(monkeypatch, MaxTurnsExceeded("6 ходов"), ok())
    assert ask()["needs_human"] is False
    assert [c["cloud"] for c in calls] == [False, True]


def test_dead_local_model_goes_to_cloud(monkeypatch, cloud_on):
    calls = script(monkeypatch, APIConnectionError(request=None), ok())
    assert ask()["needs_human"] is False
    assert [c["cloud"] for c in calls] == [False, True]


def test_human_needed_is_not_escalated(monkeypatch, cloud_on):
    calls = script(monkeypatch, ok('{"intent": "other", "answer": "Передаю", "needs_human": true, "confidence": 0.9}'))
    assert ask()["needs_human"] is True
    assert len(calls) == 1


def test_no_cloud_means_human(monkeypatch):
    calls = script(monkeypatch, APIConnectionError(request=None))
    assert ask()["needs_human"] is True
    assert len(calls) == 1


def test_cloud_failure_means_human(monkeypatch, cloud_on):
    script(monkeypatch, APIConnectionError(request=None), APIConnectionError(request=None))
    assert ask()["needs_human"] is True


def test_cloud_sees_masked_question(monkeypatch, cloud_on):
    calls = script(monkeypatch, APIConnectionError(request=None), ok())
    ask("Мой телефон +7 916 123-45-67, перезвоните")
    assert all("+7 916" not in c["prompt"] for c in calls)
    assert "[ТЕЛЕФОН_1]" in calls[1]["prompt"]
