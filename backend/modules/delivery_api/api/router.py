from fastapi import APIRouter

from modules.delivery_api.api.health_routes import router as health_router
from modules.delivery_api.api.auth_routes import router as auth_router
from modules.delivery_api.api.session_routes import router as session_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(session_router)