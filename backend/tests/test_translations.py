from decimal import Decimal
from datetime import timedelta
import pytest

from sqlalchemy import delete, event, select

from app.db.base import utcnow
from app.models import Category, Coupon, HomeSection, Order, PackageItem, Product, ProductOption, ProductOptionValue, StaticPage, StoreSettings, Translation
from app.services.translations import process_pending, source_hash, stage
from tests.conftest import auth, make_product


class Translator:
    def __init__(self, result="English copy"):
        self.result, self.calls = result, []

    def translate(self, text):
        self.calls.append(text)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def test_inventory_updates_do_not_queue_missing_translations(db):
    product = make_product(db)
    db.execute(delete(Translation))
    db.commit()
    db.info.pop("translation_queued", None)
    product.stock_quantity -= 1
    db.commit()
    assert not list(db.scalars(select(Translation)))
    assert not db.info.get("translation_queued")


def ready(db, entity, field, text):
    row = db.scalar(select(Translation).where(Translation.entity_type == entity.__tablename__,
        Translation.entity_id == entity.id, Translation.field == field))
    row.translated_text, row.status = text, "ready"
    db.commit()
    return row


def test_failed_provider_does_not_block_admin_save(client, db, session_factory, admin_token):
    response = client.post("/api/v1/admin/products", headers=auth(admin_token),
        json={"name": "شمعة", "price": 20, "stock_quantity": 5})
    assert response.status_code == 201
    product = db.get(Product, response.json()["id"])
    translator = Translator(RuntimeError("provider unavailable"))
    attempted, completed = process_pending(session_factory, translator)
    assert attempted and completed == 0
    db.expire_all()
    assert product.name == "شمعة"
    row = db.scalar(select(Translation).where(Translation.field == "name"))
    assert row.status == "failed" and row.retry_at > utcnow()
    assert client.get(f"/api/v1/products/{product.slug}?locale=en").json()["name"] == "شمعة"
    _, completed = process_pending(session_factory, Translator("Candle"), force_retry=True)
    assert completed
    assert client.get(f"/api/v1/products/{product.slug}?locale=en").json()["name"] == "Candle"


def test_stale_work_cannot_overwrite_newer_arabic(db, session_factory):
    product = make_product(db, name="قديم")
    class ChangingTranslator:
        def translate(self, text):
            with session_factory() as writer:
                row = writer.get(type(product), product.id)
                row.name = "جديد"
                writer.commit()
            return "Old"
    process_pending(session_factory, ChangingTranslator())
    db.expire_all()
    row = db.scalar(select(Translation).where(Translation.field == "name"))
    assert row.source_hash == source_hash("جديد") and row.status == "pending"
    assert row.translated_text is None


def test_nested_public_copy_and_admin_source(client, db, admin_token):
    category = Category(name="شموع", slug="candles")
    db.add(category)
    db.commit()
    product = make_product(db, name="شمعة فنية", category_id=category.id)
    option = ProductOption(product_id=product.id, name="الرائحة", drives_presentation=True)
    option.values = [ProductOptionValue(value="ورد", presentation_title="شمعة الورد")]
    db.add(option)
    db.commit()
    value = option.values[0]
    for entity, field, text in [(product, "name", "Art Candle"), (category, "name", "Candles"),
        (option, "name", "Scent"), (value, "value", "Rose"), (value, "presentation_title", "Rose Candle")]:
        ready(db, entity, field, text)
    english = client.get(f"/api/v1/products/{product.slug}?locale=en").json()
    assert english["name"] == "Art Candle" and english["category_name"] == "Candles"
    assert english["options"][0]["name"] == "Scent"
    assert english["options"][0]["values"][0]["presentation_title"] == "Rose Candle"
    assert english["slug"] == product.slug and english["price"] == 100
    assert client.get(f"/api/v1/products/{product.slug}").json()["name"] == "شمعة فنية"
    assert client.get(f"/api/v1/admin/products/{product.id}", headers=auth(admin_token)).json()["name"] == "شمعة فنية"
    assert client.get("/api/v1/categories?locale=en").json()[0]["name"] == "Candles"


def test_public_browsing_never_calls_provider(client, db, monkeypatch):
    product = make_product(db)
    def forbidden(*_):
        raise AssertionError("Public read called LibreTranslate")
    monkeypatch.setattr("app.services.translations.LibreTranslator.translate", forbidden)
    for path in ["products", f"products/{product.slug}", "categories", "store/settings", "home-sections", "delivery-areas"]:
        assert client.get(f"/api/v1/{path}?locale=en").status_code == 200


