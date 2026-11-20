from fastapi import APIRouter
from modules.storage.infrastructure.db import Database

router = APIRouter()

db = Database()


@router.get("/health")
def root_health() -> dict:
    return {
        "status": "ok",
        "service": "backend",
    }


@router.get("/api/health")
def api_health() -> dict:
    database = db.health()
    return {
        "status": "ok",
        "service": "delivery_api",
        "db": {"status": database["status"], "driver": database["driver"]},
    }
