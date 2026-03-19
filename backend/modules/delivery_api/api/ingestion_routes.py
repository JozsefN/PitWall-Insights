from fastapi import APIRouter

from modules.ingestion.application.service import IngestionService
from modules.ingestion.infrastructure.source_adapter import IngestionSourceAdapter

router = APIRouter(prefix="/api/ingestion", tags=["ingestion"])

service = IngestionService(source_adapter=IngestionSourceAdapter())


@router.get("/health")
def ingestion_health() -> dict:
    return {
        "module": "ingestion",
        "status": "ok",
        "details": service.get_status().model_dump(),
    }