def test_source_hash_fallback_and_search(client, db):
    category = Category(name="شموع", slug="candles")
    db.add(category)
    db.commit()
    product = make_product(db, name="شمعة", category_id=category.id)
    translation = ready(db, product, "name", "Art Candle")
    ready(db, category, "name", "Candles")
    assert client.get("/api/v1/products?locale=en&q=Art").json()["total"] == 1
    assert client.get("/api/v1/products?locale=en&q=Candles").json()["total"] == 1
    assert client.get("/api/v1/products?locale=ar&q=Art").json()["total"] == 0
    assert client.get("/api/v1/products?locale=ar&q=شمعة").json()["total"] == 1
    product.name = "شمعة جديدة"
    db.commit()
    assert client.get("/api/v1/products?locale=en&q=Art").json()["total"] == 0
    db.refresh(translation)
    translation.status, translation.translated_text, translation.source_hash = "ready", "Old", source_hash("different")
    db.commit()
    assert client.get(f"/api/v1/products/{product.slug}?locale=en").json()["name"] == "شمعة جديدة"


def test_backfill_is_idempotent_and_config_is_allowlisted(db, session_factory):
    section = HomeSection(section_key="text", section_type="custom_text", title="عنوان",
        config={"text": "مرحبا", "url": "/shop", "slug": "arabic", "color": "#ffffff"})
    db.add(section)
    db.commit()
    before = [(row.id, row.source_hash) for row in db.scalars(select(Translation))]
    stage(db.connection(), section)
    db.commit()
    assert [(row.id, row.source_hash) for row in db.scalars(select(Translation))] == before
    assert {row.field for row in db.scalars(select(Translation))} == {"title", "config.text"}
    translator = Translator()
    process_pending(session_factory, translator)
    process_pending(session_factory, translator)
    assert len(translator.calls) == 2


def test_public_translation_lookup_is_batched(client, db):
    for index in range(5):
        product = make_product(db, slug=f"product-{index}")
        ready(db, product, "name", f"Product {index}")
    calls = []
    def count(_connection, _cursor, statement, *_):
        if "FROM translations" in statement:
            calls.append(statement)
    engine = db.get_bind()
    event.listen(engine, "before_cursor_execute", count)
    try:
        assert client.get("/api/v1/products?locale=en").status_code == 200
    finally:
        event.remove(engine, "before_cursor_execute", count)
    assert len(calls) == 1


def test_expired_worker_lease_retries_after_restart(db, session_factory):
    product = make_product(db)
    row = db.scalar(select(Translation).where(Translation.field == "name"))
    row.status, row.retry_at = "processing", utcnow() + timedelta(minutes=1)
    db.commit()
    assert process_pending(session_factory, Translator())[0] == 0
    row.retry_at = utcnow() - timedelta(seconds=1)
    db.commit()
    assert process_pending(session_factory, Translator())[1] == 1


def test_editorial_settings_coupon_and_package_copy(client, db):
    page = StaticPage(title="من نحن", slug="about", lead="مقدمة", content="محتوى", seo_title="عنوان البحث")
    settings = StoreSettings(store_name="Tara", store_tagline="صنع يدوي", address="رام الله",
        phone="0591234567", manual_payment_instructions="حساب 123456")
    section = HomeSection(section_key="welcome", section_type="custom_text", title="مرحبا", config={"text": "نص", "url": "/shop"})
    coupon = Coupon(code="SAVE", description="عرض خاص", discount_type="percentage", discount_value=Decimal("10"))
    component = make_product(db, slug="component", name="شمعة")
    package = make_product(db, slug="package", name="بكج", product_type="package")
    item = PackageItem(package_product_id=package.id, included_product_id=component.id, display_note="هدية")
    db.add_all([page, settings, section, coupon, item])
    db.commit()
    for entity, field, text in [(page, "title", "About"), (page, "lead", "Introduction"), (page, "content", "Content"),
        (settings, "store_tagline", "Handmade"), (settings, "manual_payment_instructions", "Account 123456"),
        (section, "title", "Welcome"), (section, "config.text", "Text"), (coupon, "description", "Special offer"),
        (component, "name", "Candle"), (item, "display_note", "Gift")]:
        ready(db, entity, field, text)
    assert client.get("/api/v1/pages/about?locale=en").json()["content"] == "Content"
    identity = client.get("/api/v1/store/settings?locale=en").json()
    assert identity["store_tagline"] == "Handmade" and identity["phone"] == "0591234567"
    assert identity["manual_payment_instructions"] == "Account 123456"
    config = client.get("/api/v1/home-sections?locale=en").json()[0]["config"]
    assert config == {"text": "Text", "url": "/shop"}
    assert client.post("/api/v1/coupons/validate?locale=en", json={"code": "SAVE", "subtotal": 100}).json()["label"] == "Special offer"
    linked = client.get("/api/v1/products/package?locale=en").json()["package_items"][0]
    assert linked["included_product_name"] == "Candle" and linked["display_note"] == "Gift"
    assert not db.scalar(select(Translation).where(Translation.field.in_(("phone", "config.url", "slug", "code"))))


