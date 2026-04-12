from __future__ import annotations

from copy import deepcopy
from typing import Any

from modules.dashboard_layouts.domain.models import (
    LayoutCreateRequest,
    LayoutRecord,
    LayoutUpdateRequest,
)
from modules.dashboard_layouts.infrastructure.db_models import UserDashboardLayoutRecord
from modules.dashboard_layouts.infrastructure.repository import DashboardLayoutRepository


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
        config = validate_dashboard_config(request.config)
        record = self.repository.create(
            owner_user_id=user_id,
            name=request.name,
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
        record = self.repository.get_for_user(user_id, layout_id)
        if record is None:
            return None

        config = validate_dashboard_config(request.config) if request.config is not None else None
        updated = self.repository.update(
            record,
            name=request.name,
            description=request.description,
            audience=request.audience,
            schema_version=request.schema_version,
            config_json=config,
        )
        return self._build_record(updated)

    def delete_layout(self, user_id: str, layout_id: str) -> bool:
        record = self.repository.get_for_user(user_id, layout_id)
        if record is None:
            return False

        self.repository.delete(record)
        return True

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


def validate_dashboard_config(config: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(config, dict):
        raise ValueError("Layout config must be an object")

    layout_id = config.get("id")
    if not isinstance(layout_id, str) or not layout_id.strip():
        raise ValueError("Layout config requires a string id")

    sections = config.get("sections")
    if not isinstance(sections, list) or not sections:
        raise ValueError("Layout config requires at least one section")

    for index, section in enumerate(sections):
        _validate_section(section, f"sections[{index}]")

    return deepcopy(config)


def _validate_section(section: Any, path: str) -> None:
    if not isinstance(section, dict):
        raise ValueError(f"{path} must be an object")

    section_id = section.get("id")
    if not isinstance(section_id, str) or not section_id.strip():
        raise ValueError(f"{path}.id must be a non-empty string")

    _validate_layout_node(section.get("layout"), f"{path}.layout")


def _validate_layout_node(node: Any, path: str) -> None:
    if not isinstance(node, dict):
        raise ValueError(f"{path} must be an object")

    node_type = node.get("type")
    if node_type == "widget":
        widget_id = node.get("widgetId")
        if not isinstance(widget_id, str) or not widget_id.strip():
            raise ValueError(f"{path}.widgetId must be a non-empty string")

        options = node.get("options")
        if options is not None and not isinstance(options, dict):
            raise ValueError(f"{path}.options must be an object when provided")
        return

    if node_type == "group":
        direction = node.get("direction")
        if direction not in {"row", "column"}:
            raise ValueError(f"{path}.direction must be 'row' or 'column'")

        children = node.get("children")
        if not isinstance(children, list) or not children:
            raise ValueError(f"{path}.children must be a non-empty array")

        for index, child in enumerate(children):
            _validate_layout_node(child, f"{path}.children[{index}]")
        return

    raise ValueError(f"{path}.type must be 'widget' or 'group'")
