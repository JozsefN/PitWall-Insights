from fastapi import APIRouter, Depends

from modules.delivery_api.api.auth_dependencies import require_admin

from modules.normalization.application.service import NormalizationService

router = APIRouter(prefix="/api/normalization", tags=["normalization"])

service = NormalizationService()


@router.get("/health", dependencies=[Depends(require_admin)])
def normalization_health() -> dict:
    return {
        "module": "normalization",
        "status": "ok",
        "details": service.get_status().model_dump(),
    }