def test_checkout_localizes_labels_but_keeps_arabic_order_snapshots(client, db, delivery_area):
    product = make_product(db, name="شمعة")
    option = ProductOption(product_id=product.id, name="الرائحة")
    option.values = [ProductOptionValue(value="ورد")]
    db.add(option)
    db.commit()
    value = option.values[0]
    for entity, field, text in [(product, "name", "Candle"), (option, "name", "Scent"),
        (value, "value", "Rose"), (delivery_area, "name", "Ramallah")]:
        ready(db, entity, field, text)
    items = [{"product_id": product.id, "quantity": 1, "selected_option_value_ids": [value.id]}]
    response = client.post("/api/v1/cart/price?locale=en", json={"items": items, "delivery_area_id": delivery_area.id})
    assert response.status_code == 200, response.text
    assert response.json()["lines"][0]["variant_description"] == "Scent: Rose"
    assert response.json()["delivery_area_name"] == "Ramallah"
    response = client.post("/api/v1/orders?locale=en", json={"client_reference": "translation-order-1",
        "customer_name": "سارة أحمد", "customer_phone": "0591234567", "address": "عنوان واضح",
        "delivery_area_id": delivery_area.id, "items": items})
    assert response.status_code == 201, response.text
    created = response.json()
    assert created["items"][0]["product_name"] == "Candle"
    order = db.get(Order, created["id"])
    assert order.items[0].product_name == "شمعة" and order.customer_name == "سارة أحمد"
    assert order.delivery_area_name == "رام الله"
    lookup = client.get(f"/api/v1/orders/{order.order_number}?locale=en", headers={"X-Order-Token": created["public_token"]})
    assert lookup.json()["items"][0]["variant_description"] == "Scent: Rose"


def test_libretranslate_adapter_contract_preserves_numbers_and_paragraphs(monkeypatch):
    import io
    import json
    from types import SimpleNamespace
    from app.services.translations import LibreTranslator
    requests = []
    def respond(request, timeout):
        payload = json.loads(request.data)
        requests.append((request, payload, timeout))
        return io.BytesIO(json.dumps({"translatedText": payload["q"].replace("حساب", "Account")}).encode())
    monkeypatch.setattr("app.services.translations.urlopen", respond)
    adapter = LibreTranslator(SimpleNamespace(LIBRETRANSLATE_URL="http://127.0.0.1:5000/", LIBRETRANSLATE_API_KEY="test-key", TRANSLATION_TIMEOUT_SECONDS=15))
    source = "حساب 123456\n\n" + "حساب " * 1100
    result = adapter.translate(source)
    assert result.startswith("Account 123456\n\n") and "TARANUMBER" not in result
    assert len(requests) > 2
    for request, payload, timeout in requests:
        assert request.full_url == "http://127.0.0.1:5000/translate"
        assert payload["api_key"] == "test-key"
        assert payload["source"] == "ar" and payload["target"] == "en" and payload["format"] == "text"
        assert len(payload["q"]) <= 4000 and timeout == 15




def test_deleting_option_values_removes_stored_copy(db):
    product = make_product(db)
    option = ProductOption(product_id=product.id, name="الرائحة")
    option.values = [ProductOptionValue(value="ورد")]
    db.add(option)
    db.commit()
    value_id = option.values[0].id
    ready(db, option.values[0], "value", "Rose")
    option.values.clear()
    db.commit()
    assert not db.scalar(select(Translation).where(Translation.entity_type == "product_option_values", Translation.entity_id == value_id))


def test_worker_is_woken_after_commit_not_flush(db, session_factory, monkeypatch):
    from threading import Event
    from types import SimpleNamespace
    from app.services.translations import TranslationWorker
    called = Event()
    class NotifyingTranslator:
        def translate(self, text):
            called.set()
            return "Candle"
    monkeypatch.setattr("app.services.translations.LibreTranslator", lambda _: NotifyingTranslator())
    worker = TranslationWorker(session_factory, SimpleNamespace(TRANSLATION_BATCH_SIZE=20, TRANSLATION_POLL_SECONDS=3600))
    worker.thread.start()
    try:
        product = Product(name="شمعة", slug="worker-candle", price=Decimal("10"), stock_quantity=5)
        db.add(product)
        db.flush()
        assert not called.is_set()
        db.commit()
        assert called.wait(3)
    finally:
        worker.close()
    db.expire_all()
    row = db.scalar(select(Translation).where(Translation.field == "name"))
    assert row.status == "ready" and row.translated_text == "Candle"


