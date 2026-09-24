from __future__ import annotations

from dataclasses import dataclass
from contextlib import contextmanager
from datetime import datetime, time, timedelta, timezone
from hashlib import sha256
import hmac
import re
import secrets
from urllib.parse import unquote, urlsplit
from zoneinfo import ZoneInfo

from fastapi import HTTPException, Request, status
from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.base import utcnow
from app.models.analytics import AnalyticsProductView, AnalyticsSession
from app.models.catalog import Product
from app.schemas.analytics import AnalyticsPeriod

VISITOR_COOKIE = "tara_visitor"
SESSION_COOKIE = "tara_session"
VISITOR_MAX_AGE = 180 * 24 * 60 * 60
_UNKNOWN_LOCATION = "غير محدد"
_INSIDE_LABEL = "الداخل"
_BOT_MARKERS = (
    "bot", "crawler", "spider", "slurp", "facebookexternalhit", "bingpreview",
    "headlesschrome", "python-requests", "curl/", "wget/",
)
_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{32,128}$")
_CITY_ALIASES = {
    "jerusalem": "القدس",
    "east jerusalem": "القدس",
    "anata": "عناتا",
    "'anata": "عناتا",
    "anatot": "عناتا",
    "al eizariya": "العيزرية",
    "al-eizariya": "العيزرية",
    "al 'eizariya": "العيزرية",
    "bethany": "العيزرية",
    "hizma": "حزما",
    "hizme": "حزما",
    "az zaayyem": "الزعيم",
    "az za'ayyem": "الزعيم",
    "az-za'ayyem": "الزعيم",
    "al zaim": "الزعيم",
    "al za'im": "الزعيم",
    "zaim": "الزعيم",
    "nablus": "نابلس",
    "ramallah": "رام الله",
    "al bireh": "البيرة",
    "al-bireh": "البيرة",
    "hebron": "الخليل",
    "bethlehem": "بيت لحم",
    "jenin": "جنين",
    "tulkarm": "طولكرم",
    "qalqilya": "قلقيلية",
    "jericho": "أريحا",
    "gaza": "غزة",
    "rafah": "رفح",
    "khan yunis": "خان يونس",
}


@dataclass(slots=True)
class TrackingContext:
    session: AnalyticsSession
    visitor_token: str
    session_token: str


@contextmanager
def _tracking_lock(db: Session, visitor_hash: str):
    """Serialize one visitor's session and view writes across workers."""
    dialect = db.get_bind().dialect.name
    if dialect == "sqlite":
        # SQLite has no row locks. Claim its writer lock before the first read.
        db.connection().exec_driver_sql("BEGIN IMMEDIATE")
        yield db
    elif dialect == "mysql":
        # Named locks belong to the connection. Hold one connection through the
        # tracking transaction so a busy pool cannot deadlock on a second checkout.
        # The storefront-open dependency may already have used this request's
        # Session for a read. End that read transaction before checking out the
        # connection used for both the advisory lock and tracking writes.
        db.rollback()
        name = f"tara-analytics:{visitor_hash[:40]}"
        with db.get_bind().connect() as lock_connection:
            acquired = lock_connection.execute(
                text("SELECT GET_LOCK(:name, 5)"), {"name": name}
            ).scalar_one()
            if acquired != 1:
                raise HTTPException(status_code=503, detail="Analytics temporarily unavailable")
            lock_connection.commit()  # End the GET_LOCK statement transaction.
            try:
                # The lock and writes use one pooled connection. The Session owns
                # its transaction and commits before the named lock is released.
                with Session(bind=lock_connection, autoflush=False, expire_on_commit=False) as locked_db:
                    yield locked_db
            finally:
                lock_connection.execute(text("SELECT RELEASE_LOCK(:name)"), {"name": name})
    else:
        raise RuntimeError(f"Unsupported analytics database dialect: {dialect}")


def _utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _token_hash(scope: str, raw: str) -> str:
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        f"tara-analytics:{scope}:{raw}".encode("utf-8"),
        sha256,
    ).hexdigest()


def _valid_token(value: str | None) -> str | None:
    value = (value or "").strip()
    return value if _TOKEN_RE.fullmatch(value) else None


