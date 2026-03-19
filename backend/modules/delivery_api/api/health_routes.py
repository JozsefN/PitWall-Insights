from fastapi import APIRouter
from modules.storage.infrastructure.db import Database

router = APIRouter()

db = Database()
db.connect()


@router.get("/health")
def root_health() -> dict:
    return {
        "status": "ok",
        "service": "backend",
    }


@router.get("/api/health")
def api_health() -> dict:
    return {
        "status": "ok",
        "service": "delivery_api",
        "db": db.health(),
    }