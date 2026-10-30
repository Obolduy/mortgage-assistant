import json
import re

MONEY = re.compile(r"(\d{1,3}(?:[   ]\d{3})+|\d+)(?:,(\d{1,2}))?\s*(?:₽|руб)")
NUMBER = re.compile(r"\d{1,3}(?:[   ]\d{3})+|\d+")


def _kopecks(rub: str, kop: str | None) -> int:
    return int(re.sub(r"\D", "", rub)) * 100 + int((kop or "0").ljust(2, "0"))


def money_in(text: str) -> set[int]:
    return {_kopecks(rub, kop) for rub, kop in MONEY.findall(text)}


def numbers_in(text: str) -> set[int]:
    return {int(re.sub(r"\D", "", n)) * 100 for n in NUMBER.findall(text)}


def tool_outputs(result) -> list[str]:
    outputs = (i.output for i in result.new_items if i.type == "tool_call_output_item")
    return [o if isinstance(o, str) else json.dumps(o, ensure_ascii=False, default=str) for o in outputs]


def unconfirmed_money(answer: str, question: str, outputs: list[str]) -> set[int]:
    evidence = " ".join(outputs)
    allowed = money_in(evidence) | numbers_in(evidence) | numbers_in(question)
    return money_in(answer) - allowed
