from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from modules.delivery_api.api.auth_dependencies import require_current_user
from modules.feature_metrics.application.calculation_guard import AnalysisBusyError
from modules.feature_metrics.application.review_service import ReviewService
from modules.feature_metrics.application.qualifying_lap_service import qualifying_lap_map
from modules.feature_metrics.domain.analysis.models import AnalysisLimitError
from modules.feature_metrics.domain.review.models import (
    ReviewRequest,
    REVIEW_GROUPS,
    REVIEW_VERSION,
)
from modules.feature_metrics.domain.review.catalog import component_catalog
from modules.feature_metrics.infrastructure.timing_tower_input import load_timing_tower
from modules.ingestion.infrastructure.openf1_client import OpenF1AccessError
from modules.session_import.application.radio import recover_openf1_radio
from modules.storage.infrastructure.db import get_db

router = APIRouter(
    prefix="/api/feature-metrics",
    tags=["session_review"],
    dependencies=[Depends(require_current_user)],
)


@router.get("/sessions/{session_id}/timing-tower")
def session_timing_tower(session_id: str, db: Session = Depends(get_db)):
    timeline = load_timing_tower(db, session_id)
    if timeline is None:
        raise HTTPException(404, "Session not found")
    return timeline


@router.get("/sessions/{session_id}/qualifying-lap")
def qualifying_lap(
    session_id: str,
    entry_id: str | None = Query(default=None, max_length=100),
    lap_number: int | None = Query(default=None, ge=1, le=1000),
    minisectors: bool = False,
    db: Session = Depends(get_db),
):
    try:
        return qualifying_lap_map(db, session_id, entry_id, lap_number, minisectors)
    except LookupError as error:
        raise HTTPException(404, str(error)) from error
    except AnalysisLimitError as error:
        raise HTTPException(413, str(error)) from error
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@router.get("/review/catalog")
def review_catalog():
    return {
        "version": REVIEW_VERSION,
        "groups": REVIEW_GROUPS,
        "components": component_catalog(),
        "request_schema": ReviewRequest.model_json_schema(),
    }


@router.post("/sessions/{session_id}/review")
def session_review(
    session_id: str, payload: ReviewRequest, db: Session = Depends(get_db)
):
    try:
        return ReviewService(db).compute(session_id, payload)
    except LookupError as error:
        raise HTTPException(404, str(error)) from error
    except AnalysisBusyError as error:
        raise HTTPException(429, str(error), headers={"Retry-After": "2"}) from error
    except AnalysisLimitError as error:
        raise HTTPException(413, str(error)) from error
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@router.get("/sessions/{session_id}/radio-timeline")
def session_radio_timeline(session_id: str, db: Session = Depends(get_db)):
    return _read_radio_timeline(session_id, db)


def _read_radio_timeline(session_id: str, db: Session):
    try:
        return ReviewService(db).radio_timeline(session_id)
    except LookupError as error:
        raise HTTPException(404, str(error)) from error
    except AnalysisLimitError as error:
        raise HTTPException(413, str(error)) from error


@router.post("/sessions/{session_id}/radio-timeline")
def recover_session_radio(session_id: str, db: Session = Depends(get_db)):
    try:
        recover_openf1_radio(db, session_id)
    except LookupError as error:
        raise HTTPException(404, str(error)) from error
    except OpenF1AccessError as error:
        raise HTTPException(503, str(error)) from error
    return _read_radio_timeline(session_id, db)
