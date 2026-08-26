"""Build the deterministic acceptance fixture for a disposable validation database.

This script never runs against the tracked development databases. It refuses any
DATABASE_URL whose file name is not of the ``vista_full_validation_*.db`` form, so a
mistyped argument cannot reseed ``vista_preview.db`` or ``vista_store_dev.db``.

Catalog, content, marketing and account rows are written through the ORM. Orders and
invoices are created through the real HTTP API (an in-process TestClient bound to the
same engine) so every domain invariant, activity record, invoice numbering rule and
one-active-invoice constraint is exercised exactly as it is in production.

Idempotency is achieved by always seeding a *fresh* disposable database rather than by
deleting rows. That is deliberate: migration 0008 installs append-only triggers on
``order_activities``, so a fixture that tried to delete its own orders would have to
fight the very invariant the acceptance run is meant to prove. The script therefore
refuses to seed a database that already carries the fixture, and running it on a new
copy always produces the identical dataset.

    # 1. make a disposable copy and bring it to head
    copy backend\\data\\vista_preview.db backend\\data\\vista_full_validation_<stamp>.db
    DATABASE_URL=sqlite+pysqlite:///./data/vista_full_validation_<stamp>.db alembic upgrade head

    # 2. seed it
    python scripts/seed_full_validation.py \
        --database-url sqlite+pysqlite:///./data/vista_full_validation_<stamp>.db
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import delete, select, update  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

# ── fixture namespace ────────────────────────────────────────────────────────
# Everything this fixture owns carries one of these markers, so fixture rows stay
# distinguishable from the preview data already in the copied database.
SLUG_PREFIX = "vfx-"
# Not a special-use TLD: `email-validator` rejects .local/.test/.example outright,
# and the login endpoint validates the address as an EmailStr.
EMAIL_DOMAIN = "vista-acceptance.dev"
LEGACY_EMAIL_DOMAINS = ("validation.local",)
CLIENT_REF_PREFIX = "vfx-checkout-"
COUPON_PREFIX = "VFX"
ZONE_PREFIX = "VFX "

# Acceptance-only credentials. They exist solely inside the disposable database and
# are deliberately not documented in the committed fixture manifest.
FIXTURE_PASSWORD = "Validation!Pass42"

SUPER_ADMIN_EMAIL = f"super@{EMAIL_DOMAIN}"
NORMAL_ADMIN_EMAIL = f"admin@{EMAIL_DOMAIN}"
INACTIVE_ADMIN_EMAIL = f"inactive@{EMAIL_DOMAIN}"

VALIDATION_DB_PATTERN = re.compile(r"vista_full_validation_[0-9]{8}-[0-9]{6}\.db$")


def _guard_database_url(url: str) -> None:
    """Refuse to touch anything but a disposable validation database."""
    if not url.startswith("sqlite"):
        raise SystemExit(f"refusing non-sqlite target: {url}")
    tail = url.split("///", 1)[-1]
    if not VALIDATION_DB_PATTERN.search(tail):
        raise SystemExit(
            "refusing to seed a database that is not a disposable validation copy.\n"
            f"  got     : {url}\n"
            "  expected: .../data/vista_full_validation_<yyyymmdd-hhmmss>.db"
        )


# ── ORM seeding ──────────────────────────────────────────────────────────────
def guard_not_already_seeded(db: Session) -> None:
    """Refuse to seed twice.

    Re-seeding in place is not possible without deleting orders, and order history is
    append-only by database trigger from migration 0008. A second run therefore has to
    start from a new copy of the database.
    """
    from app.models import AdminUser, Product

    already = db.execute(
        select(AdminUser.id).where(AdminUser.email == SUPER_ADMIN_EMAIL)
    ).first() or db.execute(
        select(Product.id).where(Product.slug.like(f"{SLUG_PREFIX}%"))
    ).first()

    if already:
        raise SystemExit(
            "this database already carries the validation fixture.\n"
            "order history is append-only (migration 0008), so the fixture cannot be\n"
            "rebuilt in place. Make a new copy of the source database, upgrade it to\n"
            "head, and seed that instead."
        )


def seed_admins(db: Session) -> dict[str, int]:
    from app.core.enums import AdminRole
    from app.core.security import hash_password
    from app.models import AdminUser

    rows = [
        (SUPER_ADMIN_EMAIL, "مدير عام للتحقق", AdminRole.SUPER_ADMIN.value, True),
        (NORMAL_ADMIN_EMAIL, "موظف للتحقق", AdminRole.ADMIN.value, True),
        (INACTIVE_ADMIN_EMAIL, "حساب معطل", AdminRole.ADMIN.value, False),
    ]
    ids: dict[str, int] = {}
    for email, name, role, active in rows:
        account = AdminUser(
            email=email,
            full_name=name,
            password_hash=hash_password(FIXTURE_PASSWORD),
            role=role,
            is_active=active,
        )
        db.add(account)
        db.flush()
        ids[email] = account.id
    db.commit()
    return ids


def seed_catalog(db: Session) -> dict[str, int]:
    from app.core.enums import ProductType
    from app.models import Category, Product
    from app.models.catalog import ProductImage, ProductSpecification
    from app.services.catalog import refresh_search_text

    categories = {
        "resin": Category(
            name="ريزن وإكسسوارات",
            slug=f"{SLUG_PREFIX}resin",
            description="خامات الريزن الشفاف والملون",
            image_url="/media/seed-clay.png",
            is_active=True,
            is_featured=True,
            sort_order=1,
        ),
        "molds": Category(
            name="قوالب سيليكون",
            slug=f"{SLUG_PREFIX}molds",
            description="قوالب بأحجام مختلفة",
            is_active=True,
            sort_order=2,
        ),
        "packages": Category(
            name="باقات جاهزة",
            slug=f"{SLUG_PREFIX}packages",
            is_active=True,
            sort_order=3,
        ),
        "hidden": Category(
            name="قسم غير مفعل",
            slug=f"{SLUG_PREFIX}hidden",
            is_active=False,
            sort_order=9,
        ),
    }
    for row in categories.values():
        db.add(row)
    db.flush()

    def product(**kw) -> Product:
        images = kw.pop("images", [])
        specs = kw.pop("specs", [])
        row = Product(**kw)
        refresh_search_text(row)
        db.add(row)
        db.flush()
        for index, url in enumerate(images):
            db.add(
                ProductImage(
                    product_id=row.id,
                    url=url,
                    alt_text=row.name,
                    sort_order=index,
                )
            )
        for index, (name, value) in enumerate(specs):
            db.add(
                ProductSpecification(
                    product_id=row.id, name=name, value=value, sort_order=index
                )
            )
        db.flush()
        return row

    resin = categories["resin"].id
    molds = categories["molds"].id
    packages = categories["packages"].id

    products: dict[str, Product] = {}

    # Two products in the same category, both cart/checkout ready, one discounted.
    products["resin_clear"] = product(
        name="ريزن إيبوكسي شفاف - عبوة ١ لتر",
        slug=f"{SLUG_PREFIX}resin-clear-1l",
        sku="VFX-RES-001",
        category_id=resin,
        short_description="ريزن شفاف عالي النقاء",
        description="ريزن إيبوكسي شفاف مناسب للمجوهرات والطاولات. لا يصفرّ مع الوقت.",
        price=Decimal("120.00"),
        stock_quantity=40,
        is_active=True,
        is_featured=True,
        is_new=True,
        product_type=ProductType.STANDARD.value,
        images=["/media/seed-cream.png", "/media/seed-clay.png"],
        specs=[("الحجم", "١ لتر"), ("زمن الجفاف", "٢٤ ساعة"), ("النسبة", "٢:١")],
    )
    products["resin_color"] = product(
        name="ريزن ملون - مجموعة ٦ ألوان",
        slug=f"{SLUG_PREFIX}resin-colors-6",
        sku="VFX-RES-002",
        category_id=resin,
        description="ست ألوان أساسية قابلة للمزج.",
        price=Decimal("85.00"),
        compare_at_price=Decimal("110.00"),  # discounted -> appears in offers
        stock_quantity=25,
        is_active=True,
        is_bestseller=True,
        product_type=ProductType.STANDARD.value,
        images=["/media/seed-cream.png"],
        specs=[("عدد الألوان", "٦")],
    )
    # Missing optional image.
    products["mold_round"] = product(
        name="قالب سيليكون دائري ١٠ سم",
        slug=f"{SLUG_PREFIX}mold-round-10",
        sku="VFX-MLD-001",
        category_id=molds,
        price=Decimal("45.00"),
        stock_quantity=12,
        is_active=True,
        product_type=ProductType.SILICONE_MOLD.value,
    )
    # Low stock (threshold default 3).
    products["mold_low"] = product(
        name="قالب سيليكون مربع ١٥ سم",
        slug=f"{SLUG_PREFIX}mold-square-15",
        sku="VFX-MLD-002",
        category_id=molds,
        price=Decimal("60.00"),
        stock_quantity=2,
        low_stock_threshold=3,
        is_active=True,
        product_type=ProductType.SILICONE_MOLD.value,
        images=["/media/seed-clay.png"],
    )
    # Out of stock.
    products["mold_out"] = product(
        name="قالب سيليكون سداسي - نفدت الكمية",
        slug=f"{SLUG_PREFIX}mold-hex-out",
        sku="VFX-MLD-003",
        category_id=molds,
        price=Decimal("55.00"),
        stock_quantity=0,
        is_active=True,
        product_type=ProductType.SILICONE_MOLD.value,
    )
    # Inactive product: must never appear publicly.
    products["inactive"] = product(
        name="منتج غير مفعل",
        slug=f"{SLUG_PREFIX}inactive-product",
        sku="VFX-INA-001",
        category_id=resin,
        price=Decimal("30.00"),
        stock_quantity=5,
        is_active=False,
        product_type=ProductType.STANDARD.value,
    )
    # Long but valid Arabic name, boundary case for card and table layout.
    products["long_name"] = product(
        name=(
            "طقم متكامل لصناعة المجوهرات الراتنجية يحتوي على الريزن والمصلب "
            "والأصباغ والقوالب وأدوات القياس والتشطيب النهائي"
        ),
        slug=f"{SLUG_PREFIX}long-name-kit",
        sku="VFX-PKG-001",
        category_id=packages,
        price=Decimal("310.00"),
        compare_at_price=Decimal("380.00"),
        stock_quantity=8,
        is_active=True,
        is_featured=True,
        product_type=ProductType.PACKAGE.value,
        images=["/media/seed-cream.png"],
        specs=[("عدد القطع", "١٢"), ("Packaging", "Gift box")],
    )
    # Mixed Arabic/English, duplicate-like name with a distinct id and slug.
    products["dup_a"] = product(
        name="Resin Kit - طقم ريزن",
        slug=f"{SLUG_PREFIX}resin-kit-a",
        sku="VFX-PKG-002",
        category_id=packages,
        price=Decimal("199.00"),
        stock_quantity=6,
        is_active=True,
        product_type=ProductType.PACKAGE.value,
    )
    products["dup_b"] = product(
        name="Resin Kit - طقم ريزن",
        slug=f"{SLUG_PREFIX}resin-kit-b",
        sku="VFX-PKG-003",
        category_id=packages,
        price=Decimal("249.00"),
        stock_quantity=4,
        is_active=True,
        product_type=ProductType.PACKAGE.value,
    )

    db.commit()
    return {
        **{f"category:{k}": v.id for k, v in categories.items()},
        **{f"product:{k}": v.id for k, v in products.items()},
    }


def seed_media(db: Session) -> None:
    """Generate disposable files for the acceptance catalog's local media URLs."""
    from app.core.config import settings
    from app.models import MediaAsset
    from app.services.placeholder_image import gradient_png

    palette = {
        "seed-cream.png": ((248, 238, 218), (214, 178, 133)),
        "seed-clay.png": ((214, 178, 133), (129, 88, 64)),
        "seed-hero-teal.png": ((63, 118, 112), (20, 61, 58)),
        "seed-hero-clay.png": ((214, 178, 133), (108, 67, 50)),
    }
    root = settings.media_root
    root.mkdir(parents=True, exist_ok=True)
    for filename, (start, end) in palette.items():
        content = gradient_png(640, 480, start, end)
        (root / filename).write_bytes(content)
        db.add(MediaAsset(original_filename=filename, stored_key=filename, content_type="image/png", size_bytes=len(content), url=f"/media/{filename}"))
    db.commit()

    # The disposable copy includes historical demo rows that point at R2.  Keep the
    # validation storefront self-contained: every image it can render is local.
    from app.models.catalog import ProductImage
    from app.models.marketing import HeroSlide

    db.execute(update(ProductImage).where(ProductImage.url.like("http%")).values(url="/media/seed-cream.png"))
    db.execute(update(HeroSlide).where(HeroSlide.image_url.like("http%")).values(image_url="/media/seed-hero-teal.png"))
    db.execute(update(MediaAsset).where(MediaAsset.url.like("http%")).values(url="/media/seed-cream.png"))
    db.commit()


