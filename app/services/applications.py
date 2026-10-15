from datetime import date, timedelta

from app.core import db
from app.domain.money import format_rub
from app.domain.schedule import add_months, build_schedule, change_payment_day
from app.repositories import jobs as jobs_repo
from app.services import loans

PAYMENT_DAY = "payment_day"


def check_payment_day(loan_id: int, new_day: int, today: date | None = None) -> dict:
    today = today or date.today()
    loan = loans.get_loan(loan_id)
    if loan is None:
        return {"allowed": False, "reason": "кредит не найден"}
    if new_day == loan.payment_day:
        return {"allowed": False, "reason": f"платеж и так {new_day} числа"}
    if not 1 <= new_day <= 28:
        return {"allowed": False, "reason": "дата платежа – только с 1 по 28 число"}
    with db.connection() as conn:
        last = jobs_repo.last_approved_at(conn, loan_id, PAYMENT_DAY)
    if last and last.date() > today - timedelta(days=365):
        return {"allowed": False, "reason": "дату платежа можно менять не чаще раза в 12 месяцев"}
    rows = build_schedule(loan.principal, loan.rate_bp, loan.term_months)
    paid = [r for r in rows if add_months(loan.issued_on, r.n, loan.payment_day) <= today]
    last_date = add_months(loan.issued_on, paid[-1].n, loan.payment_day) if paid else loan.issued_on
    balance = paid[-1].balance if paid else loan.principal
    change = change_payment_day(balance, loan.rate_bp, last_date, new_day)
    return {
        "allowed": True,
        "new_payment_date": change.new_date.isoformat(),
        "transition_days": change.days,
        "transition_interest": format_rub(change.transition_interest),
    }


def get_job(job_id: str) -> dict | None:
    with db.connection() as conn:
        return jobs_repo.get(conn, job_id)
