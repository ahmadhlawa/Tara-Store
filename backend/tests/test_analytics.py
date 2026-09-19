from __future__ import annotations

from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, BrokenBarrierError

from sqlalchemy import func, select
from starlette.requests import Request

from app.core.config import settings
from app.models import AnalyticsProductView, AnalyticsSession
from app.services.analytics import normalize_location, period_bounds, prune_analytics, touch_visit, record_product_view
from tests.conftest import auth, make_product


def post_visit(client, path="/ar/", headers=None):
    return client.post("/api/v1/analytics/visit", json={"path": path}, headers=headers or {})


def post_product(client, product_id, headers=None):
    return client.post(
        "/api/v1/analytics/product-view",
        json={"product_id": product_id},
        headers=headers or {},
    )


def _parallel_requests(session_factory, visitor, session, operation):
    cookie = f"tara_visitor={visitor}; tara_session={session}".encode()
    request = Request({"type": "http", "headers": [(b"cookie", cookie)]})

    def run():
        with session_factory() as db:
            return operation(db, request)

    with ThreadPoolExecutor(max_workers=2) as pool:
        return list(pool.map(lambda _: run(), range(2)))


def test_simultaneous_tabs_reuse_one_new_session(client, db, session_factory, monkeypatch):
    assert post_visit(client).status_code == 204
    session = db.scalar(select(AnalyticsSession))
    session.last_activity_at -= timedelta(minutes=31)
    db.commit()
    import app.services.analytics as analytics
    original = analytics.normalize_location
    barrier = Barrier(2)

    def synchronized_location(*args):
        try:
            barrier.wait(timeout=0.75)
        except BrokenBarrierError:
            pass
        return original(*args)

    monkeypatch.setattr(analytics, "normalize_location", synchronized_location)
    _parallel_requests(session_factory, client.cookies["tara_visitor"], client.cookies["tara_session"], touch_visit)
    db.expire_all()
    assert db.scalar(select(func.count(AnalyticsSession.id))) == 2


def test_simultaneous_product_requests_dedupe_one_view(client, db, session_factory, monkeypatch):
    product = make_product(db, slug="simultaneous-view")
    assert post_visit(client).status_code == 204
    barrier = Barrier(2)
    original = AnalyticsProductView.__init__

    def synchronized_view(self, *args, **kwargs):
        try:
            barrier.wait(timeout=0.75)
        except BrokenBarrierError:
            pass
        original(self, *args, **kwargs)

    monkeypatch.setattr(AnalyticsProductView, "__init__", synchronized_view)
    _parallel_requests(session_factory, client.cookies["tara_visitor"], client.cookies["tara_session"],
                       lambda session, request: record_product_view(session, request, product.id))
    db.expire_all()
    assert db.scalar(select(func.count(AnalyticsProductView.id))) == 1


def test_server_sets_http_only_visitor_and_session_cookies_and_reuses_session(client, db):
    first = post_visit(client)
    assert first.status_code == 204
    assert "tara_visitor=" in first.headers.get("set-cookie", "")
    assert "HttpOnly" in first.headers.get("set-cookie", "")
    assert "tara_visitor" in client.cookies
    assert "tara_session" in client.cookies

    assert post_visit(client, "/ar/shop").status_code == 204
    db.expire_all()
    assert db.scalar(select(func.count(AnalyticsSession.id))) == 1


def test_after_30_minutes_inactivity_next_activity_creates_a_new_session(client, db):
    assert post_visit(client).status_code == 204
    session = db.scalar(select(AnalyticsSession))
    session.last_activity_at -= timedelta(minutes=31)
    db.commit()

    assert post_visit(client, "/ar/categories").status_code == 204
    db.expire_all()
    assert db.scalar(select(func.count(AnalyticsSession.id))) == 2


def test_product_views_dedupe_for_30_seconds_only_inside_current_session(client, db):
    product = make_product(db, slug="analytics-product", name="شمعة تحليل")
    assert post_product(client, product.id).status_code == 204
    assert post_product(client, product.id).status_code == 204
    db.expire_all()
    assert db.scalar(select(func.count(AnalyticsProductView.id))) == 1

    view = db.scalar(select(AnalyticsProductView))
    view.viewed_at -= timedelta(seconds=31)
    db.commit()
    assert post_product(client, product.id).status_code == 204
    db.expire_all()
    assert db.scalar(select(func.count(AnalyticsProductView.id))) == 2

    session = db.scalar(select(AnalyticsSession).order_by(AnalyticsSession.id.desc()))
    session.last_activity_at -= timedelta(minutes=31)
    db.commit()
    assert post_product(client, product.id).status_code == 204
    db.expire_all()
    assert db.scalar(select(func.count(AnalyticsSession.id))) == 2
    assert db.scalar(select(func.count(AnalyticsProductView.id))) == 3