def seed_content(db: Session) -> None:
    from app.models import HeroSlide, HomeSection, StaticPage

    # The copied development database can carry obsolete homepage rows. The
    # disposable acceptance fixture owns its deterministic current section set.
    db.execute(delete(HomeSection))

    db.add_all(
        [
            HeroSlide(
                title="[vfx] عروض الريزن",
                subtitle="خصومات حتى ٣٠٪",
                description="على كامل تشكيلة الريزن الشفاف",
                image_url="/media/seed-hero-teal.png",
                button_label="تسوق الآن",
                button_url="/shop",
                is_active=True,
                sort_order=1,
            ),
            HeroSlide(
                title="[vfx] قوالب جديدة",
                subtitle="تشكيلة ٢٠٢٦",
                image_url="/media/seed-hero-clay.png",
                button_label="اكتشف",
                button_url="/molds",
                is_active=True,
                sort_order=2,
            ),
            HeroSlide(
                title="[vfx] شريحة غير مفعلة",
                is_active=False,
                sort_order=3,
            ),
        ]
    )

    db.add_all(
        [
            StaticPage(
                title="صفحة تحقق ثابتة",
                slug=f"{SLUG_PREFIX}validation-page",
                lead="صفحة أنشأها ملف التحقق",
                content="<p>محتوى ثابت للتحقق من مسار /page/:slug</p>",
                is_published=True,
            ),
            StaticPage(
                title="صفحة غير منشورة",
                slug=f"{SLUG_PREFIX}unpublished-page",
                content="<p>يجب ألا تظهر</p>",
                is_published=False,
            ),
        ]
    )
    db.add_all(
        [
            HomeSection(section_key="featured", section_type="featured_products", is_visible=True, sort_order=1, config={}),
            HomeSection(section_key="packages", section_type="packages", is_visible=True, sort_order=2, config={}),
            HomeSection(section_key="categories", section_type="categories", is_visible=True, sort_order=3, config={}),
        ]
    )
    db.commit()


