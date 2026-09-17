"""Prelaunch sanitation on a separately named disposable MySQL schema."""
import os
import subprocess
import sys

import pytest
from sqlalchemy import event, text
from sqlalchemy.orm import sessionmaker

from app.db.session import build_engine, get_db
from app.main import app
from scripts.sanitize_transactions import TABLES, sanitize
from tests.conftest import SUPER_ADMIN_EMAIL, TEST_PASSWORD, make_admin
from tests.test_sanitize_transactions import populate
from .conftest import BACKEND_ROOT, env_url


def test_mysql_sanitation_is_atomic_preserves_data_and_restores_guard(client):
    url = env_url("MYSQL_SANITATION_URL")
    engine = build_engine(url)
    with engine.connect() as connection:
        schema = connection.execute(text("SELECT DATABASE()")).scalar_one()
        assert schema.endswith("_sanitation"), "Sanitation tests require their own disposable schema"
        assert not connection.execute(text("SHOW TABLES")).first(), "Use a fresh sanitation test schema"
    result = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"],
                            cwd=BACKEND_ROOT, env={**os.environ, "DATABASE_URL": url}, capture_output=True)
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    factory = sessionmaker(engine, autoflush=False)
    original = app.dependency_overrides[get_db]
    def isolated_db():
        with factory() as db:
            yield db
    app.dependency_overrides[get_db] = isolated_db
    try:
        with factory() as db:
            make_admin(db, email=SUPER_ADMIN_EMAIL, role="super_admin")
            login = client.post("/api/v1/auth/login", json={"email": SUPER_ADMIN_EMAIL, "password": TEST_PASSWORD})
            assert login.status_code == 200, login.text
            token = login.json()["access_token"]
            populate(db, client, token)
        before = sanitize(engine)
        assert before["after"] == before["before"] and before["before"]["orders"] == 1
        with pytest.raises(Exception, match="order_activity_immutable"):
            with engine.begin() as connection:
                connection.execute(text("DELETE FROM order_activities"))
        def fail(conn, cursor, statement, parameters, context, executemany):
            if statement.startswith("DELETE FROM orders"):
                raise RuntimeError("injected mid-transaction failure")
        event.listen(engine, "before_cursor_execute", fail)
        try:
            with pytest.raises(RuntimeError, match="injected"):
                sanitize(engine, execute=True, confirmed_test_data=True, writers_stopped=True)
        finally:
            event.remove(engine, "before_cursor_execute", fail)
        rollback = sanitize(engine)
        assert rollback["before"] == before["before"]
        assert rollback["preserved_sha256"] == before["preserved_sha256"]
        report = sanitize(engine, execute=True, confirmed_test_data=True, writers_stopped=True)
        assert all(report["after"][name] == 0 for name in TABLES)
        assert report["preserved_sha256"] == before["preserved_sha256"]
        assert report["after"]["coupon_used_count"] == report["r2_operations"] == 0
        from tests.conftest import auth
        dashboard = client.get("/api/v1/admin/dashboard", headers=auth(token)).json()
        assert dashboard["orders_total"] == dashboard["revenue_total"] == dashboard["monthly_sales"] == 0
        for path in ("orders", "invoices", "audit-logs"):
            assert client.get(f"/api/v1/admin/{path}", headers=auth(token)).json()["total"] == 0
        with engine.connect() as connection:
            assert connection.execute(text("SELECT @tara_sanitize_transactions")).scalar_one() is None
            assert connection.execute(text("SELECT IS_USED_LOCK(CONCAT('tara-prelaunch:', DATABASE()))")).scalar_one() is None
    finally:
        app.dependency_overrides[get_db] = original
        engine.dispose()
