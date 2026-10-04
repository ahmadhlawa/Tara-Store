from __future__ import annotations

from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, BrokenBarrierError

import pytest

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from starlette.requests import Request

from app.core.config import settings
from app.models import AnalyticsEvent, AnalyticsProductView, AnalyticsSession
from app.services.analytics import analytics_summary, normalize_location, period_bounds, prune_analytics, touch_visit, record_product_view
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
    assert isinstance(payload["average_session_duration_seconds"], float)
    assert payload["completed_orders"] == 0
    assert payload["abandoned_carts"] == 0
    assert payload["funnel"] == {
        "product_views": 2, "add_to_cart": 0, "checkout_reached": 0, "order_completed": 0,
    }


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


def _event_model():
    import app.models as models
    model = getattr(models, "AnalyticsEvent", None)
    assert model is not None, "anonymous funnel event model must be registered"
    return model


def _event_recorder():
    import app.services.analytics as analytics
    recorder = getattr(analytics, "record_event", None)
    assert recorder is not None, "internal funnel recorder must exist"
    return recorder


def _cookie_request(client):
    cookie = f"tara_visitor={client.cookies['tara_visitor']}; tara_session={client.cookies['tara_session']}"
    return Request({"type": "http", "headers": [(b"cookie", cookie.encode())]})


@pytest.mark.parametrize("event_type", ["add_to_cart", "checkout_reached"])
def test_public_funnel_event_reuses_and_touches_anonymous_session(client, db, event_type):
    assert post_visit(client).status_code == 204
    session = db.scalar(select(AnalyticsSession))
    visitor_hash = session.visitor_hash
    previous_activity = session.last_activity_at - timedelta(minutes=1)
    session.last_activity_at = previous_activity
    db.commit()
    response = client.post("/api/v1/analytics/event", json={"event_type": event_type})
    assert response.status_code == 204, response.text
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=lax" in response.headers["set-cookie"]
    assert "tara_visitor=" in response.headers["set-cookie"]
    assert "tara_session=" in response.headers["set-cookie"]
    Event = _event_model()
    db.expire_all()
    event = db.scalar(select(Event))
    assert event.session_id == session.id
    assert event.event_type == event_type
    assert event.occurred_at > previous_activity
    assert session.last_activity_at > previous_activity
    assert session.visitor_hash == visitor_hash
    assert db.scalar(select(func.count(AnalyticsSession.id))) == 1
    assert db.scalar(select(func.count(AnalyticsProductView.id))) == 0


@pytest.mark.parametrize("event_type", ["order_completed", "product_view", "unsupported"])
def test_public_funnel_endpoint_rejects_server_completion_and_unknown_types(client, db, event_type):
    response = client.post("/api/v1/analytics/event", json={"event_type": event_type})
    assert response.status_code == 422
    assert db.scalar(select(func.count(AnalyticsSession.id))) == 0


def test_public_funnel_payload_cannot_supply_private_context_or_customer_data(client, db):
    response = client.post("/api/v1/analytics/event", json={
        "event_type": "add_to_cart", "session_id": 123, "dedupe_key": "a" * 64,
        "occurred_at": "2026-01-01", "customer_name": "Private", "email": "private@example.com",
        "phone": "0591234567", "address": "Private address", "ip": "192.0.2.1",
        "cart": [{"product_id": 1}], "order_id": 123,
    })
    assert response.status_code == 422
    assert db.scalar(select(func.count(AnalyticsSession.id))) == 0
    assert client.post("/api/v1/analytics/event", json={"event_type": "add_to_cart"}).status_code == 204
    Event = _event_model()
    assert set(Event.__table__.columns.keys()) == {
        "id", "session_id", "event_type", "occurred_at", "dedupe_key"
    }
    assert {fk.target_fullname for fk in Event.__table__.foreign_keys} == {"analytics_sessions.id"}


@pytest.mark.parametrize("headers,status_code", [
    ({"Origin": "https://evil.example"}, 403),
    ({"Referer": "https://evil.example/shop"}, 403),
    ({"User-Agent": "Googlebot/2.1"}, 204),
])
def test_public_funnel_events_keep_origin_and_bot_protection(client, db, monkeypatch, headers, status_code):
    monkeypatch.setattr(settings, "PUBLIC_BASE_URL", "https://the-taragallery.com")
    response = client.post("/api/v1/analytics/event", json={"event_type": "add_to_cart"}, headers=headers)
    assert response.status_code == status_code
    assert "set-cookie" not in response.headers
    assert db.scalar(select(func.count(AnalyticsSession.id))) == 0
    assert db.scalar(select(func.count(_event_model().id))) == 0


