from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from modules.dashboard_layouts.infrastructure.db_models import UserDashboardLayoutRecord


class DashboardLayoutRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_for_user(self, user_id: str) -> list[UserDashboardLayoutRecord]:
        return (
            self.db.query(UserDashboardLayoutRecord)
            .filter(UserDashboardLayoutRecord.owner_user_id == user_id)
            .order_by(UserDashboardLayoutRecord.updated_at.desc())
            .all()
        )

    def get_for_user(self, user_id: str, layout_id: str) -> UserDashboardLayoutRecord | None:
        return (
            self.db.query(UserDashboardLayoutRecord)
            .filter(
                UserDashboardLayoutRecord.owner_user_id == user_id,
                UserDashboardLayoutRecord.id == layout_id,
            )
            .first()
        )

    def create(
        self,
        *,
        owner_user_id: str,
        name: str,
        description: str | None,
        audience: str,
        schema_version: int,
        config_json: dict,
    ) -> UserDashboardLayoutRecord:
        now = datetime.now(timezone.utc)
        record = UserDashboardLayoutRecord(
            owner_user_id=owner_user_id,
            name=name,
            description=description,
            audience=audience,
            schema_version=schema_version,
            config_json=config_json,
            created_at=now,
            updated_at=now,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def update(
        self,
        record: UserDashboardLayoutRecord,
        *,
        name: str | None = None,
        description: str | None = None,
        audience: str | None = None,
        schema_version: int | None = None,
        config_json: dict | None = None,
    ) -> UserDashboardLayoutRecord:
        if name is not None:
            record.name = name
        if description is not None:
            record.description = description
        if audience is not None:
            record.audience = audience
        if schema_version is not None:
            record.schema_version = schema_version
        if config_json is not None:
            record.config_json = config_json

        record.updated_at = datetime.now(timezone.utc)
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def delete(self, record: UserDashboardLayoutRecord) -> None:
        self.db.delete(record)
        self.db.commit()