def seed_promotions(db: Session) -> dict[str, int]:
    from app.core.enums import DiscountType
    from app.models import Coupon, DeliveryArea

    now = datetime.utcnow()
    coupons = {
        "valid_pct": Coupon(
            code=f"{COUPON_PREFIX}VALID20",
            description="خصم ٢٠٪ صالح",
            discount_type=DiscountType.PERCENTAGE.value,
            discount_value=Decimal("20.00"),
            min_order_amount=Decimal("0.00"),
            max_discount_amount=Decimal("100.00"),
            is_active=True,
            starts_at=now - timedelta(days=10),
            ends_at=now + timedelta(days=60),
        ),
        "valid_fixed": Coupon(
            code=f"{COUPON_PREFIX}FIXED25",
            description="خصم ٢٥ شيكل",
            discount_type=DiscountType.FIXED.value,
            discount_value=Decimal("25.00"),
            min_order_amount=Decimal("150.00"),
            is_active=True,
        ),
        "expired": Coupon(
            code=f"{COUPON_PREFIX}EXPIRED",
            discount_type=DiscountType.PERCENTAGE.value,
            discount_value=Decimal("15.00"),
            is_active=True,
            starts_at=now - timedelta(days=90),
            ends_at=now - timedelta(days=30),
        ),
        "limited": Coupon(
            code=f"{COUPON_PREFIX}LIMIT1",
            discount_type=DiscountType.FIXED.value,
            discount_value=Decimal("10.00"),
            usage_limit=1,
            used_count=1,  # already exhausted
            is_active=True,
        ),
        "disabled": Coupon(
            code=f"{COUPON_PREFIX}DISABLED",
            discount_type=DiscountType.FIXED.value,
            discount_value=Decimal("30.00"),
            is_active=False,
        ),
    }
    zones = {
        "ramallah": DeliveryArea(
            name=f"{ZONE_PREFIX}رام الله",
            delivery_fee=Decimal("20.00"),
            free_delivery_threshold=Decimal("500.00"),
            estimated_days="١-٢ يوم",
            is_active=True,
            sort_order=1,
        ),
        "nablus": DeliveryArea(
            name=f"{ZONE_PREFIX}نابلس",
            delivery_fee=Decimal("35.00"),
            min_order_amount=Decimal("100.00"),
            estimated_days="٢-٣ أيام",
            is_active=True,
            sort_order=2,
        ),
        "free": DeliveryArea(
            name=f"{ZONE_PREFIX}استلام من المتجر",
            delivery_fee=Decimal("0.00"),
            is_active=True,
            sort_order=3,
        ),
        "inactive": DeliveryArea(
            name=f"{ZONE_PREFIX}منطقة معطلة",
            delivery_fee=Decimal("99.00"),
            is_active=False,
            sort_order=4,
        ),
    }
    for row in list(coupons.values()) + list(zones.values()):
        db.add(row)
    db.commit()
    return {
        **{f"coupon:{k}": v.id for k, v in coupons.items()},
        **{f"zone:{k}": v.id for k, v in zones.items()},
    }


