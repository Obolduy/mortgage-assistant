import argparse
import asyncio
import json
import re
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from app.core import db
from app.core.config import settings
from app.core.logging import bind, setup_logging
from app.services import assistant
from app.services.citations import seen_sources
from evals.judge import judge

CASES = Path(__file__).with_name("cases.json")
REPORTS = Path(__file__).with_name("reports")


def squeeze(text: str) -> str:
    return re.sub(r"\s", "", text)


def tools_ok(expected: list[str], called: list[str]) -> bool:
    rest = iter(called)
    return all(name in rest for name in expected)


def checks(case: dict, reply) -> dict[str, bool]:
    answer = squeeze(reply.answer.answer)
    result = {
        "tools": tools_ok(case["expected_tools"], reply.tools),
        "forbidden": not set(case["forbidden_tools"]) & set(reply.tools),
        "text": all(squeeze(t) in answer for t in case["expected_text"])
        and not any(squeeze(t) in answer for t in case["forbidden_text"]),
    }
    if case["expected_needs_human"] is not None:
        result["needs_human"] = reply.answer.needs_human == case["expected_needs_human"]
    if case["must_cite"]:
        sources = set(reply.answer.sources)
        result["citations"] = bool(sources) and sources <= seen_sources(reply.outputs)
    return result


def usage(request_id: str) -> dict:
    with db.connection() as conn:
        row = conn.execute(
            "SELECT coalesce(sum(input_tokens + output_tokens), 0)::bigint, coalesce(sum(cost_micros), 0)::bigint, "
            "coalesce(sum(duration_ms) FILTER (WHERE agent <> 'Judge'), 0)::bigint "
            "FROM llm_calls WHERE request_id = %s",
            (request_id,),
        ).fetchone()
    return {"tokens": row[0], "cost_micros": row[1], "duration_ms": row[2]}


async def run_trial(case: dict, request_id: str) -> dict:
    bind(request_id=request_id)
    reply = await assistant.ask(case["loan_id"], case["input"])
    marks = checks(case, reply)
    verdict = {"verdict": "skipped", "rationale": "детерминированные проверки не прошли"}
    if all(marks.values()):
        verdict = await judge(case, reply)
    status = "fail" if not all(marks.values()) or verdict["verdict"] == "fail" else (
        "judge_failed" if verdict["verdict"] == "judge_failed" else "pass")
    return {"request_id": request_id, "status": status, "checks": marks, "judge": verdict, "tools": reply.tools, "tier": reply.tier,
            "answer": reply.answer.answer, "sources": reply.answer.sources, **usage(request_id)}


def score(trials: list[dict]) -> dict:
    judged = [t["status"] == "pass" for t in trials if t["status"] != "judge_failed"]
    return {"evaluated": bool(judged), "pass_at_k": any(judged), "pass_all_k": bool(judged) and all(judged),
            "judge_failed": sum(t["status"] == "judge_failed" for t in trials)}


def summary(results: list[dict]) -> dict:
    groups = defaultdict(list)
    for r in results:
        groups[r["category"]].append(r)
    groups["всего"] = results
    return {name: {"cases": len(rs), "evaluated": sum(r["evaluated"] for r in rs),
                   "pass_at_k": sum(r["pass_at_k"] for r in rs), "pass_all_k": sum(r["pass_all_k"] for r in rs)}
            for name, rs in groups.items()}


def markdown(report: dict) -> str:
    k = report["k"]
    header = (f"Модель: `{report['model']}`, судья: `{report['judge_model']}`, "
              f"кейсов: {len(report['results'])}, попыток на кейс: {k}.")
    money = report["money"]
    spent = (f"Стоимость прогона: {money['cost_micros']} мкд. Успешных попыток: {money['passed']}, "
             f"на успешную: {money['per_pass_micros']} мкд. Ушло в облако попыток: {money['cloud_trials']}.")
    lines = [f"# Оценка {report['run_id']}", "", header, "", spent, "",
             f"| Категория | Кейсов | Оценено | pass@{k} | pass^{k} |", "| --- | --- | --- | --- | --- |"]
    lines += [f"| {name} | {s['cases']} | {s['evaluated']} | {s['pass_at_k']} | {s['pass_all_k']} |"
              for name, s in report["summary"].items()]
    lines += ["", "| Кейс | Попытки | Токены | Секунд |", "| --- | --- | --- | --- |"]
    for r in report["results"]:
        trials = " ".join(t["status"] for t in r["trials"])
        tokens = sum(t["tokens"] for t in r["trials"]) // len(r["trials"])
        secs = sum(t["duration_ms"] for t in r["trials"]) / len(r["trials"]) / 1000
        lines.append(f"| {r['id']} | {trials} | {tokens} | {secs:.0f} |")
    return "\n".join(lines) + "\n"


async def main(full: bool, k: int) -> None:
    setup_logging()
    cases = [c for c in json.loads(CASES.read_text()) if full or c["smoke"]]
    run_id = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    results = []
    for case in cases:
        runs = [await run_trial(case, f"eval-{run_id}-{case['id']}-{n}") for n in range(1, k + 1)]
        results.append({"id": case["id"], "category": case["category"], "trials": runs, **score(runs)})
        print(f"{case['id']:18} {' '.join(t['status'] for t in runs)}", flush=True)
    trials = [t for r in results for t in r["trials"]]
    passed = sum(t["status"] == "pass" for t in trials)
    cost = sum(t["cost_micros"] for t in trials)
    money = {"cost_micros": cost, "passed": passed, "per_pass_micros": cost // passed if passed else None,
             "cloud_trials": sum(t["tier"] == "cloud" for t in trials)}
    report = {"money": money, "run_id": run_id, "model": settings.llm_model, "judge_model": settings.llm_small_model, "k": k,
              "summary": summary(results), "results": results}
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / f"{run_id}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    (REPORTS / f"{run_id}.md").write_text(markdown(report))
    print("\n" + markdown(report))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true", help="все кейсы вместо быстрого набора")
    parser.add_argument("--k", type=int, default=None, help="попыток на кейс, по умолчанию 3 для --full и 1 иначе")
    args = parser.parse_args()
    try:
        asyncio.run(main(args.full, args.k or (3 if args.full else 1)))
    finally:
        db.close_pool()
