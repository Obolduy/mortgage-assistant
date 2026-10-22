import asyncio
import hashlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from app.core import db
from app.core.config import settings
from app.main import app
from app.rag import embedder, reindex
from app.repositories import documents
from app.services import indexing
from app.temporal import activities
from app.temporal.workflows import ParseDocumentWorkflow

DATA = Path(__file__).resolve().parent.parent / "data"


def doc_id(name: str) -> str:
    return "test-" + hashlib.sha256((DATA / name).read_bytes()).hexdigest()[:16]


@pytest.fixture
def clean():
    ids = []

    def drop(targets):
        with db.connection() as conn:
            conn.execute("DELETE FROM documents WHERE id = ANY(%s)", (targets,))

    def track(name: str) -> str:
        ids.append(doc_id(name))
        drop(ids[-1:])
        return ids[-1]

    yield track
    drop(ids)


@pytest.fixture
def fake_embedder(monkeypatch):
    calls = []

    def embed(items):
        calls.append(len(items))
        return [[1.0] + [0.0] * 767 for _ in items]

    monkeypatch.setattr(embedder, "embed_documents", embed)
    return calls


def test_upload_twice_starts_one_process(monkeypatch):
    started = []

    class FakeClient:
        async def start_workflow(self, *args, **kwargs):
            started.append(kwargs["id"])

    async def get_client():
        return FakeClient()

    monkeypatch.setattr(indexing, "get_client", get_client)
    client = TestClient(app)
    files = {"file": ("tariffs.xlsx", f"test {uuid4()}".encode())}
    first = client.post("/documents", files=files)
    second = client.post("/documents", files=files)
    with db.connection() as conn:
        conn.execute("DELETE FROM documents WHERE id = %s", (first.json()["id"],))
    assert first.status_code == second.status_code == 202
    assert first.json()["id"] == second.json()["id"]
    assert started == [f"parse-{first.json()['id']}"]
    assert first.json()["status"] == "uploaded"


def test_empty_and_missing():
    client = TestClient(app)
    assert client.post("/documents", files={"file": ("a.pdf", b"")}).status_code == 400
    assert client.get("/documents/nope").status_code == 404


async def run_parse(names: list[str]) -> list[str]:
    async with await WorkflowEnvironment.start_local() as env:
        with ThreadPoolExecutor(2) as pool:
            async with Worker(
                env.client, task_queue="test", workflows=[ParseDocumentWorkflow], activity_executor=pool,
                activities=[activities.parse_document, activities.embed_document, activities.set_document_status],
            ):
                handles = [
                    await env.client.start_workflow(ParseDocumentWorkflow.run, doc_id(n), id=f"parse-{doc_id(n)}",
                                                    task_queue="test")
                    for n in names
                ]
                return await asyncio.gather(*(h.result() for h in handles))


async def test_parse_workflow_indexes_and_rejects_scan(clean, fake_embedder):
    names = ["credit_agreement.pdf", "income_statement_scan.pdf", "client_application.docx"]
    with db.connection() as conn:
        for name in names:
            documents.create(conn, clean(name), name, (DATA / name).read_bytes())
    assert await run_parse(names) == ["indexed", "rejected", "indexed"]
    with db.connection() as conn:
        contract = documents.get(conn, doc_id("credit_agreement.pdf"))
        scan = documents.get(conn, doc_id("income_statement_scan.pdf"))
        empty = conn.execute(
            "SELECT count(*) FROM chunks WHERE document_id = %s AND embedding IS NULL", (contract["id"],)
        ).fetchone()[0]
    assert contract["chunks_count"] > 3 and empty == 0
    assert "текстового слоя" in scan["error"]


async def test_reindex_is_idempotent(clean, fake_embedder, monkeypatch):
    name = "early_repayment_rules.docx"
    with db.connection() as conn:
        documents.create(conn, clean(name), name, (DATA / name).read_bytes())
    assert await run_parse([name]) == ["indexed"]
    assert reindex.embed_pending(doc_id(name)) == 0
    monkeypatch.setattr(settings, "embed_model", "other-model")
    assert reindex.embed_pending(doc_id(name)) == sum(fake_embedder[1:])
    assert reindex.embed_pending(doc_id(name)) == 0
