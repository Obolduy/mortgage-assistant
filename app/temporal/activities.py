from temporalio import activity

from app.core import db
from app.core.logging import bind, get_logger
from app.parsers.blocks import ParseError
from app.rag.reindex import embed_pending
from app.repositories import documents as documents_repo
from app.repositories import jobs as jobs_repo
from app.services import applications, documents

log = get_logger(__name__)


@activity.defn
def check_payment_day(loan_id: int, new_day: int) -> dict:
    return applications.check_payment_day(loan_id, new_day)


@activity.defn
def set_job_status(job_id: str, status: str, result: dict | None) -> None:
    bind(job_id=job_id)
    log.info("job_status", status=status)
    with db.connection() as conn:
        jobs_repo.set_status(conn, job_id, status, result)


@activity.defn
def parse_document(doc_id: str) -> dict:
    with db.connection() as conn:
        filename, data = documents_repo.content(conn, doc_id)
        try:
            chunks = documents.parse(filename, bytes(data))
        except ParseError as exc:
            return {"chunks": 0, "error": str(exc)}
        documents_repo.replace_chunks(conn, doc_id, chunks)
    return {"chunks": len(chunks), "error": None}


@activity.defn
def embed_document(doc_id: str) -> int:
    return embed_pending(doc_id)


@activity.defn
def set_document_status(doc_id: str, status: str, error: str | None) -> None:
    bind(doc_id=doc_id)
    log.info("document_status", status=status, error=error)
    with db.connection() as conn:
        documents_repo.set_status(conn, doc_id, status, error)