def seed_store_settings(db: Session) -> None:
    """Make sure the storefront has contact/WhatsApp data to render."""
    from app.models import StoreSettings

    row = db.execute(select(StoreSettings)).scalars().first()
    if row is None:
        row = StoreSettings()
        db.add(row)
    row.store_name = row.store_name or "Vista Store"
    row.whatsapp = "970599000000"
    row.phone = "0599000000"
    row.email = f"store@{EMAIL_DOMAIN}"
    row.address = "رام الله - فلسطين"
    row.working_hours = "٩ صباحاً - ٧ مساءً"
    row.maintenance_mode = False
    row.location_url = ""
    row.instagram_url = ""
    row.facebook_url = ""
    row.tiktok_url = ""
    row.youtube_url = ""
    db.commit()


# ── API-driven order and invoice fixtures ────────────────────────────────────
def seed_orders_and_invoices(session_factory: sessionmaker, ids: dict[str, int]) -> dict:
    from fastapi.testclient import TestClient

    from app.db.session import get_db
    from app.main import app

    def override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    manifest: dict[str, object] = {"orders": [], "invoices": []}

    try:
        with TestClient(app) as client:

            def login(email: str) -> dict[str, str]:
                res = client.post(
                    "/api/v1/auth/login",
                    json={"email": email, "password": FIXTURE_PASSWORD},
                )
                res.raise_for_status()
                return {"Authorization": f"Bearer {res.json()['access_token']}"}

            manager = login(SUPER_ADMIN_EMAIL)
            employee = login(NORMAL_ADMIN_EMAIL)

            clear = ids["product:resin_clear"]
            colors = ids["product:resin_color"]
            mold = ids["product:mold_round"]

            def website_order(tag: str, **over) -> dict:
                payload = {
                    "client_reference": f"{CLIENT_REF_PREFIX}{tag}",
                    "customer_name": over.pop("customer_name", "سارة عبد الله"),
                    "customer_phone": over.pop("customer_phone", "0591234567"),
                    "address": "رام الله - شارع الإرسال ١٢",
                    "delivery_area_id": ids["zone:ramallah"],
                    "payment_method": "cash_on_delivery",
                    "items": [{"product_id": clear, "quantity": 1}],
                }
                payload.update(over)
                res = client.post("/api/v1/orders", json=payload)
                res.raise_for_status()
                return res.json()

            def manual_order(tag: str, **over) -> dict:
                payload = {
                    "source": "phone",
                    "customer_name": "زبون هاتفي",
                    "customer_phone": "0598887777",
                    "address": "نابلس - شارع فيصل ٥",
                    "payment_method": "cash_on_delivery",
                    "admin_notes": f"[vfx-fixture] {tag}",
                    "items": [{"kind": "catalog", "product_id": mold, "quantity": 1}],
                }
                payload.update(over)
                res = client.post(
                    "/api/v1/admin/orders/manual", json=payload, headers=manager
                )
                res.raise_for_status()
                return res.json()

            def set_status(order_id: int, status: str, note: str | None = None) -> None:
                res = client.post(
                    f"/api/v1/admin/orders/{order_id}/status",
                    json={"status": status, "note": note},
                    headers=manager,
                )
                res.raise_for_status()

            def complete(order_id: int, **over) -> dict:
                """Completion returns the order; the fixture wants the invoice it issued."""
                payload = {
                    "payment_method": "cash_on_delivery",
                    "paid_amount": "0.00",
                }
                payload.update(over)
                res = client.post(
                    f"/api/v1/admin/orders/{order_id}/complete",
                    json=payload,
                    headers=manager,
                )
                res.raise_for_status()
                invoice = res.json().get("active_invoice")
                if not invoice:
                    raise RuntimeError(
                        f"order {order_id} completed without an active invoice"
                    )
                return invoice

            def pay(number: str, headers: dict[str, str], **body) -> dict:
                res = client.patch(
                    f"/api/v1/admin/invoices/{number}/payment", json=body, headers=headers
                )
                res.raise_for_status()
                return res.json()

            def record(order: dict, note: str) -> None:
                manifest["orders"].append(
                    {
                        "order_number": order.get("order_number"),
                        "id": order.get("id"),
                        "scenario": note,
                    }
                )

            # ── one website order per non-terminal canonical status ──────────
            statuses = ["new", "reviewing", "preparing", "out_for_delivery"]
            for status in statuses:
                order = website_order(f"status-{status}")
                if status != "new":
                    set_status(order["id"], status, note=f"نقل إلى {status}")
                record(order, f"website order left at status={status}")

            # Cancelled website order.
            cancelled = website_order("status-cancelled")
            set_status(cancelled["id"], "cancelled", note="ألغى الزبون الطلب")
            record(cancelled, "website order cancelled")

            # Website order with coupon, discount and multiple items.
            rich = website_order(
                "rich",
                items=[
                    {"product_id": clear, "quantity": 2},
                    {"product_id": colors, "quantity": 1},
                ],
                coupon_code=f"{COUPON_PREFIX}VALID20",
                customer_notes="يرجى التغليف كهدية",
            )
            set_status(rich["id"], "reviewing")
            record(rich, "website order with coupon, 2 items, customer notes")

            # ── completed website order -> active invoice, unpaid ────────────
            completed_unpaid = website_order("completed-unpaid")
            set_status(completed_unpaid["id"], "preparing")
            inv = complete(completed_unpaid["id"], payment_method="bank_transfer")
            record(completed_unpaid, "completed website order, invoice unpaid")
            manifest["invoices"].append(
                {"invoice_number": inv["invoice_number"], "scenario": "active / unpaid / bank_transfer"}
            )

            # ── completed website order, fully paid by card ──────────────────
            completed_paid = website_order("completed-paid")
            inv_paid = complete(
                completed_paid["id"],
                payment_method="card",
                paid_amount=str(completed_paid["total"]),
                payment_details="بطاقة تنتهي بـ 4242",
            )
            record(completed_paid, "completed website order, invoice fully paid")
            manifest["invoices"].append(
                {"invoice_number": inv_paid["invoice_number"], "scenario": "active / paid / card"}
            )

            # ── partially paid invoice (employee-driven, allowed increase) ───
            partial_order = website_order("completed-partial")
            inv_partial = complete(partial_order["id"])
            pay(
                inv_partial["invoice_number"],
                employee,
                paid_amount="20.00",
                payment_details="دفعة أولى نقداً",
            )
            record(partial_order, "completed website order, invoice partially paid")
            manifest["invoices"].append(
                {
                    "invoice_number": inv_partial["invoice_number"],
                    "scenario": "active / partially_paid / cash_on_delivery",
                }
            )

            # ── refunds (manager only) ──────────────────────────────────────
            refund_order = website_order("refunded")
            inv_refund = complete(
                refund_order["id"],
                payment_method="card",
                paid_amount=str(refund_order["total"]),
            )
            pay(
                inv_refund["invoice_number"],
                manager,
                refunded_amount="10.00",
                reason="إرجاع جزئي لقطعة تالفة",
            )
            record(refund_order, "completed order, invoice partially refunded")
            manifest["invoices"].append(
                {
                    "invoice_number": inv_refund["invoice_number"],
                    "scenario": "active / partially_refunded",
                }
            )

            full_refund_order = website_order("full-refunded")
            inv_full = complete(
                full_refund_order["id"],
                payment_method="card",
                paid_amount=str(full_refund_order["total"]),
            )
            pay(
                inv_full["invoice_number"],
                manager,
                refunded_amount=str(full_refund_order["total"]),
                reason="إرجاع كامل بطلب الزبون",
            )
            record(full_refund_order, "completed order, invoice fully refunded")
            manifest["invoices"].append(
                {"invoice_number": inv_full["invoice_number"], "scenario": "active / refunded"}
            )

            # ── replacement pair: complete -> reopen -> edit -> recomplete ───
            replaced_order = website_order("replaced")
            first_invoice = complete(replaced_order["id"])
            res = client.post(
                f"/api/v1/admin/orders/{replaced_order['id']}/reopen",
                json={"reason": "تصحيح الكمية بعد اتصال الزبون"},
                headers=manager,
            )
            res.raise_for_status()
            res = client.patch(
                f"/api/v1/admin/orders/{replaced_order['id']}",
                json={
                    "customer_name": "سارة عبد الله",
                    "customer_phone": "0591234567",
                    "address": "رام الله - شارع الإرسال ١٢",
                    "payment_method": "cash_on_delivery",
                    "discount": "0.00",
                    "delivery_fee": "20.00",
                    "status": "preparing",
                    "reason": "تصحيح الكمية بعد اتصال الزبون",
                    "items": [{"product_id": clear, "quantity": 3}],
                },
                headers=manager,
            )
            res.raise_for_status()
            second_invoice = complete(replaced_order["id"], paid_amount="50.00")
            record(replaced_order, "completed -> reopened -> recompleted (invoice replacement)")
            manifest["invoices"].append(
                {
                    "invoice_number": first_invoice["invoice_number"],
                    "scenario": "replaced (superseded by the reopen cycle)",
                }
            )
            manifest["invoices"].append(
                {
                    "invoice_number": second_invoice["invoice_number"],
                    "scenario": "active / partially_paid / replacement of "
                    + first_invoice["invoice_number"],
                }
            )

            # ── cancelled invoice (legacy state, see note below) ─────────────
            # There is no API path that produces this state today: an invoice only
            # exists once its order is completed, and POST /invoices/{n}/cancel then
            # refuses with `order_locked`. The archive still offers `cancelled` as a
            # filter for rows written before completion locked orders, so the fixture
            # has to write one directly to give that filter something to match.
            cancel_order = website_order("invoice-cancelled")
            inv_cancel = complete(cancel_order["id"])
            manifest["legacy_cancelled_invoice"] = inv_cancel["invoice_number"]
            record(
                cancel_order,
                "completed order whose invoice is forced to the legacy cancelled state",
            )
            manifest["invoices"].append(
                {
                    "invoice_number": inv_cancel["invoice_number"],
                    "scenario": "cancelled (legacy state, written directly)",
                }
            )

            # ── manual orders, one per non-website source ────────────────────
            sources = [
                ("whatsapp", {"customer_name": "زبون واتساب"}),
                ("phone", {"customer_name": "زبون هاتفي"}),
                ("walk_in", {"customer_name": "زبون من المعرض"}),
                ("social", {"customer_name": "زبون إنستغرام"}),
                ("other", {"customer_name": "مصدر آخر", "source_note": "معرض حرفي"}),
            ]
            for source, over in sources:
                order = manual_order(f"source-{source}", source=source, **over)
                record(order, f"manual order, source={source}")

            # Manual-item-only order, including two rows with the same name.
            manual_items_only = manual_order(
                "manual-items",
                source="walk_in",
                customer_name="طلب بنود يدوية",
                items=[
                    {
                        "kind": "manual",
                        "name": "خدمة تغليف",
                        "description": "تغليف هدايا",
                        "quantity": 1,
                        "unit_price": "15.00",
                    },
                    {
                        "kind": "manual",
                        "name": "خدمة تغليف",
                        "description": "تغليف إضافي - صف مكرر الاسم",
                        "quantity": 2,
                        "unit_price": "15.00",
                    },
                ],
            )
            record(manual_items_only, "manual order, manual items only, duplicate names")

            # Mixed catalog + manual, price override, discount, delivery fee, notes.
            mixed = manual_order(
                "mixed",
                source="whatsapp",
                customer_name="طلب مختلط",
                discount="10.00",
                delivery_fee="20.00",
                customer_notes="ملاحظة الزبون",
                items=[
                    {
                        "kind": "catalog",
                        "product_id": clear,
                        "quantity": 2,
                        "unit_price": "110.00",  # order-only price override
                    },
                    {
                        "kind": "manual",
                        "name": "نقش بالليزر",
                        "quantity": 1,
                        "unit_price": "40.00",
                    },
                ],
            )
            record(mixed, "manual mixed order with price override, discount and delivery fee")

            # Manual order completed immediately -> invoice with issuer snapshot.
            immediate = manual_order(
                "immediate-complete",
                source="walk_in",
                customer_name="بيع مباشر",
                completion={
                    "payment_method": "cash_on_delivery",
                    "paid_amount": "45.00",
                    "payment_details": "دفع نقدي كامل عند الاستلام",
                },
            )
            record(immediate, "manual order completed at creation")
            detail = client.get(
                f"/api/v1/admin/orders/{immediate['id']}", headers=manager
            ).json()
            if detail.get("active_invoice"):
                manifest["invoices"].append(
                    {
                        "invoice_number": detail["active_invoice"]["invoice_number"],
                        "scenario": "active / paid / issued from a manual walk-in order",
                    }
                )
    finally:
        app.dependency_overrides.clear()

    _force_legacy_cancelled_invoice(session_factory, manifest)
    return manifest


