from fastapi import APIRouter

from modules.ingestion.application.service import IngestionService
from modules.ingestion.infrastructure.provider_registry import build_session_source

router = APIRouter(prefix="/api/ingestion", tags=["ingestion"])

service = IngestionService(source=build_session_source())


@router.get("/health")
def ingestion_health() -> dict:
    return {
        "module": "ingestion",
        "status": "ok",
        "details": service.get_status().model_dump(),
    }
