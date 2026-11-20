from datetime import datetime, timezone

from sqlalchemy.orm import Session

from modules.billing.domain.plans import ANALYST, FREE, PLANS, EntitlementError, Plan
from modules.billing.infrastructure.db_models import BillingAccountRecord


def effective_plan(account: BillingAccountRecord | None) -> Plan:
    if account and account.status == "active" and account.paid_until:
        if account.paid_until > datetime.now(timezone.utc):
            return PLANS.get(account.plan_code, FREE)
    return FREE


def user_plan(db: Session, user_id: str) -> Plan:
    return effective_plan(db.get(BillingAccountRecord, user_id))


def require_analyst(db: Session, user_id: str) -> None:
    if user_plan(db, user_id).level < ANALYST.level:
        raise EntitlementError("This analysis requires Analyst or Pro.")
