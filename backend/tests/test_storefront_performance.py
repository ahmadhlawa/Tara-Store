from io import BytesIO

from PIL import Image

from app.models import MediaAsset
from app.models import Category
from app.services.storefront_derivatives import derivative_key_for
from sqlalchemy import event
from app.storage.local import LocalStorageProvider
from tests.conftest import make_product
import pytest


def test_responsive_media_is_small_cached_and_bounded(client, db, media_root, monkeypatch):
    from app.api.v1.endpoints import public_catalog

    storage = LocalStorageProvider(media_root, "/media")
    monkeypatch.setattr(public_catalog, "get_storage", lambda: storage, raising=False)
    output = BytesIO()
    Image.new("RGB", (2400, 1600), "purple").save(output, "PNG")
    original = storage.save(output.getvalue(), content_type="image/png", extension="png")
    db.add(MediaAsset(original_filename="test.png", stored_key=original.key,
                      content_type=original.content_type, size_bytes=original.size_bytes,
                      url=original.url, storage_provider="local"))
    db.commit()
    url = f"/api/v1/storefront-media/{original.key}?width=480"
    response = client.get(url, follow_redirects=False)
    assert response.status_code == 307
    assert "immutable" in response.headers["cache-control"]
    derivative_key = derivative_key_for(original.key, 480)
    assert response.headers["location"] == storage.url_for(derivative_key)
    assert Image.open(BytesIO(storage.read(derivative_key))).size == (480, 320)
    assert len(storage.read(derivative_key)) < original.size_bytes
    monkeypatch.setattr(storage, "read", lambda key: (_ for _ in ()).throw(AssertionError("cache miss")))
    assert client.get(url, follow_redirects=False).headers["location"] == storage.url_for(derivative_key)
    assert client.get(f"/api/v1/storefront-media/{original.key}?width=9999").status_code == 422
    assert client.get("/api/v1/storefront-media/not-registered.png?width=480").status_code == 404


def test_home_showcases_preserve_category_limits_order_and_availability(client, db, category):
    category.show_on_home = True
    for index in range(6):
        make_product(db, slug=f"showcase-{index}", category_id=category.id,
                     show_on_home=True, sort_order=index)
    make_product(db, slug="hidden", category_id=category.id, show_on_home=True, is_active=False)
    make_product(db, slug="sold-out", category_id=category.id, show_on_home=True, stock=0)
    db.commit()
    expected = client.get(f"/api/v1/products?category_id={category.id}&show_on_home=true&page_size=4").json()["items"]
    response = client.get("/api/v1/home-showcases")
    assert response.status_code == 200
    assert response.json()[str(category.id)] == expected
    category.is_active = False
    db.commit()
    assert client.get("/api/v1/home-showcases").json() == {}


def test_camera_mpo_uses_visible_frame_and_preserves_orientation():
    from app.services.media_thumbnails import generate_storefront_image

    output = BytesIO()
    Image.new("RGB", (1200, 800), "red").save(output, "MPO", save_all=True,
                                               append_images=[Image.new("RGB", (1200, 800), "blue")])
    encoded = generate_storefront_image(output.getvalue(), 480)
    image = Image.open(BytesIO(encoded))
    assert image.size == (480, 320)
    assert image.getpixel((0, 0))[0] > 200


def test_animated_artwork_is_not_silently_flattened():
    from app.services.media_thumbnails import generate_storefront_image

    output = BytesIO()
    Image.new("RGB", (100, 100), "red").save(output, "PNG", save_all=True,
                                             append_images=[Image.new("RGB", (100, 100), "blue")])
    with pytest.raises(ValueError, match="Animated"):
        generate_storefront_image(output.getvalue(), 480)


def test_showcase_query_count_does_not_grow_per_category(client, db, category):
    category.show_on_home = True
    make_product(db, slug="first-home", category_id=category.id, show_on_home=True)
    db.commit()
    statements = []

    def record(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    engine = db.get_bind()
    event.listen(engine, "before_cursor_execute", record)
    try:
        assert client.get("/api/v1/home-showcases").status_code == 200
        initial = len(statements)
        for index in range(5):
            row = Category(name=f"Home {index}", slug=f"home-{index}", show_on_home=True)
            db.add(row)
            db.flush()
            make_product(db, slug=f"home-product-{index}", category_id=row.id, show_on_home=True)
        db.commit()
        statements.clear()
        response = client.get("/api/v1/home-showcases")
        assert response.status_code == 200
        assert len(response.json()) == 6
        assert len(statements) == initial
    finally:
        event.remove(engine, "before_cursor_execute", record)
