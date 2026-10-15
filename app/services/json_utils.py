import json
import re

FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def parse_llm_json(text: str) -> dict:
    text = text.strip()
    fenced = FENCE.search(text)
    if fenced:
        text = fenced.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("в ответе модели нет JSON-объекта")
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON модели не разбирается: {exc.msg}") from exc