def test_admin_summary_is_authenticated_and_counts_sessions_unique_visitors_and_actual_product_views(client, db, admin_token):
    assert client.get("/api/v1/admin/analytics/summary?period=today").status_code == 401
    product = make_product(db, slug="analytics-summary", name="منتج إحصائي")
    assert post_visit(client).status_code == 204
    assert post_product(client, product.id).status_code == 204
    view = db.scalar(select(AnalyticsProductView))
    view.viewed_at -= timedelta(seconds=31)
    db.commit()
    assert post_product(client, product.id).status_code == 204

    response = client.get(
        "/api/v1/admin/analytics/summary",
        params={"period": "today"},
        headers=auth(admin_token),
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["sessions"] == 1
    assert payload["unique_visitors"] == 1
    assert payload["top_products"][0]["views"] == 2


def test_locations_keep_known_jerusalem_area_places_before_collapsing_other_il_locations():
    assert normalize_location("IL", "Jerusalem") == "القدس"
    assert normalize_location("PS", "Anata") == "عناتا"
    assert normalize_location("PS", "Al Eizariya") == "العيزرية"
    assert normalize_location("PS", "Hizma") == "حزما"
    assert normalize_location("PS", "Az Za'ayyem") == "الزعيم"
    assert normalize_location("IL", "Nazareth") == "الداخل"
    assert normalize_location(None, None) == "غير محدد"


def test_unrecognized_cloudflare_city_uses_unknown_location():
    assert normalize_location("PS", "Unrecognized Village") == "غير محدد"


def test_cloudflare_location_headers_require_explicit_trust_and_nginx_secret(client, admin_token, monkeypatch):
    monkeypatch.setattr(settings, "ANALYTICS_TRUST_CLOUDFLARE_HEADERS", True)
    monkeypatch.setattr(settings, "ANALYTICS_PROXY_TOKEN", "x" * 40)
    headers = {
        "CF-IPCountry": "IL",
        "CF-IPCity": "Jerusalem",
        "CF-Region": "Jerusalem",
        "X-Tara-Analytics-Proxy": "x" * 40,
    }
    assert post_visit(client, headers=headers).status_code == 204
    payload = client.get(
        "/api/v1/admin/analytics/summary?period=today",
        headers=auth(admin_token),
    ).json()
    assert payload["top_locations"] == [{"name": "القدس", "sessions": 1}]


def test_cloudflare_headers_are_ignored_when_origin_trust_is_not_enabled(client, admin_token, monkeypatch):
    monkeypatch.setattr(settings, "ANALYTICS_TRUST_CLOUDFLARE_HEADERS", False)
    monkeypatch.setattr(settings, "ANALYTICS_PROXY_TOKEN", "x" * 40)
    headers = {
        "CF-IPCountry": "IL",
        "CF-IPCity": "Jerusalem",
        "X-Tara-Analytics-Proxy": "x" * 40,
    }
    assert post_visit(client, headers=headers).status_code == 204
    payload = client.get(
        "/api/v1/admin/analytics/summary?period=today",
        headers=auth(admin_token),
    ).json()
    assert payload["top_locations"] == [{"name": "غير محدد", "sessions": 1}]


def test_known_bots_are_ignored(client, db):
    response = post_visit(client, headers={"User-Agent": "Googlebot/2.1"})
    assert response.status_code == 204
    assert db.scalar(select(func.count(AnalyticsSession.id))) == 0


def test_foreign_origin_is_rejected(client, monkeypatch):
    monkeypatch.setattr(settings, "PUBLIC_BASE_URL", "https://the-taragallery.com")
    response = post_visit(client, headers={"Origin": "https://evil.example"})
    assert response.status_code == 403


def test_period_bounds_use_local_midnights_across_both_hebron_dst_transitions(monkeypatch):
    monkeypatch.setattr(settings, "STORE_TIMEZONE", "Asia/Hebron")
    spring_start, spring_end = period_bounds(
        "today", now=datetime(2026, 3, 28, 12, 0, tzinfo=timezone.utc)
    )
    fall_start, fall_end = period_bounds(
        "today", now=datetime(2026, 10, 24, 12, 0, tzinfo=timezone.utc)
    )
    assert spring_end - spring_start == timedelta(hours=23)
    assert fall_end - fall_start == timedelta(hours=25)


def test_top_locations_return_ten_plus_other(client, db, admin_token):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for index in range(12):
        db.add(AnalyticsSession(
            session_token_hash=f"{index:064x}",
            visitor_hash=f"{index + 100:064x}",
            started_at=now,
            last_activity_at=now,
            location_label=f"مكان {index:02d}",
        ))
    db.commit()
    payload = client.get(
        "/api/v1/admin/analytics/summary?period=today",
        headers=auth(admin_token),
    ).json()
    assert len(payload["top_locations"]) == 11
    assert payload["top_locations"][-1] == {"name": "أخرى", "sessions": 2}


def test_product_snapshot_survives_product_deletion(client, db, admin_token):
    product = make_product(db, slug="history-product", name="اسم تاريخي")
    assert post_product(client, product.id).status_code == 204
    db.delete(product)
    db.commit()
    payload = client.get(
        "/api/v1/admin/analytics/summary?period=today",
        headers=auth(admin_token),
    ).json()
    assert payload["top_products"][0]["name"] == "اسم تاريخي"
    assert payload["top_products"][0]["product_exists"] is False


def test_retention_prunes_only_expired_analytics_in_bounded_batches(client, db):
    product = make_product(db, slug="retention-product")
    assert post_product(client, product.id).status_code == 204
    session = db.scalar(select(AnalyticsSession))
    view = db.scalar(select(AnalyticsProductView))
    old = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=400)
    session.started_at = old
    session.last_activity_at = old
    view.viewed_at = old
    db.commit()
    sessions, views = prune_analytics(db, retention_days=365, batch_size=1)
    assert (sessions, views) == (1, 1)
    assert db.get(type(product), product.id) is not None
