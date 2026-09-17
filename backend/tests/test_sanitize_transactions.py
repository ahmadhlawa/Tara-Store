"""Exercise sanitation against migrated, disposable databases and real services."""
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import event, select, text

from app.core.config import settings
from app.models import (
    Category, Coupon, DeliveryArea, HeroSlide, HomeSection, MediaAsset, Order, OrderActivity,
    PackageItem, ProductImage, ProductOption, ProductOptionValue, ProductOptionValueImage,
    ProductVariant, StaticPage, Translation,
)
from app.services import store_settings
from scripts.sanitize_transactions import HEAD, TABLES, SanitationError, sanitize
from tests.conftest import auth, make_product


@pytest.fixture()
def migrated(session_factory, monkeypatch):
    engine = session_factory.kw["bind"]
    # create_all fixture has no migration/trigger state. Rebuild only its temp file.
    from app.db.base import metadata_with_models
    metadata_with_models().drop_all(engine)
    monkeypatch.setattr(settings, "DATABASE_URL", str(engine.url))
    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    command.upgrade(config, "head")
    return engine


def populate(db, client, token):
    product = make_product(db, track_inventory=False)
    category = Category(name="حقيقي", slug="real", is_active=True)
    db.add(category)
    db.flush()
    variant_product = make_product(db, slug="real-variant", category_id=category.id)
    package = make_product(db, slug="real-package", product_type="package")
    option = ProductOption(product_id=variant_product.id, name="رائحة")
    db.add(option)
    db.flush()
    value = ProductOptionValue(option_id=option.id, value="ورد", presentation_title="ورد حقيقي")
    db.add(value)
    db.flush()
    variant = ProductVariant(product_id=variant_product.id, title="ورد", option_values=[value])
    db.add(variant)
    db.flush()
    db.add_all([
        MediaAsset(original_filename="real.png", stored_key="tara/real-uuid.png",
                   url="https://media.example.com/tara/real-uuid.png", content_type="image/png",
                   size_bytes=123, storage_provider="r2"),
        ProductImage(product_id=product.id, url="https://media.example.com/tara/real-uuid.png"),
        StaticPage(title="حقيقي", slug="real", content="محتوى حقيقي"),
        HeroSlide(title="حقيقي", image_url="https://media.example.com/tara/real-uuid.png"),
        Coupon(code="TEST", discount_type="fixed", discount_value=1, used_count=3),
        ProductOptionValueImage(option_value_id=value.id, url="https://media.example.com/tara/real-uuid.png"),
        PackageItem(package_product_id=package.id, included_product_id=variant_product.id, included_variant_id=variant.id),
        DeliveryArea(name="حقيقي", delivery_fee=5),
        HomeSection(section_key="real", title="حقيقي"),
    ])
    store_settings.get_or_create_settings(db)
    db.commit()
    # Keep an actual stored English translation, not only pending jobs.
    translation = db.scalars(select(Translation).where(
        Translation.entity_type == "products", Translation.entity_id == product.id,
        Translation.field == "name"
    )).one()
    translation.status = "ready"
    translation.translated_text = "Real product"
    db.commit()
    result = client.post("/api/v1/orders", json={
        "client_reference": "sanitation-test", "customer_name": "Test Customer",
        "customer_phone": "0591234567", "address": "Test address only",
        "items": [{"product_id": product.id, "quantity": 1}], "coupon_code": "TEST",
    })
    assert result.status_code == 201, result.text
    db.rollback()  # Refresh MySQL's repeatable-read snapshot after the API writer commits.
    order = db.scalars(select(Order)).one()
    response = client.post(f"/api/v1/admin/orders/{order.id}/complete",
                           headers=auth(token), json={"payment_method": "cash_on_delivery"})
    assert response.status_code == 200, response.text
    db.rollback()  # Release this reader before the sanitizer uses its own transaction.
    return product.id


