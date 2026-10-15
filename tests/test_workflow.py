import asyncio
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from temporalio.client import WorkflowUpdateFailedError
from temporalio.service import RPCError
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from app.core import db
from app.repositories import jobs
from app.temporal.activities import check_payment_day, set_job_status
from app.temporal.workflows import PaymentDayWorkflow


async def wait_status(handle, status):
    for _ in range(100):
        if await handle.query(PaymentDayWorkflow.status) == status:
            return
        await asyncio.sleep(0.1)
    raise AssertionError(f"процесс не дошел до {status}")


@pytest.mark.parametrize("approve, final", [(True, "approved"), (False, "rejected")])
async def test_payment_day_waits_for_staff(cleanup_jobs, approve, final):
    with db.connection() as conn:
        job_id, _ = jobs.create(conn, uuid4().hex[:12], "payment_day", 2, {"new_day": 20}, None)
    cleanup_jobs.append(job_id)
    async with await WorkflowEnvironment.start_local() as env:
        with ThreadPoolExecutor(2) as pool:
            async with Worker(env.client, task_queue="test", workflows=[PaymentDayWorkflow],
                              activities=[check_payment_day, set_job_status], activity_executor=pool):
                handle = await env.client.start_workflow(
                    PaymentDayWorkflow.run, args=[job_id, 2, 20], id=job_id, task_queue="test"
                )
                await wait_status(handle, "awaiting_staff")
                assert await handle.execute_update(PaymentDayWorkflow.decide, approve) == final
                assert await handle.result() == final
                with pytest.raises((WorkflowUpdateFailedError, RPCError)):
                    await handle.execute_update(PaymentDayWorkflow.decide, approve)
    with db.connection() as conn:
        assert jobs.get(conn, job_id)["status"] == final
