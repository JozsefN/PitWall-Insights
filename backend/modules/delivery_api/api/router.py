from fastapi import APIRouter, Depends
from modules.delivery_api.api.dataset_access import enforce_dataset_access

from modules.delivery_api.api.health_routes import router as health_router
from modules.delivery_api.api.auth_routes import router as auth_router
from modules.delivery_api.api.billing_routes import router as billing_router
from modules.delivery_api.api.google_routes import router as google_router
from modules.delivery_api.api.session_routes import router as session_router
from modules.delivery_api.api.import_job_routes import router as import_job_router
from modules.delivery_api.api.telemetry_materialization_routes import router as telemetry_materialization_router
from modules.delivery_api.api.ingestion_routes import router as ingestion_router
from modules.delivery_api.api.normalization_routes import router as normalization_router
from modules.delivery_api.api.feature_metrics_routes import router as feature_metrics_router
from modules.delivery_api.api.feature_analysis_routes import router as feature_analysis_router
from modules.delivery_api.api.strategy_routes import router as strategy_router
from modules.delivery_api.api.decision_engine_routes import router as decision_engine_router
from modules.delivery_api.api.layout_routes import router as layout_router
from modules.delivery_api.api.story_feed_routes import router as story_feed_router
from modules.delivery_api.api.profile_routes import router as profile_router
from modules.delivery_api.api.race_estimation_routes import router as race_estimation_router
from modules.delivery_api.api.session_review_routes import router as session_review_router

api_router = APIRouter(dependencies=[Depends(enforce_dataset_access)])
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(google_router)
api_router.include_router(billing_router)
api_router.include_router(session_router)
api_router.include_router(import_job_router)
api_router.include_router(telemetry_materialization_router)
api_router.include_router(ingestion_router)
api_router.include_router(normalization_router)
api_router.include_router(feature_metrics_router)
api_router.include_router(feature_analysis_router)
api_router.include_router(strategy_router)
api_router.include_router(decision_engine_router)
api_router.include_router(layout_router)
api_router.include_router(story_feed_router)
api_router.include_router(profile_router)
api_router.include_router(race_estimation_router)
api_router.include_router(session_review_router)
