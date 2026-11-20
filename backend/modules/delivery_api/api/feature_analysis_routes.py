from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from modules.delivery_api.api.auth_dependencies import require_analyst_user, require_current_user
from modules.storage.infrastructure.db import get_db
from modules.feature_metrics.domain.analysis.catalog import DEFINITIONS
from modules.feature_metrics.domain.analysis.models import (
    ANALYSIS_VERSION,
    AnalysisRequest,
    AnalysisResponse,
    AnalysisLimitError,
    EVENT_KINDS,
)
from modules.feature_metrics.application.analysis_service import (
    SessionAnalysisService,
    AnalysisBusyError,
    AnalysisChangedError,
)
from modules.feature_metrics.application.state_service import SessionStateService

router = APIRouter(
    prefix="/api/feature-metrics",
    tags=["f1_analytics"],
    dependencies=[Depends(require_current_user)],
)


@router.get("/analytics/catalog")
def analytic_catalog():
    return {
        "version": ANALYSIS_VERSION,
        "metric_count": len(DEFINITIONS),
        "event_kinds": list(EVENT_KINDS),
        "metrics": [item.model_dump() for item in DEFINITIONS.values()],
        "limits": {
            "max_entries": 64,
            "max_sampled_records": 1000000,
            "max_events": 5000,
            "max_hours": 12,
        },
        "notes": [
            "Uses materialized database data only; missing inputs are explicitly unavailable.",
            "Position units are supported for FastF1 sessions from 2020 onward.",
        ],
    }


@router.post("/sessions/{session_id}/analytics", response_model=AnalysisResponse, dependencies=[Depends(require_analyst_user)])
def session_analytics(
    session_id: str, request: AnalysisRequest, db: Session = Depends(get_db)
):
    try:
        return SessionAnalysisService(db).compute(session_id, request)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except AnalysisLimitError as exc:
        raise HTTPException(413, str(exc)) from exc
    except AnalysisBusyError as exc:
        raise HTTPException(429, str(exc), headers={"Retry-After": "5"}) from exc
    except AnalysisChangedError as exc:
        raise HTTPException(409, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/sessions/{session_id}/state")
def session_state(
    session_id: str,
    at_ms: int = Query(ge=0),
    entry_ids: str | None = Query(default=None, max_length=5000),
    db: Session = Depends(get_db),
):
    ids = (
        sorted(set(item.strip() for item in entry_ids.split(",") if item.strip()))
        if entry_ids is not None
        else None
    )
    if ids is not None and (not ids or len(ids) > 64):
        raise HTTPException(422, "Select between 1 and 64 entries")
    try:
        return SessionStateService(db).get(session_id, at_ms, ids)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except AnalysisLimitError as exc:
        raise HTTPException(413, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
