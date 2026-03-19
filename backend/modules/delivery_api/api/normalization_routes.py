from fastapi import APIRouter

from modules.normalization.application.service import NormalizationService

router = APIRouter(prefix="/api/normalization", tags=["normalization"])

service = NormalizationService()


@router.get("/health")
def normalization_health() -> dict:
    return {
        "module": "normalization",
        "status": "ok",
        "details": service.get_status().model_dump(),
    }