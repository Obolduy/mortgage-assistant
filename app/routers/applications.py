from fastapi import APIRouter, Header, HTTPException
from temporalio.client import WorkflowUpdateFailedError
from temporalio.service import RPCError

from app.schemas.applications import Decision, Job, PaymentDayRequest
from app.services import application_process, applications, loans

router = APIRouter(tags=["applications"])


@router.post("/applications/payment-day", status_code=202, response_model=Job)
async def create_payment_day(body: PaymentDayRequest, idempotency_key: str | None = Header(default=None)):
    if loans.get_loan(body.loan_id) is None:
        raise HTTPException(404, "кредит не найден")
    return await application_process.create_payment_day(body.loan_id, body.new_day, idempotency_key)


@router.post("/applications/{job_id}/decision")
async def decide(job_id: str, body: Decision):
    if applications.get_job(job_id) is None:
        raise HTTPException(404, "заявление не найдено")
    try:
        return {"status": await application_process.decide(job_id, body.approve)}
    except WorkflowUpdateFailedError as exc:
        raise HTTPException(409, str(exc.cause or exc)) from exc
    except RPCError as exc:
        raise HTTPException(409, "решение по заявлению уже принято") from exc


@router.get("/jobs/{job_id}", response_model=Job)
def get_job(job_id: str):
    job = applications.get_job(job_id)
    if job is None:
        raise HTTPException(404, "задача не найдена")
    return job
