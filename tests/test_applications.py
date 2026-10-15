from datetime import date
from uuid import uuid4

from app.core import db
from app.repositories import jobs
from app.services.applications import PAYMENT_DAY, check_payment_day

TODAY = date(2026, 10, 20)


def test_allowed_with_transition_interest():
    check = check_payment_day(1, 20, today=TODAY)
    assert check["allowed"] is True
    assert check["new_payment_date"] == "2026-10-20"
    assert check["transition_days"] == 5


def test_same_day_rejected():
    assert check_payment_day(1, 15, today=TODAY)["allowed"] is False


def test_day_out_of_range_rejected():
    assert "с 1 по 28" in check_payment_day(1, 30, today=TODAY)["reason"]


def test_once_per_year(cleanup_jobs):
    with db.connection() as conn:
        job_id, _ = jobs.create(conn, uuid4().hex[:12], PAYMENT_DAY, 1, {"new_day": 10}, None)
        cleanup_jobs.append(job_id)
        jobs.set_status(conn, job_id, "approved")
    assert "раза в 12 месяцев" in check_payment_day(1, 20)["reason"]
