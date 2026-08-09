"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.enums import StorageProviderName
from app.services.errors import DomainError


def _error(status_code: int, code: str, message: str, **extra) -> JSONResponse:
    """One error shape for the whole API: {"error": {"code", "message", ...}}."""
    body: dict[str, object] = {"code": code, "message": message}
    body.update(extra)
    return JSONResponse(status_code=status_code, content={"error": body})


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version="0.1.0",
        description="Reusable single-store commerce API.",
        openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
        docs_url=f"{settings.API_V1_PREFIX}/docs",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["meta"])
    def health() -> dict[str, str]:
        return {"status": "ok", "app": settings.APP_NAME, "environment": settings.APP_ENV}

    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    if settings.STORAGE_PROVIDER == StorageProviderName.LOCAL.value:
        media_root = settings.media_root
        media_root.mkdir(parents=True, exist_ok=True)
        app.mount(
            settings.LOCAL_MEDIA_BASE_URL,
            StaticFiles(directory=media_root),
            name="media",
        )

    @app.exception_handler(DomainError)
    def _domain_error(request: Request, exc: DomainError) -> JSONResponse:
        return _error(exc.status_code, exc.code, exc.message)

    @app.exception_handler(StarletteHTTPException)
    def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        detail = exc.detail
        if isinstance(detail, dict) and "code" in detail:
            return _error(exc.status_code, detail["code"], detail.get("message", ""))
        return _error(exc.status_code, "http_error", str(detail))

    @app.exception_handler(RequestValidationError)
    def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        fields = [
            {
                "field": ".".join(str(part) for part in err.get("loc", [])[1:]),
                "message": err.get("msg", "invalid value"),
            }
            for err in exc.errors()
        ]
        return _error(422, "validation_error", "البيانات المرسلة غير صالحة.", fields=fields)

    return app


app = create_app()
