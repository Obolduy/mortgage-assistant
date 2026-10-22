from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError

with workflow.unsafe.imports_passed_through():
    from app.temporal.activities import (
        check_payment_day,
        embed_document,
        parse_document,
        set_document_status,
        set_job_status,
    )

STEP_TIMEOUT = timedelta(seconds=30)
EMBED_TIMEOUT = timedelta(minutes=10)
RETRY = RetryPolicy(maximum_attempts=3)


@workflow.defn
class PaymentDayWorkflow:
    def __init__(self) -> None:
        self._status = "checking"
        self._approved: bool | None = None

    @workflow.run
    async def run(self, job_id: str, loan_id: int, new_day: int) -> str:
        check = await workflow.execute_activity(
            check_payment_day, args=[loan_id, new_day], start_to_close_timeout=STEP_TIMEOUT, retry_policy=RETRY
        )
        if not check["allowed"]:
            await self._publish(job_id, "rejected", check)
            return self._status
        await self._publish(job_id, "awaiting_staff", check)
        await workflow.wait_condition(lambda: self._approved is not None)
        await self._publish(job_id, "approved" if self._approved else "rejected", None)
        return self._status

    async def _publish(self, job_id: str, status: str, result: dict | None) -> None:
        self._status = status
        await workflow.execute_activity(
            set_job_status, args=[job_id, status, result], start_to_close_timeout=STEP_TIMEOUT, retry_policy=RETRY
        )

    @workflow.update
    def decide(self, approve: bool) -> str:
        self._approved = approve
        return "approved" if approve else "rejected"

    @decide.validator
    def check_decide(self, approve: bool) -> None:
        if self._status != "awaiting_staff" or self._approved is not None:
            raise ValueError(f"заявление в статусе {self._status}, решение не принимается")

    @workflow.query
    def status(self) -> str:
        return self._status


@workflow.defn
class ParseDocumentWorkflow:
    @workflow.run
    async def run(self, doc_id: str) -> str:
        try:
            await self._publish(doc_id, "parsing", None)
            parsed = await workflow.execute_activity(
                parse_document, doc_id, start_to_close_timeout=STEP_TIMEOUT, retry_policy=RETRY
            )
            if parsed["error"]:
                return await self._publish(doc_id, "rejected", parsed["error"])
            await self._publish(doc_id, "embedding", None)
            await workflow.execute_activity(
                embed_document, doc_id, start_to_close_timeout=EMBED_TIMEOUT, retry_policy=RETRY
            )
            return await self._publish(doc_id, "indexed", None)
        except ActivityError as exc:
            return await self._publish(doc_id, "failed", str(exc.cause or exc))

    async def _publish(self, doc_id: str, status: str, error: str | None) -> str:
        await workflow.execute_activity(
            set_document_status, args=[doc_id, status, error], start_to_close_timeout=STEP_TIMEOUT,
            retry_policy=RETRY,
        )
        return status
