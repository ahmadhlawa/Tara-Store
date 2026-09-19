"""Exercise visitor serialization on the disposable MySQL CI database."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier, BrokenBarrierError
from uuid import uuid4

from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import sessionmaker
from starlette.requests import Request

import app.services.analytics as analytics
from app.models import AnalyticsProductView, AnalyticsSession
from app.db.session import get_db
from app.main import app
from tests.conftest import make_product


def _run_pair(session_factory, cookies, operation):
    header = f"tara_visitor={cookies['tara_visitor']}; tara_session={cookies['tara_session']}".encode()

    def run(_):
        request = Request({"type": "http", "headers": [(b"cookie", header)]})
        with session_factory() as db:
            return operation(db, request)

    with ThreadPoolExecutor(max_workers=2) as executor:
        return list(executor.map(run, range(2)))


def _barrier_call(barrier, original):
    def wrapped(*args, **kwargs):
        try:
            barrier.wait(timeout=0.75)
        except BrokenBarrierError:
            pass
        return original(*args, **kwargs)
    return wrapped


def test_parallel_tabs_share_new_session_on_mysql(client, db, session_factory, monkeypatch):
    assert client.post("/api/v1/analytics/visit", json={"path": "/"}).status_code == 204
    visitor = db.scalar(select(AnalyticsSession).order_by(AnalyticsSession.id.desc()))
    visitor_hash = visitor.visitor_hash
    visitor.last_activity_at -= timedelta(minutes=31)
    db.commit()
    monkeypatch.setattr(analytics, "normalize_location", _barrier_call(Barrier(2), analytics.normalize_location))
    _run_pair(session_factory, client.cookies, analytics.touch_visit)
    db.expire_all()
    assert db.scalar(select(func.count(AnalyticsSession.id)).where(AnalyticsSession.visitor_hash == visitor_hash)) == 2


def test_parallel_product_views_dedupe_on_mysql(client, db, session_factory, monkeypatch):
    product = make_product(db, slug=f"mysql-analytics-{uuid4().hex[:12]}")
    product_id = product.id
    assert client.post("/api/v1/analytics/visit", json={"path": "/"}).status_code == 204
    original = AnalyticsProductView.__init__
    monkeypatch.setattr(AnalyticsProductView, "__init__", _barrier_call(Barrier(2), original))
    _run_pair(session_factory, client.cookies,
              lambda session, request: analytics.record_product_view(session, request, product_id))
    db.rollback()  # MySQL REPEATABLE READ must release the earlier reader snapshot.
    assert db.scalar(select(func.count(AnalyticsProductView.id)).where(AnalyticsProductView.product_id == product_id)) == 1


def test_tracking_uses_one_pooled_connection_on_mysql(session_factory):
    source = session_factory.kw["bind"]
    engine = create_engine(source.url, pool_size=1, max_overflow=0, pool_timeout=1)
    try:
        factory = sessionmaker(bind=engine, future=True)
        request = Request({"type": "http", "headers": []})
        with factory() as db:
            context = analytics.touch_visit(db, request)
            assert context is not None
        name = f"tara-analytics:{context.session.visitor_hash[:40]}"
        with engine.connect() as connection:
            assert connection.execute(text("SELECT IS_USED_LOCK(:name)"), {"name": name}).scalar_one() is None
    finally:
        engine.dispose()


def test_public_tracking_after_storefront_guard_uses_one_connection(client, session_factory):
    engine = create_engine(session_factory.kw["bind"].url, pool_size=1, max_overflow=0, pool_timeout=1)
    factory = sessionmaker(bind=engine, future=True)
    original = app.dependency_overrides[get_db]

    def isolated_db():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = isolated_db
    try:
        response = client.post("/api/v1/analytics/visit", json={"path": "/"})
        assert response.status_code == 204, response.text
    finally:
        app.dependency_overrides[get_db] = original
        engine.dispose()
