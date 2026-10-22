import hashlib

from app.core import db
from app.core.config import settings
from app.repositories import documents as documents_repo
from app.temporal.client import get_client
from app.temporal.workflows import ParseDocumentWorkflow


async def upload(filename: str, data: bytes) -> dict:
    doc_id = hashlib.sha256(data).hexdigest()[:16]
    with db.connection() as conn:
        created = documents_repo.create(conn, doc_id, filename, data)
    if created:
        client = await get_client()
        await client.start_workflow(
            ParseDocumentWorkflow.run, doc_id, id=f"parse-{doc_id}", task_queue=settings.temporal_task_queue
        )
    return get(doc_id)


def get(doc_id: str) -> dict | None:
    with db.connection() as conn:
        return documents_repo.get(conn, doc_id)
