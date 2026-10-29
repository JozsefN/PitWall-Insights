from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from modules.delivery_api.api.auth_dependencies import require_current_user
from modules.storage.infrastructure.db import get_db
from modules.feature_metrics.domain.strategy.models import (
    StrategyRequest,
    StrategyResponse,
    StrategyContext,
    STRATEGY_VERSION,
)
from modules.feature_metrics.domain.strategy.catalog import catalog
from modules.feature_metrics.domain.analysis.models import AnalysisLimitError
from modules.feature_metrics.infrastructure.strategy_input import StrategyInputProvider
from modules.feature_metrics.application.calculation_guard import (
    AnalysisBusyError,
    AnalysisChangedError,
)
from modules.decision_engine.application.strategy_service import StrategyService

router = APIRouter(prefix="/api/strategy", tags=["strategy"])


def mapped(call):
    try:
        return call()
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


@router.get("/catalog", dependencies=[Depends(require_current_user)])
def strategy_catalog():
    return {
        "version": STRATEGY_VERSION,
        "metrics": catalog(),
        "probability_policy": "Labelled prior cohort required. No heuristic score is a probability.",
        "plan_scope": "Zero/one/two stops with explicit tyre sets, bounded age curves, remaining laps, pit loss and rule profile.",
    }


@router.post("/sessions/{session_id}/evaluate", response_model=StrategyResponse)
def evaluate(
    session_id: str,
    request: StrategyRequest,
    user=Depends(require_current_user),
    db: Session = Depends(get_db),
):
    return mapped(lambda: StrategyService(db).evaluate(session_id, user.id, request))


@router.post("/sessions/{session_id}/contexts", status_code=201)
def create_context(
    session_id: str,
    context: StrategyContext,
    user=Depends(require_current_user),
    db: Session = Depends(get_db),
):
    record = mapped(
        lambda: StrategyInputProvider(db).save_context(session_id, user.id, context)
    )
    return {
        "context_id": record.id,
        "content_hash": record.content_hash,
        "known_at_ms": record.known_at_ms,
        "created_at": record.created_at,
    }


@router.get("/sessions/{session_id}/contexts/{context_id}")
def get_context(
    session_id: str,
    context_id: str,
    user=Depends(require_current_user),
    db: Session = Depends(get_db),
):
    record, context = mapped(
        lambda: StrategyInputProvider(db).context(context_id, user.id, session_id)
    )
    return {
        "context_id": record.id,
        "content_hash": record.content_hash,
        "context": context,
    }