@pytest.mark.parametrize("proxy_token,location", [("x" * 40, "\u0627\u0644\u0642\u062f\u0633"), ("wrong", "\u063a\u064a\u0631 \u0645\u062d\u062f\u062f")])
def test_public_funnel_events_reuse_trusted_proxy_location(client, db, monkeypatch, proxy_token, location):
    monkeypatch.setattr(settings, "ANALYTICS_TRUST_CLOUDFLARE_HEADERS", True)
    monkeypatch.setattr(settings, "ANALYTICS_PROXY_TOKEN", "x" * 40)
    response = client.post("/api/v1/analytics/event", json={"event_type": "add_to_cart"}, headers={
        "CF-IPCountry": "IL", "CF-IPCity": "Jerusalem", "CF-Region": "Jerusalem",
        "X-Tara-Analytics-Proxy": proxy_token, "CF-Connecting-IP": "192.0.2.1",
    })
    assert response.status_code == 204
    assert db.scalar(select(AnalyticsSession)).location_label == location


def test_public_funnel_event_shares_existing_analytics_rate_limit(client, db, monkeypatch):
    from collections import defaultdict, deque
    from app.core.rate_limit import analytics_rate_limit
    monkeypatch.setattr(analytics_rate_limit, "_hits", defaultdict(deque))
    monkeypatch.setattr(settings, "ANALYTICS_RATE_LIMIT", 1)
    assert post_visit(client).status_code == 204
    response = client.post("/api/v1/analytics/event", json={"event_type": "add_to_cart"})
    assert response.status_code == 429
    assert "Retry-After" in response.headers
    assert db.scalar(select(func.count(_event_model().id))) == 0


