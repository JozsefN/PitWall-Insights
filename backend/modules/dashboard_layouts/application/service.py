from __future__ import annotations

from copy import deepcopy

from modules.billing.application.entitlements import user_plan
from modules.billing.domain.plans import EntitlementError, Plan
from modules.dashboard_layouts.domain.models import (
    LayoutCreateRequest,
    LayoutRecord,
    LayoutUpdateRequest,
)
from modules.dashboard_layouts.infrastructure.db_models import UserDashboardLayoutRecord
from modules.dashboard_layouts.infrastructure.repository import DashboardLayoutRepository
from modules.dashboard_layouts.domain.validation import WIDGET_POLICIES, validate_dashboard_config


def validate_plan(config: dict, plan: Plan) -> None:
    def widgets(node):
        if node["type"] == "widget":
            yield node["widgetId"]
        else:
            for child in node["children"]:
                yield from widgets(child)

    panel_ids = [item for section in config["sections"] for item in widgets(section["layout"])]
    if len(panel_ids) > plan.panels_per_layout:
        raise EntitlementError(f"{plan.name} allows {plan.panels_per_layout} panels per saved layout.")
    for panel_id in panel_ids:
        policy = WIDGET_POLICIES[panel_id]
        if policy["accessTier"] > plan.level:
            raise EntitlementError(f"{policy['title']} requires Analyst or Pro.")


class DashboardLayoutService:
    def __init__(self, repository: DashboardLayoutRepository) -> None:
        self.repository = repository

    def list_layouts(self, user_id: str) -> list[LayoutRecord]:
        return [self._build_record(record) for record in self.repository.list_for_user(user_id)]

    def get_layout(self, user_id: str, layout_id: str) -> LayoutRecord | None:
        record = self.repository.get_for_user(user_id, layout_id)
        if record is None:
            return None
        return self._build_record(record)

    def create_layout(self, user_id: str, request: LayoutCreateRequest) -> LayoutRecord:
        if not request.name.strip():
            raise ValueError("Layout name cannot be blank")
        config = validate_dashboard_config(request.config, request.audience, request.schema_version)
        self.repository.lock_owner(user_id)
        plan = user_plan(self.repository.db, user_id)
        validate_plan(config, plan)
        if self.repository.count_for_user(user_id) >= plan.saved_layouts:
            raise EntitlementError(f"{plan.name} allows {plan.saved_layouts} saved layouts.")
        record = self.repository.create(
            owner_user_id=user_id,
            name=request.name.strip(),
            description=request.description,
            audience=request.audience,
            schema_version=request.schema_version,
            config_json=config,
        )
        return self._build_record(record)

    def update_layout(
        self,
        user_id: str,
        layout_id: str,
        request: LayoutUpdateRequest,
    ) -> LayoutRecord | None:
        self.repository.lock_owner(user_id)
        record = self.repository.get_for_user(user_id, layout_id)
        if record is None:
            return None

        if request.name is not None and not request.name.strip():
            raise ValueError("Layout name cannot be blank")
        validated = validate_dashboard_config(
            request.config if request.config is not None else record.config_json,
            request.audience or record.audience,
            request.schema_version or record.schema_version,
        )
        validate_plan(validated, user_plan(self.repository.db, user_id))
        config = deepcopy(request.config) if request.config is not None else None
        updated = self.repository.update(
            record,
            name=request.name.strip() if request.name is not None else None,
            description=request.description,
            audience=request.audience,
            schema_version=request.schema_version,
            config_json=config,
            clear_description="description" in request.model_fields_set,
        )
        return self._build_record(updated)

    def delete_layout(self, user_id: str, layout_id: str) -> bool:
        self.repository.lock_owner(user_id)
        record = self.repository.get_for_user(user_id, layout_id)
        if record is None:
            return False

        self.repository.delete(record)
        return True

    def list_favorites(self, user_id: str) -> list[str]:
        return self.repository.list_favorites(user_id)

    def set_favorite(self, user_id: str, layout_key: str, favorite: bool) -> list[str]:
        if layout_key.startswith("user:"):
            if self.repository.get_for_user(user_id, layout_key[5:]) is None:
                raise ValueError("Layout not found")
        elif not layout_key.startswith("builtin:") or not layout_key[8:].strip():
            raise ValueError("Invalid layout reference")
        return self.repository.set_favorite(user_id, layout_key, favorite)

    @staticmethod
    def _build_record(record: UserDashboardLayoutRecord) -> LayoutRecord:
        return LayoutRecord(
            id=record.id,
            name=record.name,
            description=record.description,
            audience=record.audience,
            schemaVersion=record.schema_version,
            config=deepcopy(record.config_json),
            createdAt=record.created_at,
            updatedAt=record.updated_at,
        )
