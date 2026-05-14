from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import ValidationError
from sqlalchemy.orm import Session

from modules.decision_engine.application.service import DecisionEngineService
from modules.decision_engine.domain.models import DecisionSignalId
from modules.decision_engine.domain.registry import SUPPORTED_SIGNAL_IDS
from modules.feature_metrics.application.service import FeatureMetricsService
from modules.feature_metrics.domain.models import AnalysisScope, MetricId
from modules.feature_metrics.domain.registry import SUPPORTED_METRIC_IDS
from modules.feature_metrics.infrastructure.input_provider import FeatureMetricInputProvider
from modules.storage.infrastructure.db import get_db

router = APIRouter(prefix="/api/feature-metrics", tags=["feature_metrics"])


@router.get("/health")
def feature_metrics_health() -> dict:
    service = FeatureMetricsService()
    return {
        "module": "feature_metrics",
        "status": "ok",
        "details": service.get_status().model_dump(),
    }


@router.get("/sessions/{session_id}/driver-scores")
def get_session_driver_scores(
    session_id: str,
    metric_ids: str | None = Query(
        default=None,
        description="Comma-separated metric ids. Defaults to all available v1 metrics.",
    ),
    entry_ids: str | None = Query(
        default=None,
        description="Optional comma-separated session entry ids.",
    ),
    analysis_scope: AnalysisScope = Query(
        default="field",
        description="field computes against every entry; explicit_entries computes against entry_ids.",
    ),
    recent_laps: int = Query(default=5, ge=1, le=50),
    lap_from: int | None = Query(default=None, ge=1),
    lap_to: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
) -> dict:
    service = FeatureMetricsService(input_provider=FeatureMetricInputProvider(db))
    try:
        response = service.compute_driver_scores(
            session_id,
            metric_ids=_parse_metric_ids(metric_ids),
            analysis_scope=analysis_scope,
            entry_ids=_parse_csv(entry_ids),
            recent_laps=recent_laps,
            lap_from=lap_from,
            lap_to=lap_to,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if response is None:
        raise HTTPException(status_code=404, detail="Session not found")

    return response.model_dump()


@router.get("/sessions/{session_id}/insights")
def get_session_metric_insights(
    session_id: str,
    signal_ids: str | None = Query(
        default=None,
        description="Comma-separated metric insight ids. Defaults to all current feature-metric insights.",
    ),
    entry_ids: str | None = Query(
        default=None,
        description="Optional comma-separated session entry ids.",
    ),
    analysis_scope: AnalysisScope = Query(
        default="field",
        description="field computes against every entry; explicit_entries computes against entry_ids.",
    ),
    recent_laps: int = Query(default=5, ge=1, le=50),
    lap_from: int | None = Query(default=None, ge=1),
    lap_to: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
) -> dict:
    service = DecisionEngineService(input_provider=FeatureMetricInputProvider(db))
    try:
        response = service.get_signals(
            session_id,
            signal_ids=_parse_signal_ids(signal_ids),
            analysis_scope=analysis_scope,
            entry_ids=_parse_csv(entry_ids),
            recent_laps=recent_laps,
            lap_from=lap_from,
            lap_to=lap_to,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if response is None:
        raise HTTPException(status_code=404, detail="Session not found")

    return response.model_dump()


def _parse_csv(value: str | None) -> list[str] | None:
    if value is None:
        return None

    items = [item.strip() for item in value.split(",") if item.strip()]
    return items or None


def _parse_metric_ids(value: str | None) -> list[MetricId] | None:
    items = _parse_csv(value)
    if items is None:
        return None

    supported = set(SUPPORTED_METRIC_IDS)
    invalid = [item for item in items if item not in supported]
    if invalid:
        raise ValueError(
            f"Unsupported metric id(s): {', '.join(invalid)}. Supported metrics: {', '.join(SUPPORTED_METRIC_IDS)}"
        )

    return items


def _parse_signal_ids(value: str | None) -> list[DecisionSignalId] | None:
    items = _parse_csv(value)
    if items is None:
        return None

    supported = set(SUPPORTED_SIGNAL_IDS)
    invalid = [item for item in items if item not in supported]
    if invalid:
        raise ValueError(
            f"Unsupported metric insight id(s): {', '.join(invalid)}. Supported insights: {', '.join(SUPPORTED_SIGNAL_IDS)}"
        )

    return items
