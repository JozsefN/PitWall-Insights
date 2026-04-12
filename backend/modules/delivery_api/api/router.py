from fastapi import APIRouter

from modules.delivery_api.api.health_routes import router as health_router
from modules.delivery_api.api.auth_routes import router as auth_router
from modules.delivery_api.api.session_routes import router as session_router
from modules.delivery_api.api.ingestion_routes import router as ingestion_router
from modules.delivery_api.api.normalization_routes import router as normalization_router
from modules.delivery_api.api.feature_metrics_routes import router as feature_metrics_router
from modules.delivery_api.api.layout_routes import router as layout_router
from modules.delivery_api.api.story_feed_routes import router as story_feed_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(session_router)
api_router.include_router(ingestion_router)
api_router.include_router(normalization_router)
api_router.include_router(feature_metrics_router)
api_router.include_router(layout_router)
api_router.include_router(story_feed_router)
