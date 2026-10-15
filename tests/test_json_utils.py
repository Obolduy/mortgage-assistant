import pytest

from app.services.json_utils import parse_llm_json


def test_clean_json():
    assert parse_llm_json('{"a": 1}') == {"a": 1}


def test_fenced_json():
    assert parse_llm_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_text_around_json():
    assert parse_llm_json('Вот ответ: {"a": 1} Надеюсь, помог!') == {"a": 1}


@pytest.mark.parametrize("text", ["", "просто текст", '{"a": 1,,}'])
def test_garbage(text):
    with pytest.raises(ValueError):
        parse_llm_json(text)