def _new_token() -> str:
    return secrets.token_urlsafe(32)


def _normalize_cloudflare_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = unquote(value).strip()
    try:
        return normalized.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return normalized


def _city_key(value: str) -> str:
    value = (_normalize_cloudflare_text(value) or "").casefold().replace("’", "'")
    value = re.sub(r"\s+", " ", value)
    return value


def normalize_location(country_code: str | None, city_name: str | None) -> str:
    country = (country_code or "").strip().upper()
    city = _normalize_cloudflare_text(city_name) or ""
    if city:
        explicit = _CITY_ALIASES.get(_city_key(city))
        if explicit:
            return explicit
    if country == "IL":
        return _INSIDE_LABEL
    if city:
        return city
    return _UNKNOWN_LOCATION


def _same_origin_or_unspecified(request: Request) -> None:
    if not settings.PUBLIC_BASE_URL:
        return
    source = request.headers.get("origin") or request.headers.get("referer")
    if not source:
        return
    expected = urlsplit(settings.PUBLIC_BASE_URL)
    parsed = urlsplit(source)
    if (parsed.scheme.lower(), parsed.netloc.lower()) != (
        expected.scheme.lower(), expected.netloc.lower()
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "analytics_origin_rejected", "message": "Request origin rejected."},
        )


def is_obvious_bot(request: Request) -> bool:
    user_agent = request.headers.get("user-agent", "").casefold()
    return bool(user_agent and any(marker in user_agent for marker in _BOT_MARKERS))


def _trusted_location(request: Request) -> tuple[str | None, str | None, str | None]:
    if not settings.ANALYTICS_TRUST_CLOUDFLARE_HEADERS:
        return None, None, None
    expected = settings.ANALYTICS_PROXY_TOKEN.strip()
    supplied = request.headers.get("x-tara-analytics-proxy", "")
    if not expected or not supplied or not hmac.compare_digest(expected, supplied):
        return None, None, None
    return (
        request.headers.get("cf-ipcountry"),
        _normalize_cloudflare_text(request.headers.get("cf-ipcity")),
        _normalize_cloudflare_text(request.headers.get("cf-region")),
    )


def resolve_session(
    db: Session,
    request: Request,
    *,
    now: datetime | None = None,
    visitor_token: str | None = None,
) -> TrackingContext | None:
    _same_origin_or_unspecified(request)
    if is_obvious_bot(request):
        return None

    current = _utc_naive(now or utcnow())
    visitor_token = visitor_token or _valid_token(request.cookies.get(VISITOR_COOKIE)) or _new_token()
    visitor_hash = _token_hash("visitor", visitor_token)
    cutoff = current - timedelta(minutes=settings.ANALYTICS_SESSION_TIMEOUT_MINUTES)

    supplied_session = _valid_token(request.cookies.get(SESSION_COOKIE))
    session = None
    session_token = supplied_session
    if supplied_session:
        session = db.execute(
            select(AnalyticsSession).where(
                AnalyticsSession.session_token_hash == _token_hash("session", supplied_session),
                AnalyticsSession.visitor_hash == visitor_hash,
                AnalyticsSession.last_activity_at > cutoff,
            )
        ).scalar_one_or_none()

    if session is None:
        session = db.execute(
            select(AnalyticsSession)
            .where(
                AnalyticsSession.visitor_hash == visitor_hash,
                AnalyticsSession.last_activity_at > cutoff,
            )
            .order_by(AnalyticsSession.last_activity_at.desc(), AnalyticsSession.id.desc())
            .limit(1)
        ).scalar_one_or_none()
        # A valid active session may outlive/lose its browser session cookie. Rotate
        # the opaque session token and attach the browser back to the same DB row.
        if session is not None:
            session_token = _new_token()
            session.session_token_hash = _token_hash("session", session_token)

    country, city, region = _trusted_location(request)
    location_label = normalize_location(country, city)

    if session is None:
        session_token = _new_token()
        session = AnalyticsSession(
            session_token_hash=_token_hash("session", session_token),
            visitor_hash=visitor_hash,
            started_at=current,
            last_activity_at=current,
            country_code=(country or "").strip().upper() or None,
            raw_city=city or None,
            raw_region=region or None,
            location_label=location_label,
        )
        db.add(session)
        db.flush()
    else:
        session.last_activity_at = current
        if session.location_label == _UNKNOWN_LOCATION and location_label != _UNKNOWN_LOCATION:
            session.country_code = (country or "").strip().upper() or None
            session.raw_city = city or None
            session.raw_region = region or None
            session.location_label = location_label

    assert session_token is not None
    return TrackingContext(session=session, visitor_token=visitor_token, session_token=session_token)


