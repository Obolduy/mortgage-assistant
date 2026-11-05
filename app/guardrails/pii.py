import re
import sys
from pathlib import Path

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]*\w")
PASSPORT = re.compile(r"(?i)(паспорт\D{0,10})(\d{4}\s?\d{6})\b")
CARD = re.compile(r"\b\d(?:[ -]?\d){12,18}\b")
INN = re.compile(r"\b\d{10}(?:\d{2})?\b")
PHONE = re.compile(r"(?<![\d-])(?:\+7|8)[\s(-]*\d{3}[\s)-]*\d{3}[\s-]*\d{2}[\s-]*\d{2}(?![\d-])")

INN_10 = [2, 4, 10, 3, 5, 9, 4, 6, 8]
INN_11 = [7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
INN_12 = [3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8]


def _check_digit(digits: str, weights: list[int]) -> int:
    return sum(int(d) * w for d, w in zip(digits, weights)) % 11 % 10


def valid_inn(value: str) -> bool:
    if len(value) == 10:
        return _check_digit(value, INN_10) == int(value[9])
    return _check_digit(value, INN_11) == int(value[10]) and _check_digit(value, INN_12) == int(value[11])


def valid_card(value: str) -> bool:
    digits = [int(d) for d in re.sub(r"\D", "", value)][::-1]
    if not 13 <= len(digits) <= 19:
        return False
    return sum(d if i % 2 == 0 else (d * 2 - 9 if d > 4 else d * 2) for i, d in enumerate(digits)) % 10 == 0


def mask_pii(text: str) -> tuple[str, dict[str, int]]:
    found = {"email": 0, "passport": 0, "card": 0, "inn": 0, "phone": 0}

    def label(kind: str, title: str) -> str:
        found[kind] += 1
        return f"[{title}_{found[kind]}]"

    text = EMAIL.sub(lambda m: label("email", "ПОЧТА"), text)
    text = PASSPORT.sub(lambda m: m.group(1) + label("passport", "ПАСПОРТ"), text)
    text = CARD.sub(lambda m: label("card", "КАРТА") if valid_card(m.group()) else m.group(), text)
    text = INN.sub(lambda m: label("inn", "ИНН") if valid_inn(m.group()) else m.group(), text)
    text = PHONE.sub(lambda m: label("phone", "ТЕЛЕФОН"), text)
    return text, {k: v for k, v in found.items() if v}


if __name__ == "__main__":
    from app.services.documents import parse

    path = Path(sys.argv[1])
    for chunk in parse(path.name, path.read_bytes()):
        masked, found = mask_pii(chunk.text)
        print(f"[{chunk.ordinal}] {found or 'ПДн нет'}\n    {masked}\n")
