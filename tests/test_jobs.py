from uuid import uuid4

from app.core import db
from app.repositories import jobs


def test_same_key_returns_same_job(cleanup_jobs):
    key = uuid4().hex
    with db.connection() as conn:
        first, created = jobs.create(conn, uuid4().hex[:12], "payment_day", 1, {"new_day": 20}, key)
        second, created_again = jobs.create(conn, uuid4().hex[:12], "payment_day", 1, {"new_day": 20}, key)
    cleanup_jobs.append(first)
    assert (created, created_again) == (True, False)
    assert first == second


def test_status_and_result(cleanup_jobs):
    with db.connection() as conn:
        job_id, _ = jobs.create(conn, uuid4().hex[:12], "payment_day", 1, {"new_day": 20}, None)
        cleanup_jobs.append(job_id)
        jobs.set_status(conn, job_id, "awaiting_staff", {"allowed": True})
        jobs.set_status(conn, job_id, "approved")
        row = jobs.get(conn, job_id)
    assert row["status"] == "approved"
    assert row["result"] == {"allowed": True}
