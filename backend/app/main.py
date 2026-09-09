"""FastAPI application factory."""

from __future__ import annotations

import json
import logging
import os
import re
import time
import uuid
from urllib.parse import quote
from xml.etree import ElementTree

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.enums import StorageProviderName
from app.db.session import get_db
from app.models import Category, Product, StaticPage
from app.services.errors import DomainError

request_logger = logging.getLogger("tara_store.requests")
_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{8,128}$")


def _public_url(base: str, path: str = "") -> str:
    return f"{base}{path}"


def _sitemap_xml(base: str, db: Session) -> bytes:
    root = ElementTree.Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
    paths = ["/", "/shop", "/offers", "/packages", "/molds", "/categories", "/contact"]
    paths.extend(
        f"/category/{quote(slug, safe='')}"
        for slug in db.execute(select(Category.slug).where(Category.is_active.is_(True))).scalars()
    )
    paths.extend(
        f"/product/{quote(slug, safe='')}"
        for slug in db.execute(select(Product.slug).where(Product.is_active.is_(True))).scalars()
    )
    special_pages = {"about", "privacy-policy", "return-policy", "terms", "contact"}
    paths.extend(
        f"/{slug}" if slug in special_pages else f"/page/{quote(slug, safe='')}"
        for slug in db.execute(select(StaticPage.slug).where(StaticPage.is_published.is_(True))).scalars()
    )
    for path in dict.fromkeys(paths):
        url = ElementTree.SubElement(root, "url")
        ElementTree.SubElement(url, "loc").text = _public_url(base, path)
    return ElementTree.tostring(root, encoding="utf-8", xml_declaration=True)


def _error(status_code: int, code: str, message: str, *, headers=None, **extra) -> JSONResponse:
    """One error shape for the whole API: {"error": {"code", "message", ...}}."""
    body: dict[str, object] = {"code": code, "message": message}
    body.update(extra)
    return JSONResponse(status_code=status_code, content={"error": body}, headers=headers)


def create_app(config=settings) -> FastAPI:
    production = config.APP_ENV == "production"
    app = FastAPI(
        title=config.APP_NAME,
        version="0.1.0",
        description="Reusable single-store commerce API.",
        openapi_url=None if production else f"{config.API_V1_PREFIX}/openapi.json",
        docs_url=None if production else f"{config.API_V1_PREFIX}/docs",
        redoc_url=None,
    )
    app.state.config = config

    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.CORS_ORIGINS,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_observability(request: Request, call_next):
        incoming = request.headers.get("x-request-id", "")
        request_id = incoming if _REQUEST_ID.fullmatch(incoming) else uuid.uuid4().hex
        request.state.request_id = request_id
        started = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            request_logger.info(
                json.dumps(
                    {
                        "request_id": request_id,
                        "method": request.method,
                        "path": request.url.path,
                        "status": status_code,
                        "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                    },
                    separators=(",", ":"),
                )
            )

    @app.get("/health", tags=["meta"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready", tags=["meta"])
    def ready(db: Session = Depends(get_db)):
        try:
            db.execute(text("SELECT 1")).scalar_one()
        except Exception:
            return JSONResponse(
                status_code=503,
                content={"status": "not_ready", "database": "unavailable"},
            )
        try:
            if config.STORAGE_PROVIDER == StorageProviderName.LOCAL.value:
                media_root = config.media_root
                if not media_root.is_dir() or not os.access(media_root, os.R_OK | os.W_OK):
                    raise RuntimeError("local media directory is unavailable")
                storage = "local"
            elif config.STORAGE_PROVIDER == StorageProviderName.R2.value:
                required = (
                    config.R2_ENDPOINT_URL,
                    config.R2_ACCESS_KEY_ID,
                    config.R2_SECRET_ACCESS_KEY,
                    config.R2_BUCKET_NAME,
                    config.R2_PUBLIC_BASE_URL,
                )
                if not all(required):
                    raise RuntimeError("R2 storage configuration is incomplete")
                storage = "configured-not-probed"
            else:
                raise RuntimeError("unknown storage provider")
            return {"status": "ready", "database": "ok", "storage": storage}
        except Exception:
            return JSONResponse(
                status_code=503,
                content={"status": "not_ready", "database": "ok", "storage": "unavailable"},
            )

    @app.get("/robots.txt", include_in_schema=False)
    def robots() -> Response:
        base = config.PUBLIC_BASE_URL
        lines = ["User-agent: *", "Disallow: /admin/", "Disallow: /cart", "Disallow: /checkout", "Disallow: /order-success/", "Disallow: /search"]
        if base:
            lines.append(f"Sitemap: {base}/sitemap.xml")
        return Response("\n".join(lines) + "\n", media_type="text/plain")

    @app.get("/sitemap.xml", include_in_schema=False)
    def sitemap(db: Session = Depends(get_db)) -> Response:
        if not config.PUBLIC_BASE_URL:
            return Response(status_code=404)
        return Response(_sitemap_xml(config.PUBLIC_BASE_URL, db), media_type="application/xml")

    app.include_router(api_router, prefix=config.API_V1_PREFIX)

    if config.STORAGE_PROVIDER == StorageProviderName.LOCAL.value:
        media_root = config.media_root
        media_root.mkdir(parents=True, exist_ok=True)
        app.mount(
            config.LOCAL_MEDIA_BASE_URL,
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
            return _error(exc.status_code, detail["code"], detail.get("message", ""), headers=exc.headers)
        return _error(exc.status_code, "http_error", str(detail), headers=exc.headers)

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
