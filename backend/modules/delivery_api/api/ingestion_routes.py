from fastapi import APIRouter, Depends

from modules.delivery_api.api.auth_dependencies import require_admin

from modules.ingestion.application.service import IngestionService
from modules.ingestion.infrastructure.provider_registry import build_session_source
from modules.ingestion.domain.capabilities import DATA_CAPABILITIES

router = APIRouter(prefix="/api/ingestion", tags=["ingestion"])

service = IngestionService(source=build_session_source())


@router.get("/capabilities")
def data_capabilities():
    return {"features": DATA_CAPABILITIES, "live_viewer_implemented": False,
            "source": "openf1", "coverage_from": 2023,
            "note": "Availability depends on the selected session. Live streaming, fuel mass, tyre temperatures and precise track edges are unavailable."}


@router.get("/health", dependencies=[Depends(require_admin)])
def ingestion_health() -> dict:
    return {
        "module": "ingestion",
        "status": "ok",
        "details": service.get_status().model_dump(),
    }
