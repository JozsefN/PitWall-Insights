from fastapi import APIRouter

from modules.feature_metrics.application.service import FeatureMetricsService

router = APIRouter(prefix="/api/feature-metrics", tags=["feature_metrics"])

service = FeatureMetricsService()


@router.get("/health")
def feature_metrics_health() -> dict:
    return {
        "module": "feature_metrics",
        "status": "ok",
        "details": service.get_status().model_dump(),
    }