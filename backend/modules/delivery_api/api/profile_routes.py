from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from modules.delivery_api.api.auth_dependencies import require_current_user
from modules.identity_auth.domain.models import User
from modules.account_profile.application.schemas import ProfileUpdate
from modules.account_profile.infrastructure.db_models import AccountProfileRecord
from modules.storage.infrastructure.db import get_db

router = APIRouter(prefix="/api/profile", tags=["profile"])


@router.get("")
def profile(user: User = Depends(require_current_user), db: Session = Depends(get_db)):
    row = db.get(AccountProfileRecord, user.id)
    return {"user_id": user.id, "email": user.email,
            **{field: getattr(row, field, None) for field in ("name", "nickname", "phone_number")},
            "subscription": {"plan": "free", "billing_available": False, "upgrade_status": "coming_later"}}


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