def test_dry_run_changes_nothing(migrated, db, client, super_token):
    populate(db, client, super_token)
    report = sanitize(migrated)
    assert report["mode"] == "dry-run"
    assert report["before"] == report["after"]
    assert report["before"]["orders"] == report["before"]["invoices"] == 1
    assert report["before"]["order_activities"] > 0
    assert all(report["projected_after"][name] == 0 for name in TABLES)
    assert sanitize(migrated)["preserved_sha256"] == report["preserved_sha256"]


def test_execution_preserves_real_data_and_actual_api_totals(migrated, db, client, super_token):
    product_id = populate(db, client, super_token)
    report = sanitize(migrated, execute=True, confirmed_test_data=True, writers_stopped=True)
    assert all(report["after"][name] == 0 for name in TABLES)
    assert report["after"]["coupon_used_count"] == report["r2_operations"] == 0
    for name in report["preserved_sha256"]:
        assert report["before"][name] == report["after"][name]
    for path in ("orders", "invoices", "audit-logs"):
        response = client.get(f"/api/v1/admin/{path}", headers=auth(super_token))
        assert response.status_code == 200, response.text
        assert response.json()["total"] == 0 and response.json()["items"] == []
    response = client.get("/api/v1/admin/dashboard", headers=auth(super_token))
    assert response.status_code == 200, response.text
    dashboard = response.json()
    for key in ("orders_total", "revenue_total", "monthly_sales", "previous_month_sales",
                "period_sales_total", "period_orders_total", "recent_orders_total", "average_order_value"):
        assert dashboard[key] == 0
    assert dashboard["products_total"] == 3
    detail = client.get("/api/v1/products/test-product?locale=en")
    assert detail.status_code == 200 and detail.json()["name"] == "Real product"
    db.expire_all()
    assert db.get(MediaAsset, 1).stored_key == "tara/real-uuid.png"
    assert db.get(StaticPage, 1).content == "محتوى حقيقي"
    assert db.get(Coupon, 1).code == "TEST" and db.get(Coupon, 1).used_count == 0
    # Invoice business numbering restarts via empty sequences; surrogate IDs need not reset.
    from app.models import InvoiceSequence
    assert list(db.scalars(select(InvoiceSequence))) == []
    # The original immutable trigger was restored.
    db.add(OrderActivity(order_id=999, event_type="impossible"))
    with pytest.raises(Exception):
        db.commit()
    db.rollback()


@pytest.mark.parametrize("flags", [{}, {"confirmed_test_data": True}, {"writers_stopped": True}])
def test_execution_requires_explicit_confirmations(migrated, flags):
    with pytest.raises(SanitationError, match="confirmation"):
        sanitize(migrated, execute=True, **flags)


def test_mid_execution_failure_rolls_back_rows_and_triggers(migrated, db, client, super_token):
    populate(db, client, super_token)
    before = sanitize(migrated)
    def fail(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("DELETE FROM orders"):
            raise RuntimeError("injected failure after invoice deletes")
    event.listen(migrated, "before_cursor_execute", fail)
    try:
        with pytest.raises(RuntimeError, match="injected failure"):
            sanitize(migrated, execute=True, confirmed_test_data=True, writers_stopped=True)
    finally:
        event.remove(migrated, "before_cursor_execute", fail)
    after = sanitize(migrated)
    assert after["before"] == before["before"]
    assert after["preserved_sha256"] == before["preserved_sha256"]


def test_unexpected_fk_schema_fails_before_mutation(migrated):
    with migrated.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE unexpected (id INTEGER PRIMARY KEY, order_id INTEGER REFERENCES orders(id))")
    with pytest.raises(SanitationError, match="Unexpected schema"):
        sanitize(migrated, execute=True, confirmed_test_data=True, writers_stopped=True)


def test_orphans_fail_before_mutation(migrated):
    with migrated.connect() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        connection.exec_driver_sql("INSERT INTO product_images (product_id, url, sort_order, is_primary) VALUES (999, 'real.png', 0, 0)")
        connection.commit()
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
    with pytest.raises(SanitationError, match="Orphaned FK"):
        sanitize(migrated)
