import asyncio
import json
from pathlib import Path

from app.core import db
from app.core.logging import setup_logging
from app.services import assistant

CASES = Path(__file__).with_name("cases.json")


def tools_ok(expected: list[str], called: list[str]) -> bool:
    rest = iter(called)
    return all(name in rest for name in expected)


async def run_case(case: dict) -> dict:
    reply = await assistant.ask(case["loan_id"], case["input"])
    checks = {
        "tools": tools_ok(case["expected_tools"], reply.tools),
        "needs_human": reply.answer.needs_human == case["expected_needs_human"],
    }
    return {"id": case["id"], "category": case["category"], "tools": reply.tools,
            "answer": reply.answer.answer, "checks": checks, "passed": all(checks.values())}


async def main() -> None:
    setup_logging()
    results = [await run_case(case) for case in json.loads(CASES.read_text())]
    for r in results:
        marks = " ".join(f"{k}={'ok' if v else 'FAIL'}" for k, v in r["checks"].items())
        print(f"{'PASS' if r['passed'] else 'FAIL'}  {r['id']:14} {marks}  tools={r['tools']}")
        if not r["passed"]:
            print(f"      ответ: {r['answer'][:200]}")
    print(f"\nпрошло {sum(r['passed'] for r in results)} из {len(results)}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    finally:
        db.close_pool()