def test_public_funnel_event_keeps_storefront_maintenance_guard(client, db):
    from app.models import StoreSettings
    db.add(StoreSettings(maintenance_mode=True))
    db.commit()
    response = client.post("/api/v1/analytics/event", json={"event_type": "add_to_cart"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "maintenance_mode"
    assert db.scalar(select(func.count(AnalyticsSession.id))) == 0


def test_checkout_reached_dedupes_per_active_session_even_after_cookie_rotation(client, db):
    payload = {"event_type": "checkout_reached"}
    assert client.post("/api/v1/analytics/event", json=payload).status_code == 204
    Event = _event_model()
    session = db.scalar(select(AnalyticsSession))
    original_token = client.cookies["tara_session"]
    original_event = db.scalar(select(Event))
    original_time = original_event.occurred_at
    session.last_activity_at -= timedelta(minutes=1)
    db.commit()
    assert client.post("/api/v1/analytics/event", json=payload).status_code == 204
    client.cookies.delete("tara_session")
    assert client.post("/api/v1/analytics/event", json=payload).status_code == 204
    assert client.cookies["tara_session"] != original_token
    db.expire_all()
    assert db.scalar(select(func.count(Event.id))) == 1
    assert original_event.occurred_at == original_time
    assert session.last_activity_at > original_time
    session.last_activity_at -= timedelta(minutes=31)
    db.commit()
    assert client.post("/api/v1/analytics/event", json=payload).status_code == 204
    assert db.scalar(select(func.count(AnalyticsSession.id))) == 2
    events = db.scalars(select(Event).order_by(Event.id)).all()
    assert len(events) == 2
    assert events[0].dedupe_key != events[1].dedupe_key


@pytest.mark.parametrize("event_type,want_count", [("checkout_reached", 1), ("add_to_cart", 2)])
def test_simultaneous_funnel_requests_use_existing_visitor_lock(client, db, session_factory, event_type, want_count):
    recorder = _event_recorder()
    assert post_visit(client).status_code == 204
    _parallel_requests(session_factory, client.cookies["tara_visitor"], client.cookies["tara_session"],
                       lambda session, request: recorder(session, request, event_type))
    Event = _event_model()
    assert db.scalar(select(func.count(AnalyticsSession.id))) == 1
    events = db.scalars(select(Event)).all()
    assert len(events) == want_count
    assert all(event.event_type == event_type for event in events)
    if event_type == "add_to_cart":
        assert all(event.dedupe_key is None for event in events)


def test_internal_order_completion_key_dedupes_across_anonymous_visitors(session_factory, db):
    recorder = _event_recorder()
    Event = _event_model()
    # Two visitor locks cannot serialize one order: the DB uniqueness must do it.
    barrier = Barrier(2)
    def run(visitor):
        request = Request({"type": "http", "headers": [(b"cookie", f"tara_visitor={visitor * 43}".encode())]})
        with session_factory() as session:
            barrier.wait(timeout=5)
            return recorder(session, request, "order_completed", dedupe_key="a" * 64)
    with ThreadPoolExecutor(max_workers=2) as pool:
        contexts = list(pool.map(run, ["a", "b"]))
    assert all(context is not None for context in contexts)
    assert db.scalar(select(func.count(Event.id))) == 1
    db.rollback()
    with session_factory() as session:
        recorder(session, Request({"type": "http", "headers": []}), "order_completed", dedupe_key="b" * 64)
    assert db.scalar(select(func.count(Event.id))) == 2


@pytest.mark.parametrize("event_type,dedupe_key", [
    ("unsupported", None), ("order_completed", None), ("order_completed", "raw-order-id"),
    ("checkout_reached", "a" * 64), ("add_to_cart", "a" * 64),
])
def test_internal_funnel_recorder_rejects_invalid_type_or_dedupe_contract(db, event_type, dedupe_key):
    recorder = _event_recorder()
    with pytest.raises(ValueError):
        recorder(db, Request({"type": "http", "headers": []}), event_type, dedupe_key=dedupe_key)
    assert db.scalar(select(func.count(AnalyticsSession.id))) == 0


def test_funnel_database_rejects_unknown_types_and_duplicate_nonnull_keys(client, db):
    Event = _event_model()
    assert post_visit(client).status_code == 204
    session_id = db.scalar(select(AnalyticsSession.id))
    for event_type in ("add_to_cart", "checkout_reached", "order_completed"):
        db.add(Event(session_id=session_id, event_type=event_type, dedupe_key=None))
    db.commit()
    assert db.scalar(select(func.count(Event.id))) == 3
    db.add(Event(session_id=session_id, event_type="unsupported"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    db.add(Event(session_id=session_id, event_type="checkout_reached", dedupe_key="a" * 64))
    db.commit()
    db.add(Event(session_id=session_id, event_type="checkout_reached", dedupe_key="a" * 64))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_funnel_recorder_rolls_back_session_if_event_table_is_unavailable(client, db, session_factory):
    recorder = _event_recorder()
    Event = _event_model()
    assert post_visit(client).status_code == 204
    old = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=1)
    session = db.scalar(select(AnalyticsSession))
    session.last_activity_at = old
    db.commit()
    Event.__table__.drop(session_factory.kw["bind"])
    from sqlalchemy.exc import OperationalError
    with pytest.raises(OperationalError):
        recorder(db, _cookie_request(client), "add_to_cart")
    db.expire_all()
    assert session.last_activity_at == old
    assert db.scalar(select(func.count(AnalyticsSession.id))) == 1


def test_retention_cascades_events_only_from_expired_sessions(client, db):
    Event = _event_model()
    product = make_product(db, slug="funnel-retention")
    assert post_product(client, product.id).status_code == 204
    assert client.post("/api/v1/analytics/event", json={"event_type": "add_to_cart"}).status_code == 204
    old_session = db.scalar(select(AnalyticsSession))
    old_session.last_activity_at -= timedelta(days=400)
    db.commit()
    assert client.post("/api/v1/analytics/event", json={"event_type": "add_to_cart"}).status_code == 204
    assert prune_analytics(db, retention_days=365, batch_size=1) == (1, 0)
    db.expire_all()
    assert db.scalar(select(func.count(Event.id))) == 1
    assert db.scalar(select(func.count(AnalyticsSession.id))) == 1
    assert db.scalar(select(func.count(AnalyticsProductView.id))) == 0
    assert db.get(type(product), product.id) is not None


def _summary_session(db, started, last_activity, *, visitor="visitor"):
    from uuid import uuid4

    session = AnalyticsSession(
        session_token_hash=uuid4().hex, visitor_hash=visitor,
        started_at=started, last_activity_at=last_activity, location_label="summary-test",
    )
    db.add(session)
    db.flush()
    return session


@pytest.mark.parametrize("durations,expected", [
    ([], 0.0), ([0, 0], 0.0), ([-2, -0.5], 0.0), ([1.25, 2.75, -1, 0], 1.0),
])
def test_summary_duration_clamps_each_session_and_keeps_fractional_seconds(db, monkeypatch, durations, expected):
    monkeypatch.setattr(settings, "STORE_TIMEZONE", "Asia/Hebron")
    started = datetime(2026, 9, 10, 10)
    for seconds in durations:
        _summary_session(db, started, started + timedelta(seconds=seconds))
    db.commit()
    result = analytics_summary(db, "30d", now=datetime(2026, 10, 4, 12))
    assert result["sessions"] == len(durations)
    assert result["average_session_duration_seconds"] == pytest.approx(expected, abs=0.001)
    assert isinstance(result["average_session_duration_seconds"], float)
    # Historical sessions contribute duration without invented funnel events.
    assert result["funnel"] == {
        "product_views": 0, "add_to_cart": 0, "checkout_reached": 0, "order_completed": 0,
    }
    assert result["completed_orders"] == 0
    assert result["abandoned_carts"] == 0


@pytest.mark.parametrize("period,start", [
    ("today", datetime(2026, 10, 3, 21)),
    ("7d", datetime(2026, 9, 27, 21)),
    ("30d", datetime(2026, 9, 4, 21)),
])
def test_summary_bounds_use_session_start_but_funnel_uses_event_time(db, monkeypatch, period, start):
    monkeypatch.setattr(settings, "STORE_TIMEZONE", "Asia/Hebron")
    end = datetime(2026, 10, 4, 21)
    moment = timedelta(microseconds=1)
    older = _summary_session(db, start - moment, start + timedelta(seconds=100))
    _summary_session(db, start, start + timedelta(seconds=10))
    _summary_session(db, end - moment, end - moment + timedelta(seconds=30))
    _summary_session(db, end, end + timedelta(seconds=1000))
    # Session start is outside the range; its in-range events still count.
    for occurred in (start - moment, start, end - moment, end):
        db.add(AnalyticsProductView(
            session_id=older.id, product_id=999999,
            product_slug_snapshot="deleted-summary", product_name_snapshot="Deleted summary",
            viewed_at=occurred,
        ))
        for event_type in ("add_to_cart", "checkout_reached", "order_completed"):
            db.add(AnalyticsEvent(session_id=older.id, event_type=event_type, occurred_at=occurred))
    db.commit()
    result = analytics_summary(db, period, now=datetime(2026, 10, 4, 12, tzinfo=timezone.utc))
    assert (result["range_start"], result["range_end"]) == (start, end)
    assert result["sessions"] == 2
    assert result["unique_visitors"] == 1
    assert result["average_session_duration_seconds"] == pytest.approx(20.0, abs=0.001)
    assert result["funnel"] == {
        "product_views": 2, "add_to_cart": 2, "checkout_reached": 2, "order_completed": 2,
    }
    assert result["completed_orders"] == 2
    assert result["abandoned_carts"] == 0
    assert result["top_locations"] == [{"name": "summary-test", "sessions": 2}]
    assert result["top_products"] == [{
        "product_id": 999999, "name": "Deleted summary", "slug": "deleted-summary",
        "views": 2, "product_exists": False,
    }]


@pytest.mark.parametrize("case,expected", [
    ("inactive", 1), ("active-session", 0), ("cutoff-session", 0), ("future-session", 0),
    ("active-event", 0), ("cutoff-event", 0), ("future-event", 0),
    ("completed-before-period", 0), ("completed-after-period", 0),
    ("add-outside-period", 0), ("no-add", 0),
])
def test_abandoned_carts_count_distinct_inactive_sessions_without_any_completion(db, monkeypatch, case, expected):
    monkeypatch.setattr(settings, "STORE_TIMEZONE", "Asia/Hebron")
    monkeypatch.setattr(settings, "ANALYTICS_SESSION_TIMEOUT_MINUTES", 45)
    now = datetime(2026, 10, 4, 12)
    start = datetime(2026, 10, 3, 21)
    cutoff = datetime(2026, 10, 4, 11, 15)
    old_activity = cutoff - timedelta(microseconds=1)
    last_activity = {
        "active-session": cutoff + timedelta(seconds=1), "cutoff-session": cutoff,
        "future-session": now + timedelta(days=1),
    }.get(case, old_activity)
    session = _summary_session(db, start - timedelta(days=1), last_activity)
    if case != "no-add":
        add_time = start - timedelta(seconds=1) if case == "add-outside-period" else old_activity
        # Repeated adds are event counts but only one potential abandoned cart.
        db.add_all([AnalyticsEvent(session_id=session.id, event_type="add_to_cart", occurred_at=add_time)
                    for _ in range(2)])
    event_time = {
        "active-event": cutoff + timedelta(seconds=1), "cutoff-event": cutoff,
        "future-event": now + timedelta(days=1),
    }.get(case)
    if event_time is not None:
        db.add(AnalyticsEvent(session_id=session.id, event_type="checkout_reached", occurred_at=event_time))
    completion = {
        "completed-before-period": start - timedelta(seconds=1),
        "completed-after-period": datetime(2026, 10, 4, 21),
    }.get(case)
    if completion is not None:
        db.add(AnalyticsEvent(session_id=session.id, event_type="order_completed", occurred_at=completion))
    db.commit()
    result = analytics_summary(db, "today", now=now.replace(tzinfo=timezone.utc))
    assert result["abandoned_carts"] == expected
    assert result["sessions"] == 0
    assert result["completed_orders"] == 0
    assert result["funnel"]["add_to_cart"] == (0 if case in {"no-add", "add-outside-period"} else 2)
