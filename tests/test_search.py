import math
from uuid import uuid4

import pytest

from app.core import db
from app.parsers.chunker import Chunk
from app.rag import embedder, retrieval
from app.repositories import chunks, documents

DIM = 768


def unit(**axes: float) -> list[float]:
    vec = [0.0] * DIM
    for axis, value in axes.items():
        vec[int(axis[1:])] = value
    norm = math.sqrt(sum(x * x for x in vec))
    return [x / norm for x in vec]


ROWS = [
    ("Досрочное погашение без комиссий, минимальная сумма 10 000 рублей", "Комиссии", None, unit(a0=1)),
    ("Дату платежа можно менять не чаще одного раза в 12 месяцев", "Условия", None, unit(a1=1)),
    ("Программы. Код программы: IP-FAMILY-6; Название: Семейная ипотека; Ставка, % годовых: 6",
     "Программы", "IP-FAMILY-6", unit(a2=1)),
    ("Программы. Код программы: IP-IT-5; Название: Ипотека для IT-специалистов; Ставка, % годовых: 5",
     "Программы", "IP-IT-5", unit(a2=1, a3=0.2)),
]


@pytest.fixture
def corpus():
    name = f"test-{uuid4().hex[:8]}.xlsx"
    ids = [uuid4().hex[:16], uuid4().hex[:16]]
    with db.connection() as conn:
        for doc_id, status in zip(ids, ["indexed", "parsing"]):
            documents.create(conn, doc_id, name, b"-")
            documents.set_status(conn, doc_id, status)
            documents.replace_chunks(conn, doc_id, [
                Chunk(n, text, "row" if code else "text", section, None, "Программы" if code else None,
                      n + 2 if code else None, code)
                for n, (text, section, code, _) in enumerate(ROWS)
            ])
            pending = chunks.pending(conn, "fixed", 100, doc_id)
            chunks.set_embeddings(conn, [(c["id"], row[3]) for c, row in zip(pending, ROWS)], "fixed")
    yield name
    with db.connection() as conn:
        conn.execute("DELETE FROM documents WHERE id = ANY(%s)", (ids,))


def texts(hits):
    return [h["text"] for h in hits]


def test_vector_ranks_by_cosine_and_cuts_by_threshold(corpus):
    with db.connection() as conn:
        hits = chunks.search_vector(conn, unit(a0=1, a1=0.5), 5, 0.3, corpus)
        assert texts(hits) == [ROWS[0][0], ROWS[1][0]]
        assert hits[0]["score"] == pytest.approx(2 / math.sqrt(5), abs=1e-4)
        assert chunks.search_vector(conn, unit(a5=1), 5, 0.3, corpus) == []


def test_fts_finds_program_code(corpus):
    with db.connection() as conn:
        assert texts(chunks.search_fts(conn, "IP-FAMILY-6", 5, corpus)) == [ROWS[2][0]]
        assert texts(chunks.search_fts(conn, "досрочное погашение", 5, corpus)) == [ROWS[0][0]]


def test_threshold_applies_only_to_vector_branch(corpus):
    with db.connection() as conn:
        hits = chunks.search_hybrid(conn, "IP-FAMILY-6", unit(a9=1), 5, 0.99, corpus)
    assert texts(hits) == [ROWS[2][0]]


def test_hybrid_merges_both_branches(corpus):
    with db.connection() as conn:
        hits = chunks.search_hybrid(conn, "досрочное погашение", unit(a1=1), 5, 0.5, corpus)
    assert set(texts(hits)) == {ROWS[0][0], ROWS[1][0]}


def test_vector_confuses_codes_exact_lookup_does_not(corpus, monkeypatch):
    monkeypatch.setattr(embedder, "embed_query", lambda q: unit(a2=1, a3=0.2))
    vector = retrieval.search("ставка по IP-FAMILY-6", "vector", 1, corpus)
    hybrid = retrieval.search("ставка по ip-family-6", "hybrid", 3, corpus)
    assert vector[0]["program_code"] == "IP-IT-5"
    assert hybrid[0]["program_code"] == "IP-FAMILY-6"
    assert len({h["id"] for h in hybrid}) == len(hybrid)


def test_not_indexed_documents_are_hidden(corpus):
    with db.connection() as conn:
        assert len(chunks.search_fts(conn, "IP-FAMILY-6", 10, corpus)) == 1