def touch_visit(db: Session, request: Request, *, now: datetime | None = None) -> TrackingContext | None:
    visitor_token = _valid_token(request.cookies.get(VISITOR_COOKIE)) or _new_token()
    with _tracking_lock(db, _token_hash("visitor", visitor_token)) as locked_db:
        try:
            context = resolve_session(locked_db, request, now=now, visitor_token=visitor_token)
            if context is not None:
                locked_db.commit()
            else:
                locked_db.rollback()
            return context
        except Exception:
            locked_db.rollback()
            raise


def record_product_view(
    db: Session,
    request: Request,
    product_id: int,
    *,
    now: datetime | None = None,
) -> TrackingContext | None:
    current = _utc_naive(now or utcnow())
    visitor_token = _valid_token(request.cookies.get(VISITOR_COOKIE)) or _new_token()
    with _tracking_lock(db, _token_hash("visitor", visitor_token)) as locked_db:
        try:
            return _record_product_view_locked(locked_db, request, product_id, current, visitor_token)
        except Exception:
            locked_db.rollback()
            raise


def _record_product_view_locked(db: Session, request: Request, product_id: int,
                                current: datetime, visitor_token: str) -> TrackingContext | None:
    context = resolve_session(db, request, now=current, visitor_token=visitor_token)
    if context is None:
        db.rollback()
        return None

    product = db.execute(
        select(Product).where(Product.id == product_id, Product.is_active.is_(True))
    ).scalar_one_or_none()
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "product_not_found", "message": "المنتج غير موجود."},
        )

    dedupe_cutoff = current - timedelta(seconds=settings.ANALYTICS_PRODUCT_VIEW_DEDUPE_SECONDS)
    duplicate = db.execute(
        select(AnalyticsProductView.id)
        .where(
            AnalyticsProductView.session_id == context.session.id,
            AnalyticsProductView.product_id == product.id,
            AnalyticsProductView.viewed_at > dedupe_cutoff,
        )
        .limit(1)
    ).scalar_one_or_none()
    if duplicate is None:
        db.add(
            AnalyticsProductView(
                session_id=context.session.id,
                product_id=product.id,
                product_slug_snapshot=product.slug,
                product_name_snapshot=product.name,
                viewed_at=current,
            )
        )
    db.commit()
    return context


def period_bounds(period: AnalyticsPeriod, *, now: datetime | None = None) -> tuple[datetime, datetime]:
    current_utc = now or datetime.now(timezone.utc)
    if current_utc.tzinfo is None:
        current_utc = current_utc.replace(tzinfo=timezone.utc)
    else:
        current_utc = current_utc.astimezone(timezone.utc)
    zone = ZoneInfo(settings.STORE_TIMEZONE)
    today = current_utc.astimezone(zone).date()
    days = {"today": 1, "7d": 7, "30d": 30}[period]
    start_date = today - timedelta(days=days - 1)
    end_date = today + timedelta(days=1)
    start_local = datetime.combine(start_date, time.min, tzinfo=zone)
    end_local = datetime.combine(end_date, time.min, tzinfo=zone)
    return (
        start_local.astimezone(timezone.utc).replace(tzinfo=None),
        end_local.astimezone(timezone.utc).replace(tzinfo=None),
    )


