from types import SimpleNamespace

import pytest
from agents import MaxTurnsExceeded
from fastapi.testclient import TestClient

from app.main import app
from app.services import assistant

client = TestClient(app)

TOOL = SimpleNamespace(type="tool_call_output_item", output={"new_payment": "49 477,38 ₽"})
GOOD = '{"intent": "early_repayment", "answer": "Новый платеж 49 477,38 ₽", "confidence": 0.9}'
INVENTED = '{"intent": "early_repayment", "answer": "Новый платеж около 48 900 ₽", "confidence": 0.9}'
UNSURE = '{"intent": "early_repayment", "answer": "Новый платеж 49 477,38 ₽", "confidence": 0.3}'


def result(final_output):
    return SimpleNamespace(final_output=final_output, new_items=[TOOL], to_input_list=lambda: [{"role": "user"}])


@pytest.fixture
def agent_says(monkeypatch):
    calls = []

    def script(*outputs):
        replies = iter(outputs)

        async def run(agent, prompt, context=None):
            calls.append((prompt, context))
            return result(next(replies))

        monkeypatch.setattr(assistant, "run_agent", run)
        return calls

    return script


def ask(question="Через год внесу 500 000 и уменьшу платеж"):
    return client.post("/ask", json={"loan_id": 1, "question": question})


def test_good_answer(agent_says):
    calls = agent_says(GOOD)
    assert ask().json()["answer"] == "Новый платеж 49 477,38 ₽"
    assert calls[0][1].loan_id == 1


def test_dirty_json_is_parsed(agent_says):
    agent_says("Конечно! ```json\n" + GOOD + "\n```")
    assert ask().json()["needs_human"] is False


def test_invalid_answer_is_healed_with_error(agent_says):
    calls = agent_says("не JSON", GOOD)
    assert ask().json()["answer"] == "Новый платеж 49 477,38 ₽"
    retry_prompt = calls[1][0]
    assert "не прошел проверку" in retry_prompt[-1]["content"]


def test_invented_money_twice_goes_to_human(agent_says):
    calls = agent_says(INVENTED, INVENTED)
    body = ask().json()
    assert body["needs_human"] is True
    assert "48 900,00 ₽" in calls[1][0][-1]["content"]


def test_low_confidence_goes_to_human(agent_says):
    agent_says(UNSURE)
    assert ask().json()["needs_human"] is True


def test_unknown_loan(agent_says):
    calls = agent_says(GOOD)
    assert client.post("/ask", json={"loan_id": 999999, "question": "?"}).status_code == 404
    assert calls == []


def test_turn_budget_goes_to_human(monkeypatch):
    async def run(agent, prompt, context=None):
        raise MaxTurnsExceeded("6 ходов")

    monkeypatch.setattr(assistant, "run_agent", run)
    assert ask().json()["needs_human"] is True
