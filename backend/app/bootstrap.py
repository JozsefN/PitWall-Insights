from urllib.parse import urlsplit

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.config import settings
from modules.delivery_api.api.router import api_router
from modules.billing.domain.plans import EntitlementError


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
    )

    web = urlsplit(settings.web_app_url)
    origins = [f"{web.scheme}://{web.netloc}"]
    if web.hostname in {"localhost", "127.0.0.1"}:
        origins.extend(f"http://{host}:{port}" for host in ("localhost", "127.0.0.1") for port in (5173, 4173))
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)

    @app.exception_handler(EntitlementError)
    async def subscription_required(request, error):
        return JSONResponse(status_code=403, content={"detail": str(error)}, headers={"Cache-Control": "no-store"})

    @app.exception_handler(RequestValidationError)
    async def validation_error_without_secrets(request, error):
        # Pydantic's default errors include the original input, including passwords.
        return JSONResponse(status_code=422, content={"detail": [
            {key: item[key] for key in ("loc", "msg", "type") if key in item}
            for item in error.errors()
        ]})

    return app
