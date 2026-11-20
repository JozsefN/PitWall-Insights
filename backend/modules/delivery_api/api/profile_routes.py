from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from modules.delivery_api.api.auth_dependencies import require_current_user
from modules.identity_auth.domain.models import User
from modules.account_profile.application.schemas import ProfileUpdate
from modules.account_profile.infrastructure.db_models import AccountProfileRecord
from modules.storage.infrastructure.db import get_db
from modules.billing.application.service import membership
from modules.billing.infrastructure.db_models import BillingAccountRecord

router = APIRouter(prefix="/api/profile", tags=["profile"])


@router.get("")
def profile(user: User = Depends(require_current_user), db: Session = Depends(get_db)):
    row = db.get(AccountProfileRecord, user.id)
    billing = membership(db.get(BillingAccountRecord, user.id))
    return {"user_id": user.id, "email": user.email, "role": user.role, "email_verified": user.email_verified,
            **{field: getattr(row, field, None) for field in ("name", "nickname", "phone_number")},
            "subscription": {"plan": billing["plan"].code, "billing_available": billing["checkout_enabled"],
                             "upgrade_status": "test_checkout" if billing["checkout_enabled"] else "unavailable"}}


@router.patch("")
def update_profile(payload: ProfileUpdate, user: User = Depends(require_current_user), db: Session = Depends(get_db)):
    from datetime import datetime, timezone
    row = db.get(AccountProfileRecord, user.id) or AccountProfileRecord(user_id=user.id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    row.updated_at = datetime.now(timezone.utc)
    db.add(row)
    db.commit()
    return profile(user, db)
