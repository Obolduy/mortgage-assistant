from app.domain.money import format_rub


def test_format_rub():
    assert format_rub(4_947_738) == "49 477,38 ₽"
    assert format_rub(5) == "0,05 ₽"
    assert format_rub(500_000_000) == "5 000 000,00 ₽"
