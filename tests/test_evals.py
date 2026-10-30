import json
from pathlib import Path
from types import SimpleNamespace

from app.schemas.assistant import AssistantAnswer
from app.services.assistant import Reply
from evals import judge as judge_module
from evals.runner import checks, score, summary, tools_ok

CASES = json.loads((Path(__file__).resolve().parent.parent / "evals" / "cases.json").read_text())
CASE = {"expected_tools": ["search_policies"], "forbidden_tools": ["create_payment_date_application"],
        "expected_needs_human": False, "expected_text": ["10 000"], "forbidden_text": ["0,1%"], "must_cite": True}


def reply(text="Минимум 10000 рублей", tools=("search_policies",), sources=(7,), seen=(7,), needs_human=False):
    answer = AssistantAnswer(intent="policy", answer=text, sources=list(sources), needs_human=needs_human,
                             confidence=0.9)
    return Reply(answer, list(tools), ["\n".join(f"[{i} | f.pdf]\nтекст" for i in seen)])


def test_cases_are_complete():
    assert len(CASES) >= 15
    assert len({c["id"] for c in CASES}) == len(CASES)
    assert sum(c["is_negative"] for c in CASES) >= 3
    assert all(c["rubric"] for c in CASES)


def test_tools_order_matters_extra_calls_allowed():
    assert tools_ok(["get_loan", "simulate_early_repayment"], ["get_loan", "get_schedule", "simulate_early_repayment"])
    assert not tools_ok(["get_loan", "simulate_early_repayment"], ["simulate_early_repayment", "get_loan"])


def test_checks_pass_and_text_ignores_spaces():
    assert all(checks(CASE, reply()).values())


def test_checks_catch_each_failure():
    assert not checks(CASE, reply(tools=()))["tools"]
    assert not checks(CASE, reply(tools=("search_policies", "create_payment_date_application")))["forbidden"]
    assert not checks(CASE, reply(text="Минимум 5 000 рублей"))["text"]
    assert not checks(CASE, reply(text="10 000, ставка 0,1%"))["text"]
    assert not checks(CASE, reply(sources=(9,)))["citations"]
    assert not checks(CASE, reply(needs_human=True))["needs_human"]


def test_pass_at_k_and_pass_all_k():
    flaky = [{"status": "pass"}, {"status": "fail"}, {"status": "pass"}]
    assert score(flaky) == {"evaluated": True, "pass_at_k": True, "pass_all_k": False, "judge_failed": 0}


def test_judge_failed_is_not_a_fail():
    trials = [{"status": "pass"}, {"status": "judge_failed"}, {"status": "pass"}]
    assert score(trials) == {"evaluated": True, "pass_at_k": True, "pass_all_k": True, "judge_failed": 1}
    assert score([{"status": "judge_failed"}])["evaluated"] is False


def test_summary_by_category():
    results = [{"category": "policy", "evaluated": True, "pass_at_k": True, "pass_all_k": False},
               {"category": "policy", "evaluated": True, "pass_at_k": True, "pass_all_k": True},
               {"category": "policy", "evaluated": False, "pass_at_k": False, "pass_all_k": False}]
    assert summary(results)["policy"] == {"cases": 3, "evaluated": 2, "pass_at_k": 2, "pass_all_k": 1}


async def test_judge_verdicts(monkeypatch):
    from agents import ModelBehaviorError

    outputs = iter([judge_module.Verdict(rationale="все пункты", passed=True),
                    judge_module.Verdict(rationale="нет ссылки", passed=False), ModelBehaviorError("не JSON")])

    async def run(agent, prompt, context=None):
        assert "== РУБРИКА ==" in prompt and agent.name == "Judge"
        out = next(outputs)
        if isinstance(out, Exception):
            raise out
        return SimpleNamespace(final_output=out)

    monkeypatch.setattr(judge_module, "run_agent", run)
    case = {"rubric": "Ответ: 10 000", "input": "Минимальная сумма?"}
    assert (await judge_module.judge(case, reply()))["verdict"] == "pass"
    assert (await judge_module.judge(case, reply()))["verdict"] == "fail"
    assert (await judge_module.judge(case, reply()))["verdict"] == "judge_failed"
