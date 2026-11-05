import json
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core import db
from app.main import app
from app.services import assistant
from app.services.citations import citation_error

client = TestClient(app)


def chunk_id() -> int:
    with db.connection() as conn:
        row = conn.execute("SELECT id FROM chunks LIMIT 1").fetchone()
    return row[0] if row else 0


def test_source_must_be_in_context():
    assert "не было среди найденных" in citation_error([5], {7})


def test_found_but_not_cited():
    assert "без источников" in citation_error([], {7})


def test_no_search_no_sources():
    assert citation_error([], set()) is None


def test_source_in_context_but_not_in_db():
    assert "нет в базе" in citation_error([-1], {-1})


def test_valid_source():
    cid = chunk_id()
    if cid:
        assert citation_error([cid], {cid}) is None


def search_result(final_output, ids):
    context = "\n\n".join(f"[{i} | rules.docx | Комиссии]\nбез комиссий" for i in ids)
    item = SimpleNamespace(type="tool_call_output_item", output=context)
    return SimpleNamespace(final_output=final_output, new_items=[item], to_input_list=lambda: [{"role": "user"}])


def answer(*sources):
    return json.dumps({"intent": "policy", "answer": "Комиссии нет", "confidence": 0.9, "sources": list(sources)})


def test_invented_source_is_healed_then_handed_off(monkeypatch):
    prompts = []

    async def run(agent, prompt, context=None, cloud=False):
        prompts.append(prompt)
        return search_result(answer(999999), [-1])

    monkeypatch.setattr(assistant, "run_agent", run)
    body = client.post("/ask", json={"loan_id": 1, "question": "Есть комиссия?"}).json()
    assert body["needs_human"] is True
    assert "999999" in prompts[1][-1]["content"]


def test_request_id_reaches_header_and_llm_calls(monkeypatch):
    from app.llm import client as llm

    rid = f"test-{uuid4().hex[:8]}"
    usage = SimpleNamespace(requests=1, input_tokens=10, output_tokens=5)

    async def fake_run(agent, prompt, *, context=None, max_turns=None):
        return SimpleNamespace(new_items=[], context_wrapper=SimpleNamespace(usage=usage),
                               final_output='{"intent": "other", "answer": "Здравствуйте", "confidence": 0.9}')

    monkeypatch.setattr(llm.Runner, "run", fake_run)
    resp = client.post("/ask", json={"loan_id": 1, "question": "Привет"}, headers={"X-Request-ID": rid})
    assert resp.headers["x-request-id"] == rid
    with db.connection() as conn:
        rows = conn.execute("DELETE FROM llm_calls WHERE request_id = %s RETURNING agent", (rid,)).fetchall()
    assert rows == [("MortgageAssistant",)]


def test_source_label_is_reduced_to_number():
    from app.schemas.assistant import AssistantAnswer

    answer = AssistantAnswer(intent="policy", answer="нет", confidence=1,
                             sources=["1164 | credit_agreement.pdf | стр. 2", "[1160 | rules.docx]", 7])
    assert answer.sources == [1164, 1160, 7]
