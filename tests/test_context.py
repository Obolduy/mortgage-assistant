from app.llm import cost
from app.rag.context import build_context, source_ids


def hit(id, text, **kw):
    return {"id": id, "text": text, "filename": "f.pdf", "section": "", "page": None, "sheet": None,
            "row_no": None} | kw


def test_context_labels_sources():
    ctx = build_context([hit(7, "без комиссий", page=2, section="3. Досрочное погашение"),
                         hit(9, "IP-FAMILY-6", filename="tariffs.xlsx", sheet="Программы", row_no=3)], 1000)
    assert "[7 | f.pdf | стр. 2 | 3. Досрочное погашение]\nбез комиссий" in ctx
    assert "[9 | tariffs.xlsx | Программы, строка 3]" in ctx
    assert source_ids(ctx) == {7, 9}


def test_context_drops_duplicates_and_respects_budget():
    ctx = build_context([hit(1, "а" * 50), hit(2, "а" * 50), hit(3, "б" * 50), hit(4, "в" * 50)], 140)
    assert source_ids(ctx) == {1, 3}


def test_context_keeps_first_even_if_too_long():
    assert source_ids(build_context([hit(1, "а" * 500)], 100)) == {1}


def test_empty_context():
    assert build_context([], 100) == "Ничего не найдено."


def test_cost_in_micros(monkeypatch):
    monkeypatch.setattr(cost.settings, "llm_prices", {"cloud": (150_000, 600_000)})
    assert cost.cost_micros("cloud", 1000, 500) == 450
    assert cost.cost_micros("gemma-4-e4b-it", 1000, 500) == 0
