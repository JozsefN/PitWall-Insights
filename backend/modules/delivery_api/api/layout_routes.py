from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from modules.dashboard_layouts.application.service import DashboardLayoutService
from modules.dashboard_layouts.domain.models import (
    LayoutCreateRequest,
    LayoutRecord,
    LayoutUpdateRequest,
)
from modules.dashboard_layouts.infrastructure.repository import DashboardLayoutRepository
from modules.delivery_api.api.auth_dependencies import require_current_user
from modules.identity_auth.domain.models import User
from modules.storage.infrastructure.db import get_db

router = APIRouter(prefix="/api/layouts", tags=["layouts"])


def get_layout_service(db: Session = Depends(get_db)) -> DashboardLayoutService:
    repository = DashboardLayoutRepository(db)
    return DashboardLayoutService(repository=repository)


@router.get("", response_model=list[LayoutRecord])
def list_layouts(
    current_user: User = Depends(require_current_user),
    service: DashboardLayoutService = Depends(get_layout_service),
) -> list[LayoutRecord]:
    return service.list_layouts(current_user.id)


@router.get("/{layout_id}", response_model=LayoutRecord)
def get_layout(
    layout_id: str,
    current_user: User = Depends(require_current_user),
    service: DashboardLayoutService = Depends(get_layout_service),
) -> LayoutRecord:
    record = service.get_layout(current_user.id, layout_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Layout not found")
    return record


@router.post("", response_model=LayoutRecord, status_code=status.HTTP_201_CREATED)
def create_layout(
    request: LayoutCreateRequest,
    current_user: User = Depends(require_current_user),
    service: DashboardLayoutService = Depends(get_layout_service),
) -> LayoutRecord:
    try:
        return service.create_layout(current_user.id, request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/{layout_id}", response_model=LayoutRecord)
def update_layout(
    layout_id: str,
    request: LayoutUpdateRequest,
    current_user: User = Depends(require_current_user),
    service: DashboardLayoutService = Depends(get_layout_service),
) -> LayoutRecord:
    try:
        record = service.update_layout(current_user.id, layout_id, request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if record is None:
        raise HTTPException(status_code=404, detail="Layout not found")

    return record


@router.delete("/{layout_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_layout(
    layout_id: str,
    current_user: User = Depends(require_current_user),
    service: DashboardLayoutService = Depends(get_layout_service),
) -> None:
    deleted = service.delete_layout(current_user.id, layout_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Layout not found")
