from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from modules.delivery_api.api.auth_dependencies import require_current_user
from modules.storage.infrastructure.db import get_db
from modules.feature_metrics.domain.race_estimation.models import (
    RaceEstimateRequest,
    RaceEstimateResponse,
    MODEL_VERSION,
    EVENT_TYPES,
    ModelAssumptions,
)
from modules.feature_metrics.domain.race_estimation.catalog import (
    DEFINITIONS,
    MODEL_NOTES,
)
from modules.feature_metrics.application.race_estimation_service import (
    RaceEstimationService,
)
from modules.feature_metrics.domain.analysis.models import AnalysisLimitError
from modules.feature_metrics.application.calculation_guard import (
    AnalysisBusyError,
    AnalysisChangedError,
)

router = APIRouter(
    prefix="/api/feature-metrics",
    tags=["race_estimation"],
    dependencies=[Depends(require_current_user)],
)


@router.get("/race-estimates/catalog")
def race_estimates_catalog():
    return {
        "version": MODEL_VERSION,
        "metric_count": len(DEFINITIONS),
        "metrics": list(DEFINITIONS.values()),
        "event_types": EVENT_TYPES,
        "default_assumptions": ModelAssumptions().model_dump(),
        "notes": MODEL_NOTES,
    }


@router.post(
    "/sessions/{session_id}/race-estimates", response_model=RaceEstimateResponse
)
def race_estimates(
    session_id: str, payload: RaceEstimateRequest, db: Session = Depends(get_db)
):
    try:
        return RaceEstimationService(db).compute(session_id, payload)
    except LookupError as error:
        raise HTTPException(404, str(error)) from error
    except AnalysisLimitError as error:
        raise HTTPException(413, str(error)) from error
    except AnalysisBusyError as error:
        raise HTTPException(429, str(error), headers={"Retry-After": "2"}) from error
    except AnalysisChangedError as error:
        raise HTTPException(409, str(error)) from error
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