def test_api_automatically_translates_after_commit_and_retries_failed_source_edit(
        db, session_factory, admin_token, monkeypatch):
    import io
    import json
    import time
    from threading import Event
    from urllib.error import URLError
    from fastapi.testclient import TestClient
    from app.core.config import settings
    from app.db.session import get_db
    from app.main import create_app
    from app.services.translations import LibreTranslator

    started, release = Event(), Event()
    calls = []
    failing = False
    def respond(request, timeout):
        payload = json.loads(request.data)
        calls.append(payload)
        assert payload["source"] == "ar" and payload["target"] == "en"
        assert request.full_url == "http://127.0.0.1:5000/translate"
        with session_factory() as reader:
            assert reader.scalar(select(Product).where(Product.name == payload["q"])) is not None
        started.set()
        assert release.wait(3), "Test did not release the translation service"
        if failing:
            raise URLError("offline")
        return io.BytesIO(json.dumps({"translatedText": "Candle" if payload["q"] == "شمعة" else "New candle"}).encode())
    monkeypatch.setattr("app.services.translations.urlopen", respond)
    monkeypatch.setattr("app.main.SessionLocal", session_factory)
    config = settings.model_copy(update={"TRANSLATION_ENABLED": True,
        "LIBRETRANSLATE_URL": "http://127.0.0.1:5000", "TRANSLATION_POLL_SECONDS": 3600})
    app = create_app(config)
    def test_db():
        with session_factory() as session:
            yield session
    app.dependency_overrides[get_db] = test_db
    def wait_for(status):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            with session_factory() as reader:
                row = reader.scalar(select(Translation).where(Translation.entity_type == "products",
                    Translation.entity_id == product_id, Translation.field == "name"))
                if row and row.status == status:
                    return
            time.sleep(0.01)
        pytest.fail(f"Worker did not reach {status}")
    with TestClient(app) as client:
        try:
            saved = client.post("/api/v1/admin/products", headers=auth(admin_token),
                json={"name": "شمعة", "price": 20, "is_active": True, "stock_quantity": 5})
            assert saved.status_code == 201
            product_id, slug = saved.json()["id"], saved.json()["slug"]
            assert started.wait(3)
            assert client.get(f"/api/v1/products/{slug}?locale=en").json()["name"] == "شمعة"
            assert len(calls) == 1  # Public browsing starts no provider work.
            release.set()
            wait_for("ready")
            assert client.get(f"/api/v1/products/{slug}?locale=en").json()["name"] == "Candle"
            assert client.get(f"/api/v1/admin/products/{product_id}", headers=auth(admin_token)).json()["name"] == "شمعة"
            assert len(calls) == 1
            failing = True
            changed = client.patch(f"/api/v1/admin/products/{product_id}", headers=auth(admin_token), json={"name": "شمعة جديدة"})
            assert changed.status_code == 200
            wait_for("failed")
            assert client.get(f"/api/v1/products/{slug}?locale=en").json()["name"] == "شمعة جديدة"
            assert len(calls) == 2
            failing = False
            assert process_pending(session_factory, LibreTranslator(config), force_retry=True) == (1, 1)
            assert client.get(f"/api/v1/products/{slug}?locale=en").json()["name"] == "New candle"
            assert len(calls) == 3
        finally:
            release.set()


def test_unchanged_stored_english_is_not_requeued(client, db, session_factory, admin_token):
    product = make_product(db, name="شمعة")
    row = ready(db, product, "name", "Existing English")
    before = (row.translated_text, row.source_hash, row.updated_at)
    assert client.patch(f"/api/v1/admin/products/{product.id}", headers=auth(admin_token), json={"name": "شمعة"}).status_code == 200
    translator = Translator()
    process_pending(session_factory, translator)
    db.expire_all()
    assert (row.translated_text, row.source_hash, row.updated_at) == before
    assert translator.calls == []


def test_admin_translation_endpoints_are_removed(client, admin_token):
    assert client.post("/api/v1/admin/translations/preview", headers=auth(admin_token),
        json={"text": "شمعة", "source": "ar", "target": "en"}).status_code == 404
    assert client.get("/api/v1/admin/translations/products/1", headers=auth(admin_token)).status_code == 404
