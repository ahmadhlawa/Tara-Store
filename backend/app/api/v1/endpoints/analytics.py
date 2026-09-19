from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response, status

from app.api.deps import CurrentAdmin, DbSession
from app.core.config import settings
from app.core.rate_limit import analytics_rate_limit
from app.schemas.analytics import (
    AnalyticsPeriod,
    AnalyticsProductViewIn,
    AnalyticsSummaryOut,
    AnalyticsVisitIn,
)
from app.services.analytics import (
    SESSION_COOKIE,
    VISITOR_COOKIE,
    VISITOR_MAX_AGE,
    TrackingContext,
    analytics_summary,
    record_product_view,
    touch_visit,
)

public_router = APIRouter(tags=["analytics"])
admin_router = APIRouter(prefix="/admin/analytics", tags=["admin-analytics"])


def _set_tracking_cookies(response: Response, context: TrackingContext | None) -> None:
    if context is None:
        return
    secure = settings.APP_ENV == "production"
    response.set_cookie(
        VISITOR_COOKIE,
        context.visitor_token,
        max_age=VISITOR_MAX_AGE,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        SESSION_COOKIE,
        context.session_token,
        max_age=settings.ANALYTICS_SESSION_TIMEOUT_MINUTES * 60,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )


@public_router.post(
    "/analytics/visit",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(analytics_rate_limit)],
)
def visit(payload: AnalyticsVisitIn, request: Request, db: DbSession) -> Response:
    del payload  # path is validated but deliberately not persisted.
    context = touch_visit(db, request)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    _set_tracking_cookies(response, context)
    return response


@public_router.post(
    "/analytics/product-view",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(analytics_rate_limit)],
)
def product_view(payload: AnalyticsProductViewIn, request: Request, db: DbSession) -> Response:
    context = record_product_view(db, request, payload.product_id)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    _set_tracking_cookies(response, context)
    return response


@admin_router.get("/summary", response_model=AnalyticsSummaryOut)
def summary(
    db: DbSession,
    admin: CurrentAdmin,
    period: Annotated[AnalyticsPeriod, Query()] = "today",
):
    del admin
    return analytics_summary(db, period)