def _force_legacy_cancelled_invoice(session_factory: sessionmaker, manifest: dict) -> None:
    """Write the one invoice state the current API cannot reach.

    Kept out of the API section on purpose, and clearly marked, so nobody reads this as
    evidence that cancellation works from the invoice screen — it does not.
    """
    from app.core.enums import InvoiceStatus
    from app.models import AdminUser, Invoice

    number = manifest.get("legacy_cancelled_invoice")
    if not number:
        return

    with session_factory() as db:
        invoice = db.execute(
            select(Invoice).where(Invoice.invoice_number == number)
        ).scalar_one()
        manager = db.execute(
            select(AdminUser).where(AdminUser.email == SUPER_ADMIN_EMAIL)
        ).scalar_one()

        invoice.status = InvoiceStatus.CANCELLED.value
        # Archived rows must release the marker or the one-active-invoice unique pair
        # would still count this row as the order's live invoice.
        invoice.active_invoice_marker = None
        invoice.cancelled_at = datetime.utcnow()
        invoice.cancellation_reason = "سجل قديم: فاتورة ملغاة قبل قفل الطلبات المكتملة"
        invoice.cancelled_by_admin_id = manager.id
        db.commit()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", required=True)
    args = parser.parse_args(argv)

    _guard_database_url(args.database_url)

    # The engine must exist before app.main imports resolve the session factory.
    import os

    os.environ["DATABASE_URL"] = args.database_url

    from app.core.config import get_settings

    get_settings.cache_clear()
    import app.core.config as config_module

    config_module.settings = get_settings()

    from app.db.session import build_engine

    engine = build_engine(args.database_url)
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)

    import app.db.session as session_module

    session_module.engine = engine
    session_module.SessionLocal = factory

    with factory() as db:
        guard_not_already_seeded(db)
        seed_store_settings(db)
        seed_admins(db)
        seed_media(db)
        ids = seed_catalog(db)
        seed_content(db)
        ids.update(seed_promotions(db))

    manifest = seed_orders_and_invoices(factory, ids)

    print(f"database   : {args.database_url}")
    print(f"categories : {sum(1 for k in ids if k.startswith('category:'))}")
    print(f"products   : {sum(1 for k in ids if k.startswith('product:'))}")
    print(f"coupons    : {sum(1 for k in ids if k.startswith('coupon:'))}")
    print(f"zones      : {sum(1 for k in ids if k.startswith('zone:'))}")
    print(f"orders     : {len(manifest['orders'])}")
    print(f"invoices   : {len(manifest['invoices'])}")
    for row in manifest["orders"]:
        print(f"  order   {row['order_number']:<20} {row['scenario']}")
    for row in manifest["invoices"]:
        print(f"  invoice {row['invoice_number']:<20} {row['scenario']}")
    engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
