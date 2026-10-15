from uuid import uuid4

from app.core import db
from app.core.config import settings
from app.repositories import jobs as jobs_repo
from app.services.applications import PAYMENT_DAY, get_job
from app.temporal.client import get_client
from app.temporal.workflows import PaymentDayWorkflow


async def create_payment_day(loan_id: int, new_day: int, idempotency_key: str | None) -> dict:
    with db.connection() as conn:
        job_id, created = jobs_repo.create(
            conn, uuid4().hex[:12], PAYMENT_DAY, loan_id, {"new_day": new_day}, idempotency_key
        )
    if created:
        client = await get_client()
        await client.start_workflow(
            PaymentDayWorkflow.run,
            args=[job_id, loan_id, new_day],
            id=job_id,
            task_queue=settings.temporal_task_queue,
        )
    return get_job(job_id)


async def decide(job_id: str, approve: bool) -> str:
    client = await get_client()
    return await client.get_workflow_handle(job_id).execute_update(PaymentDayWorkflow.decide, approve)
