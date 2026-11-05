from pathlib import Path

from app.guardrails.pii import mask_pii, valid_card, valid_inn
from app.rag.context import build_context
from app.services.documents import parse

DATA = Path(__file__).resolve().parent.parent / "data"


def test_application_is_masked():
    chunk = parse("client_application.docx", (DATA / "client_application.docx").read_bytes())[0]
    masked, found = mask_pii(chunk.text)
    assert found == {"email": 1, "passport": 1, "inn": 1, "phone": 1}
    for secret in ("4510 123456", "+7 916 123-45-67", "p.ivanov@example.ru", "500100732259"):
        assert secret not in masked
    assert "[ТЕЛЕФОН_1]" in masked and "Паспорт: [ПАСПОРТ_1]" in masked
    assert "ИК-2025-0001" in masked


def test_wrong_inn_checksum_stays():
    assert valid_inn("500100732259")
    text = "Артикул 500100732250"
    assert mask_pii(text) == (text, {})


def test_ten_digit_inn():
    assert valid_inn("7707083893")
    assert mask_pii("ИНН банка 7707083893")[0] == "ИНН банка [ИНН_1]"


def test_card_by_luhn_only():
    assert valid_card("4111 1111 1111 1111")
    assert mask_pii("карта 4111 1111 1111 1111")[0] == "карта [КАРТА_1]"
    assert mask_pii("счет 4111 1111 1111 1112")[1] == {}


def test_money_and_dates_are_not_pii():
    text = "Сумма 5 000 000 рублей, платеж 55 054,31 ₽, договор № ИК-2025-0001 от 15.10.2025, срок 240 месяцев"
    assert mask_pii(text) == (text, {})


def test_phone_formats():
    for phone in ("+7 916 123-45-67", "8 (916) 123-45-67", "+79161234567"):
        assert mask_pii(f"звонить {phone}")[0] == "звонить [ТЕЛЕФОН_1]"


def test_context_is_masked_before_model():
    hit = {"id": 1, "text": "Телефон: +7 916 123-45-67", "filename": "a.docx", "section": "", "page": None,
           "sheet": None, "row_no": None}
    context = build_context([hit], 1000)
    assert "+7 916" not in context and "[ТЕЛЕФОН_1]" in context
