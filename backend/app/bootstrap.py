from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.config import settings
from modules.delivery_api.api.router import api_router


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)

    @app.exception_handler(RequestValidationError)
    async def validation_error_without_secrets(request, error):
        # Pydantic's default errors include the original input, including passwords.
        return JSONResponse(status_code=422, content={"detail": [
            {key: item[key] for key in ("loc", "msg", "type") if key in item}
            for item in error.errors()
        ]})

    return app