def analytics_summary(db: Session, period: AnalyticsPeriod, *, now: datetime | None = None) -> dict:
    start, end = period_bounds(period, now=now)

    session_filter = (
        AnalyticsSession.started_at >= start,
        AnalyticsSession.started_at < end,
    )
    sessions = db.execute(
        select(func.count(AnalyticsSession.id)).where(*session_filter)
    ).scalar_one()
    unique_visitors = db.execute(
        select(func.count(func.distinct(AnalyticsSession.visitor_hash))).where(*session_filter)
    ).scalar_one()

    location_count = func.count(AnalyticsSession.id)
    location_rows = db.execute(
        select(AnalyticsSession.location_label, location_count)
        .where(*session_filter)
        .group_by(AnalyticsSession.location_label)
        .order_by(location_count.desc(), AnalyticsSession.location_label.asc())
    ).all()
    top_locations = [
        {"name": name, "sessions": int(count)} for name, count in location_rows[:10]
    ]
    if len(location_rows) > 10:
        other = sum(int(count) for _, count in location_rows[10:])
        if other:
            top_locations.append({"name": "أخرى", "sessions": other})

    view_count = func.count(AnalyticsProductView.id)
    product_rows = db.execute(
        select(
            AnalyticsProductView.product_id,
            func.coalesce(Product.name, func.max(AnalyticsProductView.product_name_snapshot)),
            func.coalesce(Product.slug, func.max(AnalyticsProductView.product_slug_snapshot)),
            view_count,
            Product.id.is_not(None),
        )
        .outerjoin(Product, Product.id == AnalyticsProductView.product_id)
        .where(
            AnalyticsProductView.viewed_at >= start,
            AnalyticsProductView.viewed_at < end,
        )
        .group_by(AnalyticsProductView.product_id, Product.id, Product.name, Product.slug)
        .order_by(view_count.desc(), AnalyticsProductView.product_id.asc())
        .limit(10)
    ).all()

    return {
        "period": period,
        "range_start": start,
        "range_end": end,
        "location_tracking_configured": bool(
            settings.ANALYTICS_TRUST_CLOUDFLARE_HEADERS
            and settings.ANALYTICS_PROXY_TOKEN.strip()
        ),
        "sessions": int(sessions),
        "unique_visitors": int(unique_visitors),
        "top_locations": top_locations,
        "top_products": [
            {
                "product_id": int(product_id),
                "name": name,
                "slug": slug,
                "views": int(views),
                "product_exists": bool(product_exists),
            }
            for product_id, name, slug, views, product_exists in product_rows
        ],
    }


def retention_counts(db: Session, *, now: datetime | None = None, retention_days: int | None = None) -> tuple[int, int, datetime]:
    current = _utc_naive(now or utcnow())
    days = retention_days or settings.ANALYTICS_RETENTION_DAYS
    cutoff = current - timedelta(days=days)
    views = db.execute(
        select(func.count(AnalyticsProductView.id)).where(AnalyticsProductView.viewed_at < cutoff)
    ).scalar_one()
    sessions = db.execute(
        select(func.count(AnalyticsSession.id)).where(AnalyticsSession.last_activity_at < cutoff)
    ).scalar_one()
    return int(sessions), int(views), cutoff


def prune_analytics(
    db: Session,
    *,
    now: datetime | None = None,
    retention_days: int | None = None,
    batch_size: int = 1000,
) -> tuple[int, int]:
    _, _, cutoff = retention_counts(db, now=now, retention_days=retention_days)
    deleted_views = 0
    deleted_sessions = 0

    while True:
        ids = list(db.scalars(
            select(AnalyticsProductView.id)
            .where(AnalyticsProductView.viewed_at < cutoff)
            .order_by(AnalyticsProductView.id)
            .limit(batch_size)
        ))
        if not ids:
            break
        result = db.execute(delete(AnalyticsProductView).where(AnalyticsProductView.id.in_(ids)))
        deleted_views += int(result.rowcount or len(ids))
        db.commit()

    while True:
        ids = list(db.scalars(
            select(AnalyticsSession.id)
            .where(AnalyticsSession.last_activity_at < cutoff)
            .order_by(AnalyticsSession.id)
            .limit(batch_size)
        ))
        if not ids:
            break
        result = db.execute(delete(AnalyticsSession).where(AnalyticsSession.id.in_(ids)))
        deleted_sessions += int(result.rowcount or len(ids))
        db.commit()

    return deleted_sessions, deleted_views
