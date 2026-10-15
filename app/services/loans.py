from app.core import db
from app.domain.money import format_rub
from app.domain.schedule import add_months, build_schedule, early_repayment
from app.repositories import loans as repo
from app.schemas.loans import Loan, ScheduleRow


def get_loan(loan_id: int) -> Loan | None:
    with db.connection() as conn:
        row = repo.get_loan(conn, loan_id)
    return Loan(**row) if row else None


def get_schedule(loan_id: int) -> list[ScheduleRow] | None:
    loan = get_loan(loan_id)
    if loan is None:
        return None
    rows = build_schedule(loan.principal, loan.rate_bp, loan.term_months)
    return [
        ScheduleRow(
            n=r.n,
            date=add_months(loan.issued_on, r.n, loan.payment_day),
            payment=r.payment,
            interest=r.interest,
            principal=r.principal,
            balance=r.balance,
        )
        for r in rows
    ]


def loan_terms(loan: Loan) -> dict:
    payment = build_schedule(loan.principal, loan.rate_bp, loan.term_months)[0].payment
    return {
        "principal": format_rub(loan.principal),
        "rate_percent": loan.rate_bp / 100,
        "term_months": loan.term_months,
        "issued_on": loan.issued_on.isoformat(),
        "payment_day": loan.payment_day,
        "monthly_payment": format_rub(payment),
    }


def schedule_slice(loan: Loan, from_month: int, count: int) -> list[dict]:
    rows = build_schedule(loan.principal, loan.rate_bp, loan.term_months)
    return [
        {
            "n": r.n,
            "date": add_months(loan.issued_on, r.n, loan.payment_day).isoformat(),
            "payment": format_rub(r.payment),
            "interest": format_rub(r.interest),
            "principal": format_rub(r.principal),
            "balance_after": format_rub(r.balance),
        }
        for r in rows[from_month - 1 : from_month - 1 + count]
    ]


def simulate_early_repayment(loan: Loan, after_month: int, amount: int, mode: str) -> dict:
    r = early_repayment(loan.principal, loan.rate_bp, loan.term_months, after_month, amount, mode)
    return {
        "mode": mode,
        "new_payment": format_rub(r.payment),
        "months_total": r.months_total,
        "interest_total": format_rub(r.interest_total),
        "saved_on_interest": format_rub(r.saved),
    }
