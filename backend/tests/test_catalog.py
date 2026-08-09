from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.enums import ProductType
from app.models import Category, Product
from tests.conftest import auth, make_product


def test_category_crud(client: TestClient, admin_token: str) -> None:
    created = client.post(
        "/api/v1/admin/categories",
        headers=auth(admin_token),
        json={"name": "قوالب سيليكون", "description": "قوالب", "is_featured": True},
    )
    assert created.status_code == 201, created.text
    category = created.json()
    assert category["slug"]

    updated = client.patch(
        f"/api/v1/admin/categories/{category['id']}",
        headers=auth(admin_token),
        json={"name": "قوالب", "sort_order": 3},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "قوالب"
    assert updated.json()["sort_order"] == 3

    listed = client.get("/api/v1/admin/categories", headers=auth(admin_token))
    assert listed.status_code == 200
    assert listed.json()["total"] == 1

    deleted = client.delete(
        f"/api/v1/admin/categories/{category['id']}", headers=auth(admin_token)
    )
    assert deleted.status_code == 200
    assert client.get("/api/v1/categories").json() == []


def test_category_with_products_cannot_be_deleted(
    client: TestClient, db: Session, admin_token: str, category: Category
) -> None:
    make_product(db, category_id=category.id)
    response = client.delete(
        f"/api/v1/admin/categories/{category.id}", headers=auth(admin_token)
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "category_has_products"


def test_product_crud_and_slug_uniqueness(
    client: TestClient, admin_token: str, category: Category
) -> None:
    payload = {
        "name": "ريزن شفاف",
        "category_id": category.id,
        "price": 120.5,
        "compare_at_price": 150,
        "cost_price": 80,
        "stock_quantity": 12,
        "is_featured": True,
        "specifications": [{"name": "الوزن", "value": "١ كغم"}],
    }
    first = client.post("/api/v1/admin/products", headers=auth(admin_token), json=payload)
    assert first.status_code == 201, first.text
    assert first.json()["slug"] == "ريزن-شفاف"
    assert len(first.json()["specifications"]) == 1

    second = client.post("/api/v1/admin/products", headers=auth(admin_token), json=payload)
    assert second.status_code == 201
    assert second.json()["slug"] != first.json()["slug"]

    product_id = first.json()["id"]
    updated = client.patch(
        f"/api/v1/admin/products/{product_id}",
        headers=auth(admin_token),
        json={"price": 99, "is_active": False},
    )
    assert updated.status_code == 200
    assert updated.json()["price"] == 99
    assert updated.json()["is_active"] is False

    deleted = client.delete(f"/api/v1/admin/products/{product_id}", headers=auth(admin_token))
    assert deleted.status_code == 200
    assert client.get(f"/api/v1/admin/products/{product_id}", headers=auth(admin_token)).status_code == 404


def test_compare_at_price_must_beat_the_selling_price(
    client: TestClient, admin_token: str
) -> None:
    response = client.post(
        "/api/v1/admin/products",
        headers=auth(admin_token),
        json={"name": "منتج", "price": 100, "compare_at_price": 90},
    )
    assert response.status_code == 422


def test_public_listing_hides_inactive_products_and_cost_price(
    client: TestClient, db: Session, category: Category
) -> None:
    make_product(db, slug="visible", name="منتج ظاهر", category_id=category.id, cost_price=50)
    make_product(db, slug="hidden", name="منتج مخفي", is_active=False, category_id=category.id)

    listed = client.get("/api/v1/products")
    assert listed.status_code == 200
    body = listed.json()
    assert body["total"] == 1
    assert body["items"][0]["slug"] == "visible"
    assert "cost_price" not in body["items"][0]

    assert client.get("/api/v1/products/hidden").status_code == 404
    detail = client.get("/api/v1/products/visible")
    assert detail.status_code == 200
    assert "cost_price" not in detail.json()


def test_arabic_search_ignores_spelling_variants(client: TestClient, db: Session) -> None:
    make_product(db, slug="alef", name="أدوات الخلط")
    found = client.get("/api/v1/products", params={"q": "ادوات"})
    assert found.json()["total"] == 1


def test_product_filters_and_pagination(client: TestClient, db: Session, category: Category) -> None:
    make_product(db, slug="p1", name="منتج ١", price="10.00", category_id=category.id, is_featured=True)
    make_product(db, slug="p2", name="منتج ٢", price="200.00", category_id=category.id)
    make_product(db, slug="p3", name="منتج ٣", price="50.00", stock=0, category_id=category.id)
    make_product(db, slug="mold", name="قالب", product_type=ProductType.SILICONE_MOLD.value)
    make_product(db, slug="kit", name="بكج", product_type=ProductType.PACKAGE.value)

    assert client.get("/api/v1/products", params={"is_featured": True}).json()["total"] == 1
    assert client.get("/api/v1/products", params={"in_stock": True}).json()["total"] == 4
    assert client.get("/api/v1/products", params={"max_price": 60}).json()["total"] == 2
    assert client.get("/api/v1/products", params={"category": "resin"}).json()["total"] == 3
    assert client.get("/api/v1/products/molds").json()["total"] == 1
    assert client.get("/api/v1/products/packages").json()["total"] == 1

    page = client.get("/api/v1/products", params={"page": 2, "page_size": 2}).json()
    assert page["page"] == 2 and page["pages"] == 3 and len(page["items"]) == 2

    cheapest = client.get("/api/v1/products", params={"sort": "price-asc"}).json()
    assert cheapest["items"][0]["price"] == 10


def test_variants_belong_to_their_product_and_carry_their_own_stock(
    client: TestClient, db: Session, admin_token: str
) -> None:
    product = make_product(db, slug="with-variants", name="منتج بخيارات")
    other = make_product(db, slug="other", name="منتج آخر")

    options = client.put(
        f"/api/v1/admin/products/{product.id}/options",
        headers=auth(admin_token),
        json=[{"name": "الحجم", "values": [{"value": "صغير"}, {"value": "كبير"}]}],
    )
    assert options.status_code == 200
    value_ids = [value["id"] for value in options.json()[0]["values"]]

    created = client.post(
        f"/api/v1/admin/products/{product.id}/variants",
        headers=auth(admin_token),
        json={
            "title": "كبير",
            "price_override": 150,
            "stock_quantity": 4,
            "option_value_ids": [value_ids[1]],
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["option_value_ids"] == [value_ids[1]]

    # A value from another product must not be attachable.
    foreign = client.post(
        f"/api/v1/admin/products/{other.id}/variants",
        headers=auth(admin_token),
        json={"title": "خطأ", "option_value_ids": [value_ids[0]]},
    )
    assert foreign.status_code == 400
    assert foreign.json()["error"]["code"] == "option_value_mismatch"

    detail = client.get(f"/api/v1/products/{product.slug}").json()
    assert len(detail["variants"]) == 1
    assert detail["variants"][0]["price_override"] == 150


def test_a_variant_cannot_take_two_values_from_the_same_axis(
    client: TestClient, db: Session, admin_token: str
) -> None:
    product = make_product(db, slug="two-axis", name="منتج بمحورين")
    options = client.put(
        f"/api/v1/admin/products/{product.id}/options",
        headers=auth(admin_token),
        json=[
            {"name": "اللون", "values": [{"value": "أحمر"}, {"value": "أزرق"}]},
            {"name": "الحجم", "values": [{"value": "صغير"}, {"value": "كبير"}]},
        ],
    ).json()
    colours = [value["id"] for value in options[0]["values"]]
    sizes = [value["id"] for value in options[1]["values"]]

    both_colours = client.post(
        f"/api/v1/admin/products/{product.id}/variants",
        headers=auth(admin_token),
        json={"title": "أحمر وأزرق", "option_value_ids": colours},
    )
    assert both_colours.status_code == 400
    assert both_colours.json()["error"]["code"] == "option_axis_conflict"

    # One value per axis is the combination the storefront resolves.
    created = client.post(
        f"/api/v1/admin/products/{product.id}/variants",
        headers=auth(admin_token),
        json={"title": "أحمر / كبير", "option_value_ids": [colours[0], sizes[1]]},
    )
    assert created.status_code == 201, created.text
    assert sorted(created.json()["option_value_ids"]) == sorted([colours[0], sizes[1]])


def test_listing_flags_products_that_need_an_option_chosen(
    client: TestClient, db: Session, admin_token: str
) -> None:
    """A catalogue card decides between a direct add and "choose an option" from
    the list projection, which deliberately carries no option rows."""
    plain = make_product(db, slug="plain-item", name="منتج بسيط")
    with_options = make_product(db, slug="option-item", name="منتج بخيارات")

    client.put(
        f"/api/v1/admin/products/{with_options.id}/options",
        headers=auth(admin_token),
        json=[{"name": "اللون", "values": [{"value": "أحمر"}, {"value": "أزرق"}]}],
    )

    listed = {item["slug"]: item for item in client.get("/api/v1/products").json()["items"]}
    assert listed[plain.slug]["has_options"] is False
    assert listed[with_options.slug]["has_options"] is True

    assert client.get(f"/api/v1/products/{with_options.slug}").json()["has_options"] is True


def test_package_cannot_contain_itself_or_another_package(
    client: TestClient, db: Session, admin_token: str
) -> None:
    package = make_product(
        db, slug="kit", name="بكج", product_type=ProductType.PACKAGE.value
    )
    other_package = make_product(
        db, slug="kit-2", name="بكج ٢", product_type=ProductType.PACKAGE.value
    )
    item = make_product(db, slug="item", name="عنصر")

    self_ref = client.post(
        f"/api/v1/admin/products/{package.id}/package-items",
        headers=auth(admin_token),
        json={"included_product_id": package.id, "quantity": 1},
    )
    assert self_ref.status_code == 400
    assert self_ref.json()["error"]["code"] == "package_self_reference"

    nested = client.post(
        f"/api/v1/admin/products/{package.id}/package-items",
        headers=auth(admin_token),
        json={"included_product_id": other_package.id, "quantity": 1},
    )
    assert nested.status_code == 400
    assert nested.json()["error"]["code"] == "package_nested"

    ok = client.post(
        f"/api/v1/admin/products/{package.id}/package-items",
        headers=auth(admin_token),
        json={"included_product_id": item.id, "quantity": 2, "display_note": "عنصر"},
    )
    assert ok.status_code == 201
    assert ok.json()["included_product_name"] == "عنصر"

    duplicate = client.post(
        f"/api/v1/admin/products/{package.id}/package-items",
        headers=auth(admin_token),
        json={"included_product_id": item.id, "quantity": 1},
    )
    assert duplicate.status_code == 409

    non_package = client.post(
        f"/api/v1/admin/products/{item.id}/package-items",
        headers=auth(admin_token),
        json={"included_product_id": package.id, "quantity": 1},
    )
    assert non_package.status_code == 400
    assert non_package.json()["error"]["code"] == "not_a_package"


def _add_image(client, admin_token, product_id, url):
    response = client.post(
        f"/api/v1/admin/products/{product_id}/images",
        headers=auth(admin_token),
        json={"url": url},
    )
    assert response.status_code == 201
    return response.json()


def test_product_image_order_decides_the_cover(
    client: TestClient, db: Session, admin_token: str
) -> None:
    """Order is the only source of truth: the first image is the cover."""
    product = make_product(db, slug="imaged", name="منتج بصورة")
    a = _add_image(client, admin_token, product.id, "/media/a.png")
    b = _add_image(client, admin_token, product.id, "/media/b.png")
    c = _add_image(client, admin_token, product.id, "/media/c.png")

    # An added image appends; it never takes the cover from an existing one.
    assert [image["sort_order"] for image in (a, b, c)] == [0, 1, 2]
    detail = client.get(f"/api/v1/products/{product.slug}").json()
    assert detail["primary_image_url"] == "/media/a.png"
    assert [image["url"] for image in detail["images"]] == ["/media/a.png", "/media/b.png", "/media/c.png"]

    reordered = client.put(
        f"/api/v1/admin/products/{product.id}/images/reorder",
        headers=auth(admin_token),
        json={"image_ids": [c["id"], a["id"], b["id"]]},
    )
    assert reordered.status_code == 200
    assert [image["url"] for image in reordered.json()] == ["/media/c.png", "/media/a.png", "/media/b.png"]
    assert [image["sort_order"] for image in reordered.json()] == [0, 1, 2]

    detail = client.get(f"/api/v1/products/{product.slug}").json()
    assert detail["primary_image_url"] == "/media/c.png"
    assert [image["url"] for image in detail["images"]] == ["/media/c.png", "/media/a.png", "/media/b.png"]

    # Removing the cover promotes whatever is now first, with no second call.
    removed = client.delete(
        f"/api/v1/admin/products/{product.id}/images/{c['id']}",
        headers=auth(admin_token),
    )
    assert removed.status_code == 200
    detail = client.get(f"/api/v1/products/{product.slug}").json()
    assert detail["primary_image_url"] == "/media/a.png"
    assert [image["sort_order"] for image in detail["images"]] == [0, 1]


def test_image_reorder_rejects_anything_but_a_full_permutation(
    client: TestClient, db: Session, admin_token: str
) -> None:
    product = make_product(db, slug="imaged-2", name="منتج آخر")
    other = make_product(db, slug="imaged-3", name="منتج ثالث")
    a = _add_image(client, admin_token, product.id, "/media/a.png")
    b = _add_image(client, admin_token, product.id, "/media/b.png")
    foreign = _add_image(client, admin_token, other.id, "/media/x.png")

    def reorder(image_ids):
        return client.put(
            f"/api/v1/admin/products/{product.id}/images/reorder",
            headers=auth(admin_token),
            json={"image_ids": image_ids},
        )

    assert reorder([a["id"], foreign["id"]]).status_code == 400
    assert reorder([a["id"], foreign["id"]]).json()["error"]["code"] == "image_mismatch"
    assert reorder([a["id"], a["id"]]).json()["error"]["code"] == "image_mismatch"
    assert reorder([a["id"]]).json()["error"]["code"] == "image_mismatch"
    assert reorder([]).status_code == 422

    # A rejected reorder leaves the stored order untouched.
    detail = client.get(f"/api/v1/products/{product.slug}").json()
    assert [image["id"] for image in detail["images"]] == [a["id"], b["id"]]


def test_list_projection_carries_a_secondary_image(
    client: TestClient, db: Session, admin_token: str
) -> None:
    """A catalogue card swaps to the second image on hover.

    The field has to ride on the *list* payload: without it every card in a grid
    would need a product-detail request just to know whether it has a second
    picture. A product with one image reports None, which is the fallback the
    cards render as "cover stays put".
    """
    product = make_product(db, slug="two-shots", name="منتج بصورتين")

    single = next(
        row
        for row in client.get("/api/v1/products").json()["items"]
        if row["slug"] == product.slug
    )
    assert single["secondary_image_url"] is None

    for url in ("/media/cover.png", "/media/contents.png"):
        created = client.post(
            f"/api/v1/admin/products/{product.id}/images",
            headers=auth(admin_token),
            json={"url": url},
        )
        assert created.status_code == 201

    listed = next(
        row
        for row in client.get("/api/v1/products").json()["items"]
        if row["slug"] == product.slug
    )
    assert listed["primary_image_url"] == "/media/cover.png"
    assert listed["secondary_image_url"] == "/media/contents.png"
    # The detail projection agrees with the list one.
    assert client.get(f"/api/v1/products/{product.slug}").json()["secondary_image_url"] == (
        "/media/contents.png"
    )


def _two_axis_product(client: TestClient, db: Session, admin_token: str, slug: str):
    """A product with اللون × الحجم and one variant per combination."""
    product = make_product(db, slug=slug, name="منتج للنسخ")
    options = client.put(
        f"/api/v1/admin/products/{product.id}/options",
        headers=auth(admin_token),
        json=[
            {"name": "اللون", "values": [{"value": "أحمر"}, {"value": "أزرق"}]},
            {"name": "الحجم", "values": [{"value": "صغير"}, {"value": "كبير"}]},
        ],
    ).json()
    variants = {}
    for colour in options[0]["values"]:
        for size in options[1]["values"]:
            key = (colour["value"], size["value"])
            variants[key] = client.post(
                f"/api/v1/admin/products/{product.id}/variants",
                headers=auth(admin_token),
                json={
                    "title": f"{colour['value']} / {size['value']}",
                    "sku": f"{slug}-{len(variants)}",
                    "stock_quantity": 3 + len(variants),
                    "price_override": 120,
                    "option_value_ids": [colour["id"], size["id"]],
                },
            ).json()
    return product, options, variants


def _variants(client: TestClient, admin_token: str, product_id: int) -> dict[int, dict]:
    rows = client.get(
        f"/api/v1/admin/products/{product_id}/variants", headers=auth(admin_token)
    ).json()
    return {row["id"]: row for row in rows}


def test_renaming_an_axis_or_a_value_keeps_every_variant(
    client: TestClient, db: Session, admin_token: str
) -> None:
    product, options, variants = _two_axis_product(client, db, admin_token, "rename-keeps")
    before = _variants(client, admin_token, product.id)

    saved = client.put(
        f"/api/v1/admin/products/{product.id}/options",
        headers=auth(admin_token),
        json=[
            {
                "id": options[0]["id"],
                "name": "الدرجة اللونية",  # axis renamed
                "values": [
                    {"id": options[0]["values"][0]["id"], "value": "قرمزي"},  # value renamed
                    {"id": options[0]["values"][1]["id"], "value": "أزرق"},
                ],
            },
            {
                "id": options[1]["id"],
                "name": "الحجم",
                "values": [{"id": value["id"], "value": value["value"]} for value in options[1]["values"]],
            },
        ],
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()[0]["name"] == "الدرجة اللونية"
    assert saved.json()[0]["values"][0]["id"] == options[0]["values"][0]["id"]

    after = _variants(client, admin_token, product.id)
    assert after == before  # ids, sku, stock, price, is_active and links untouched
    assert len(after) == len(variants)


def test_adding_a_value_keeps_variants_and_the_generator_fills_only_the_gap(
    client: TestClient, db: Session, admin_token: str
) -> None:
    product, options, _ = _two_axis_product(client, db, admin_token, "add-value")
    before = _variants(client, admin_token, product.id)

    saved = client.put(
        f"/api/v1/admin/products/{product.id}/options",
        headers=auth(admin_token),
        json=[
            {
                "id": options[0]["id"],
                "name": "اللون",
                "values": [
                    *[{"id": value["id"], "value": value["value"]} for value in options[0]["values"]],
                    {"value": "أخضر"},
                ],
            },
            {
                "id": options[1]["id"],
                "name": "الحجم",
                "values": [{"id": value["id"], "value": value["value"]} for value in options[1]["values"]],
            },
        ],
    ).json()

    after = _variants(client, admin_token, product.id)
    assert after == before  # no variant lost, none created for the new value

    # The generator adds only the missing combinations of the new value.
    green = saved[0]["values"][2]["id"]
    for size in saved[1]["values"]:
        created = client.post(
            f"/api/v1/admin/products/{product.id}/variants",
            headers=auth(admin_token),
            json={"title": "أخضر", "option_value_ids": [green, size["id"]]},
        )
        assert created.status_code == 201, created.text
    assert len(_variants(client, admin_token, product.id)) == len(before) + 2


def test_deleting_a_value_removes_only_the_variants_that_used_it(
    client: TestClient, db: Session, admin_token: str
) -> None:
    product, options, variants = _two_axis_product(client, db, admin_token, "drop-value")
    dropped = options[0]["values"][1]["id"]  # أزرق
    survivors = {
        variant["id"]: variant
        for key, variant in variants.items()
        if key[0] != "أزرق"
    }

    client.put(
        f"/api/v1/admin/products/{product.id}/options",
        headers=auth(admin_token),
        json=[
            {
                "id": options[0]["id"],
                "name": "اللون",
                "values": [{"id": options[0]["values"][0]["id"], "value": "أحمر"}],
            },
            {
                "id": options[1]["id"],
                "name": "الحجم",
                "values": [{"id": value["id"], "value": value["value"]} for value in options[1]["values"]],
            },
        ],
    )

    after = _variants(client, admin_token, product.id)
    assert set(after) == set(survivors)
    for variant_id, kept in after.items():
        was = survivors[variant_id]
        assert (kept["sku"], kept["stock_quantity"], kept["price_override"], kept["is_active"]) == (
            was["sku"],
            was["stock_quantity"],
            was["price_override"],
            was["is_active"],
        )
    assert dropped not in {vid for row in after.values() for vid in row["option_value_ids"]}


def test_removing_a_whole_axis_drops_the_variants_instead_of_merging_them(
    client: TestClient, db: Session, admin_token: str
) -> None:
    product, options, _ = _two_axis_product(client, db, admin_token, "drop-axis")
    client.put(
        f"/api/v1/admin/products/{product.id}/options",
        headers=auth(admin_token),
        json=[
            {
                "id": options[0]["id"],
                "name": "اللون",
                "values": [{"id": value["id"], "value": value["value"]} for value in options[0]["values"]],
            }
        ],
    )
    assert _variants(client, admin_token, product.id) == {}


def test_a_rejected_option_update_leaves_options_and_variants_untouched(
    client: TestClient, db: Session, admin_token: str
) -> None:
    product, options, _ = _two_axis_product(client, db, admin_token, "rollback")
    before = _variants(client, admin_token, product.id)

    failed = client.put(
        f"/api/v1/admin/products/{product.id}/options",
        headers=auth(admin_token),
        json=[
            {"id": options[0]["id"], "name": "لون جديد", "values": []},
            {"id": 999999, "name": "محور وهمي", "values": []},
        ],
    )
    assert failed.status_code == 400
    assert failed.json()["error"]["code"] == "option_not_found"

    kept = client.get(
        f"/api/v1/admin/products/{product.id}/options", headers=auth(admin_token)
    ).json()
    assert [option["name"] for option in kept] == ["اللون", "الحجم"]
    assert _variants(client, admin_token, product.id) == before
