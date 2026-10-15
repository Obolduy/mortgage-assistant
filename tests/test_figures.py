from types import SimpleNamespace

from app.services.figures import money_in, unconfirmed_money


def result_with(*outputs):
    return SimpleNamespace(new_items=[SimpleNamespace(type="tool_call_output_item", output=o) for o in outputs])


def test_money_in():
    assert money_in("платеж 49 477,38 ₽, экономия 771 538 руб.") == {4_947_738, 77_153_800}


def test_money_from_tool_is_confirmed():
    result = result_with({"new_payment": "49 477,38 ₽"})
    assert unconfirmed_money("Новый платеж 49 477,38 ₽", "вопрос", result) == set()


def test_money_from_question_is_confirmed():
    assert unconfirmed_money("Вносите 500 000 ₽", "внесу 500 000 досрочно", result_with()) == set()


def test_invented_money():
    result = result_with({"new_payment": "49 477,38 ₽"})
    assert unconfirmed_money("Новый платеж около 48 900 ₽", "вопрос", result) == {4_890_000}
