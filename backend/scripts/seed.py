"""DEMO SEED — development and demonstration only. Never run against a client store.

Creates enough content to demonstrate every part of the storefront and the admin
area: sample categories, products, variants, packages, coupons, a demo
order and demo store identity. Re-running it updates the same rows instead of
duplicating them — every entity is matched on its natural key (slug, code, name or
section key) — and it deliberately rewrites its own seeded content, including
resetting seeded product stock.

    python -m scripts.seed

This is one of two separate initialization workflows:

  demo seed        (here)                    sample commercial data, for development
  client bootstrap (scripts.instance_cli)    store identity and structural defaults
                                             only — no products, orders or coupons,
                                             and it never overwrites owner edits

A real client instance gets `instance_cli apply`, not this. See
docs/client-lifecycle.md.

An admin account is only created when credentials are supplied explicitly, through
--admin-email/--admin-password or INITIAL_ADMIN_EMAIL/INITIAL_ADMIN_PASSWORD.
"""

from __future__ import annotations

import argparse
import sys
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.enums import (
    AdminRole,
    DiscountType,
    HomeSectionType,
    ProductType,
    StorageProviderName,
)
from app.db.base import utcnow
from app.db.session import SessionLocal
from app.initial_data import upsert_admin
from app.models import (
    Category,
    Coupon,
    DeliveryArea,
    HeroSlide,
    HomeSection,
    MediaAsset,
    Order,
    PackageItem,
    Product,
    ProductImage,
    ProductOption,
    ProductOptionValue,
    ProductSpecification,
    ProductVariant,
    StaticPage,
)
from app.services import catalog as catalog_service
from app.services import orders as orders_service
from app.services import store_settings as settings_service
from app.services.placeholder_image import gradient_png, hex_to_rgb

# Palette carried over from the storefront design so seeded artwork matches the theme.
TONES: dict[str, tuple[str, str]] = {
    "teal": ("#e8f0ef", "#7fa9a3"),
    "sand": ("#f1ece5", "#c2ab86"),
    "rose": ("#f3e9ea", "#cfa3aa"),
    "cream": ("#f6efe4", "#d9bd86"),
    "lilac": ("#eceaf2", "#a9a2c6"),
    "steel": ("#eaeced", "#a3b0b6"),
    "olive": ("#eef1e9", "#adbd96"),
    "clay": ("#f2e8e2", "#c49a80"),
    "mint": ("#e9f2ec", "#96c1a8"),
    "stone": ("#eeece8", "#b3aa9a"),
    "hero-teal": ("#1f4e4a", "#c9a24b"),
    "hero-clay": ("#3a2a22", "#e8d8bd"),
    "hero-slate": ("#2b2f3a", "#d3cfe2"),
}

IMAGE_SIZES = {"tile": (640, 800), "wide": (1280, 640)}

CATEGORIES = [
    ("resin", "إيبوكسي ريزن", "teal", True, "راتنجات شفافة ومصلّبات للمشاريع الحرفية."),
    ("candle-making", "صناعة الشمع", "cream", True, "شمع صويا ونحل وفتائل جاهزة للاستخدام."),
    ("fragrances", "صناعة المعطرات", "lilac", True, "قواعد معطرات وزجاجات ومضخات."),
    ("terrazzo", "تيرازو وكونكريت", "steel", True, "مساحيق ورقائق للتيرازو والكونكريت."),
    ("clock-boards", "أخشاب ومستلزمات الساعات", "sand", True, "قواعد ومكائن ومؤشرات ساعات."),
    ("candle-containers", "أكواب الشمع", "mint", True, "أوعية زجاج ومعدن وخشب وفخار."),
    ("starter-kits", "بكجات المبتدئين", "olive", True, "أطقم كاملة جاهزة لبدء المشروع."),
    ("pigments", "صبغات وملونات", "rose", True, "مايكا وألوان ميتاليك وملونات شمع."),
    ("silicone-molds", "قوالب سيليكون", "clay", True, "قوالب للريزن والشمع والتيرازو."),
    ("tools", "مستلزمات وأدوات عمل", "stone", True, "موازين وأدوات خلط ومسدسات حرارية."),
    ("packaging", "منتجات تغليف", "stone", False, "علب وأكياس وورق تغليف وستيكرز."),
]

SUBCATEGORIES = [
    ("resin-fast-cure", "ريزن سريع الجفاف", "resin", "teal"),
    ("resin-deep-pour", "ريزن للسماكات العالية", "resin", "teal"),
    ("molds-for-candles", "قوالب شمع", "silicone-molds", "clay"),
    ("molds-for-resin", "قوالب ريزن", "silicone-molds", "clay"),
]

# slug, name, category, type, price, compare_at, stock, flags (f/n/b), tone
PRODUCTS = [
    ("resin-clear-1kg", "ريزن إيبوكسي شفاف سريع الجفاف — ١ كغم", "resin", ProductType.STANDARD, "119.00", "145.00", 40, "fn", "teal"),
    ("resin-deep-15kg", "ريزن إيبوكسي للسماكات العالية — ١.٥ كغم", "resin", ProductType.STANDARD, "229.00", "265.00", 25, "f", "teal"),
    ("resin-uv-500g", "ريزن مقاوم للاصفرار UV — ٥٠٠ غم", "resin", ProductType.STANDARD, "89.00", None, 30, "", "teal"),
    ("resin-hardener-500ml", "مصلّب إضافي للريزن — ٥٠٠ مل", "resin", ProductType.STANDARD, "62.00", None, 18, "", "teal"),
    ("soy-wax-2kg", "شمع صويا طبيعي — ٢ كغم", "candle-making", ProductType.STANDARD, "84.00", "98.00", 50, "fb", "cream"),
    ("beeswax-1kg", "شمع نحل مصفّى — ١ كغم", "candle-making", ProductType.STANDARD, "99.00", "124.00", 22, "n", "cream"),
    ("cotton-wicks-100", "فتائل قطنية مشمّعة — ١٠٠ فتيلة", "candle-making", ProductType.STANDARD, "32.00", None, 80, "b", "cream"),
    ("diffuser-base-1l", "قاعدة معطر جو كحولية — ١ لتر", "fragrances", ProductType.STANDARD, "55.00", "68.00", 26, "f", "lilac"),
    ("diffuser-bottles-6", "زجاجات معطر بمضخة — ٦ حبات", "fragrances", ProductType.STANDARD, "54.00", None, 34, "", "lilac"),
    ("terrazzo-white-5kg", "مسحوق ماستر تيرازو أبيض — ٥ كغم", "terrazzo", ProductType.STANDARD, "95.00", "110.00", 16, "f", "steel"),
    ("terrazzo-chips-1kg", "رقائق تيرازو ملونة — ١ كغم", "terrazzo", ProductType.STANDARD, "42.00", None, 28, "", "steel"),
    ("clock-board-57", "قاعدة ساعة خشبية دائرية — قطر ٥٧ سم", "clock-boards", ProductType.STANDARD, "40.00", None, 14, "f", "sand"),
    ("moon-board-37", "خشبة القمر المضيء — قطر ٣٧ سم مع إضاءة", "clock-boards", ProductType.STANDARD, "49.00", "60.00", 9, "n", "sand"),
    ("clock-mechanism", "ماكينة ساعة صامتة مع مؤشرات", "clock-boards", ProductType.STANDARD, "18.00", None, 60, "b", "sand"),
    ("glass-vessels-6", "أوعية زجاجية مضلعة — ٦ حبات", "candle-containers", ProductType.STANDARD, "87.00", None, 20, "", "mint"),
    ("metal-vessels-6", "أوعية معدنية بغطاء ذهبي — ٦ حبات", "candle-containers", ProductType.STANDARD, "78.00", "96.00", 12, "f", "mint"),
    ("mica-set-12", "مجموعة أصباغ ميكا لامعة — ١٢ لون", "pigments", ProductType.STANDARD, "89.00", "115.00", 33, "fb", "rose"),
    ("metallic-paste-6", "ألوان ميتاليك معجون — ٦ درجات", "pigments", ProductType.STANDARD, "68.00", None, 21, "", "rose"),
    ("wax-dyes-8", "ملونات شمع سائلة — ٨ درجات", "pigments", ProductType.STANDARD, "45.00", "54.00", 0, "n", "rose"),
    ("digital-scale", "ميزان رقمي دقيق ٠.٠١ غم", "tools", ProductType.STANDARD, "96.00", None, 17, "fb", "stone"),
    ("mixing-tools-14", "طقم أدوات خلط وتشكيل — ١٤ قطعة", "tools", ProductType.STANDARD, "61.00", "74.00", 24, "n", "stone"),
    ("heat-gun-2000w", "مسدس حراري احترافي ٢٠٠٠ واط", "tools", ProductType.STANDARD, "155.00", "189.00", 7, "", "stone"),
    ("pvc-boxes-50", "علب PVC شفافة — ٥٠ علبة", "packaging", ProductType.STANDARD, "46.00", None, 45, "", "stone"),
    ("organza-bags-100", "أكياس أورجانزا — ١٠٠ كيس", "packaging", ProductType.STANDARD, "27.00", "34.00", 38, "f", "stone"),
    ("mold-coaster-rect", "قالب سيليكون كوستر مستطيل سادة", "silicone-molds", ProductType.SILICONE_MOLD, "10.00", None, 65, "f", "clay"),
    ("mold-heart-frame", "قالب سيليكون إطار صورة شكل قلب", "silicone-molds", ProductType.SILICONE_MOLD, "15.00", None, 40, "n", "clay"),
    ("mold-cube-10", "قالب سيليكون مكعب شفاف ١٠ سم مع دعامات", "silicone-molds", ProductType.SILICONE_MOLD, "16.00", "20.00", 28, "fb", "clay"),
    ("mold-lotus-bowl", "قالب سيليكون وعاء زهرة اللوتس", "silicone-molds", ProductType.SILICONE_MOLD, "6.00", None, 52, "", "clay"),
    ("mold-arabic-letters", "قالب حروف عربية بارزة", "silicone-molds", ProductType.SILICONE_MOLD, "52.00", "68.00", 11, "", "clay"),
    ("kit-resin-decor", "بكج صناعة قطع ديكور من الريزن", "starter-kits", ProductType.PACKAGE, "119.00", "140.00", 15, "fnb", "olive"),
    ("kit-candle-decor", "بكج صناعة شمع الديكور", "starter-kits", ProductType.PACKAGE, "120.00", None, 12, "f", "olive"),
]

SHORT_DESCRIPTION = (
    "منتج حرفي مختار بعناية، مناسب للمشاريع اليدوية والاستخدام التجاري الخفيف. "
    "يُشحن بتغليف محكم يحمي المحتوى، ومعه ورقة إرشادات بالعربية."
)

DESCRIPTION = (
    "يُنصح باستخدام المنتج في مكان جيد التهوية وبدرجة حرارة بين ٢٠ و٢٥ مئوية للحصول على "
    "أفضل نتيجة. تجنّب الخلط السريع لتقليل الفقاعات، واترك الخليط دقيقتين قبل الصب."
)

DEFAULT_SPECS = [
    ("البلد المنشأ", "مستورد"),
    ("مدة الصلاحية", "٢٤ شهراً"),
    ("التغليف", "علبة محكمة مع ورقة إرشادات"),
    ("الاستخدام", "حرفي ومنزلي"),
]

PRODUCT_SPECS = {
    "resin-clear-1kg": [
        ("نسبة الخلط", "٢:١ بالوزن"),
        ("زمن العمل", "٣٠ دقيقة"),
        ("زمن الجفاف الكامل", "٢٤ ساعة"),
        ("البلد المنشأ", "مستورد"),
    ],
    "mold-cube-10": [
        ("أبعاد القالب", "١٠ × ١٠ × ١٠ سم"),
        ("سماكة الجدار", "٨ مم"),
        ("درجة الصلابة", "شور A 25"),
        ("عدد الدعامات", "٤ دعامات"),
    ],
    "mold-arabic-letters": [
        ("أبعاد القالب", "٢٤ × ١٢ سم"),
        ("ارتفاع الحرف", "٤ سم"),
        ("عدد الحروف", "٢٨ حرفاً"),
    ],
}

# product slug -> option name -> values
PRODUCT_OPTIONS = {
    "resin-clear-1kg": {"الحجم": ["٥٠٠ غم", "١ كغم", "١.٥ كغم"]},
    "mica-set-12": {"اللون": ["ذهبي", "فضي", "نحاسي"]},
    "mold-coaster-rect": {"المقاس": ["صغير", "وسط", "كبير"]},
}

# product slug -> [(variant title, option values, price override, stock)]
PRODUCT_VARIANTS = {
    "resin-clear-1kg": [
        ("٥٠٠ غم", ["٥٠٠ غم"], "69.00", 12),
        ("١ كغم", ["١ كغم"], None, 20),
        ("١.٥ كغم", ["١.٥ كغم"], "169.00", 8),
    ],
    "mica-set-12": [
        ("ذهبي", ["ذهبي"], None, 12),
        ("فضي", ["فضي"], None, 11),
        ("نحاسي", ["نحاسي"], None, 10),
    ],
    "mold-coaster-rect": [
        ("صغير", ["صغير"], "8.00", 25),
        ("وسط", ["وسط"], None, 25),
        ("كبير", ["كبير"], "13.00", 15),
    ],
}

PACKAGE_CONTENTS = {
    "kit-resin-decor": [
        ("resin-clear-1kg", 1, "ريزن + مصلّب"),
        ("mold-coaster-rect", 2, "قوالب سيليكون"),
        ("mica-set-12", 1, "أصباغ ميكا"),
        ("mixing-tools-14", 1, "أدوات خلط"),
    ],
    "kit-candle-decor": [
        ("soy-wax-2kg", 1, "شمع صويا"),
        ("cotton-wicks-100", 1, "فتائل مشمّعة"),
        ("glass-vessels-6", 1, "أوعية زجاج"),
        ("wax-dyes-8", 1, "ملونات شمع"),
    ],
}

HERO_SLIDES = [
    (
        "كل مستلزمات الريزن والشمع في مكان واحد",
        "تشكيلة جديدة",
        "ريزن، قوالب، أصباغ وأدوات بجودة احترافية وأسعار الجملة.",
        "تسوّق الآن",
        "/shop",
        "hero-teal",
    ),
    (
        "بكجات المبتدئين بخصم يصل ٢٠٪",
        "عرض هذا الأسبوع",
        "ابدأ مشروعك الحرفي بطقم كامل جاهز للاستخدام.",
        "شاهد البكجات",
        "/packages",
        "hero-clay",
    ),
    (
        "أكبر تشكيلة قوالب سيليكون",
        "وصل حديثاً",
        "أكثر من ٢٠٠ قالب للريزن والشمع والتيرازو.",
        "تصفّح القوالب",
        "/molds",
        "hero-slate",
    ),
]

HOME_SECTIONS = [
    ("categories", HomeSectionType.CATEGORIES, "أقسام منتجاتنا", "تسوّق حسب القسم", 1, {"limit": 12}),
    ("packages", HomeSectionType.PACKAGES, "بكجات المبتدئين", "ابدأ من هنا", 2, {"limit": 8}),
    ("molds", HomeSectionType.SILICONE_MOLDS, "قوالب سيليكون", "أكبر تشكيلة قوالب سيليكون", 3, {"limit": 4}),
    ("featured", HomeSectionType.FEATURED_PRODUCTS, "منتجات مختارة", "اختيارات فريق الورشة", 4, {"limit": 8}),
    ("new-and-best", HomeSectionType.NEW_PRODUCTS, "منتجات جديدة", "وصل حديثاً", 5, {"limit": 8}),
    ("bestsellers", HomeSectionType.BESTSELLERS, "الأكثر مبيعاً", "ما يطلبه الحرفيون أكثر", 6, {"limit": 8}),
    ("workshop-note", HomeSectionType.CUSTOM_TEXT, "من الورشة", "نختبر كل منتج قبل إضافته إلى المتجر.", 7, {"body": "منتجات جديدة، وعروض خاصة."}),
]

COUPONS = [
    ("WELCOME10", "خصم ١٠٪ على أول طلب", DiscountType.PERCENTAGE, "10", "100.00", "50.00", 500),
    ("SAVE25", "خصم ٢٥ على الطلبات فوق ٢٥٠", DiscountType.FIXED, "25", "250.00", None, 200),
]

DELIVERY_AREAS = [
    ("رام الله والبيرة", "20.00", "750.00", "١–٢ أيام عمل", 0),
    ("نابلس", "25.00", "750.00", "٢–٣ أيام عمل", 1),
    ("الخليل", "25.00", "750.00", "٢–٣ أيام عمل", 2),
    ("القدس", "30.00", "900.00", "٢–٤ أيام عمل", 3),
    ("غزة", "35.00", None, "٣–٥ أيام عمل", 4),
]

STATIC_PAGES = [
    (
        "about",
        "موقع الشركة",
        "متجر حرفي متخصص في مستلزمات الريزن والشمع، نخدم الحرفيين وأصحاب المشاريع الصغيرة.",
        "بدأنا كورشة صغيرة تصنع قطعاً بالطلب، ثم تحوّلنا إلى مورّد للمواد التي كنا نبحث عنها بأنفسنا.\n\n"
        "نختبر كل منتج داخل الورشة قبل إضافته للمتجر، ونكتب إرشادات استخدام بالعربية مع كل طلب.\n\n"
        "نوفّر أسعار جملة لأصحاب المشاريع، وندعم العملاء فنياً في اختيار المواد المناسبة.",
    ),
    (
        "privacy-policy",
        "سياسة الخصوصية",
        "نحفظ بياناتك بالحد الأدنى اللازم لتنفيذ الطلب.",
        "نجمع الاسم ورقم الهاتف والعنوان لغرض التوصيل فقط، ولا نشارك هذه البيانات مع أي طرف ثالث خارج شركة الشحن.\n\n"
        "لا نحفظ بيانات بطاقات الدفع؛ الدفع في هذا المتجر عند الاستلام أو بتحويل يدوي.\n\n"
        "يمكنك طلب حذف بياناتك في أي وقت عبر صفحة تواصل معنا.",
    ),
    (
        "return-policy",
        "سياسة التبديل والإرجاع",
        "لا يمكن استبدال أو إرجاع المنتجات بعد تأكيد الطلب أو استلامه.",
        "نظراً لطبيعة منتجات تارا وحساسية القطع، وكونها مصنوعة ومجهزة يدوياً بعناية، لا يمكن استبدال أو إرجاع المنتجات بعد تأكيد الطلب أو استلامه.\n\n"
        "ولا تعد الاختلافات البسيطة والطبيعية في اللون أو الشكل أو القياس أو التفاصيل الناتجة عن طبيعة التصنيع اليدوي عيباً أو تلفاً في المنتج.\n\n"
        "نرجو التأكد من تفاصيل المنتج والمواصفات المطلوبة قبل تأكيد الطلب.",
    ),
    (
        "terms",
        "الشروط والأحكام",
        "استخدامك للمتجر يعني موافقتك على الشروط التالية.",
        "الأسعار المعروضة تشمل الضريبة، وقد تتغيّر دون إشعار مسبق.\n\n"
        "توفّر المنتجات مرتبط بالمخزون الفعلي؛ في حال نفاد منتج بعد الطلب نتواصل معك لاختيار بديل.\n\n"
        "الصور توضيحية وقد تختلف درجة اللون قليلاً بين الدفعات الإنتاجية.",
    ),
    (
        "shipping-policy",
        "سياسة الشحن",
        "نوصل لكل المناطق خلال ١–٤ أيام عمل.",
        "تُحسب رسوم التوصيل حسب المنطقة المختارة عند إتمام الطلب.\n\n"
        "التوصيل مجاني عند تجاوز الحد الموضح لكل منطقة.\n\n"
        "يتواصل معك المندوب قبل التسليم بساعة تقريباً.",
    ),
    (
        "contact",
        "اتصل بنا",
        "فريق الدعم متاح خلال ساعات العمل — نرد عادة خلال ساعتين في أيام العمل.",
        "للاستفسارات الفنية حول اختيار المواد، تواصل معنا عبر واتساب أو الهاتف.\n\n"
        "لطلبات الجملة، أرسل قائمة المنتجات والكميات وسنرد بعرض سعر خلال يوم عمل.",
    ),
]


# ── helpers ──────────────────────────────────────────────────────────────────
def _log(message: str) -> None:
    print(f"  {message}")


def ensure_media(db: Session) -> dict[str, str]:
    """Generate gradient artwork on disk once and register it as MediaAssets."""
    if settings.STORAGE_PROVIDER != StorageProviderName.LOCAL.value:
        _log("storage provider is not local; skipping seeded artwork")
        return {}

    root = settings.media_root
    root.mkdir(parents=True, exist_ok=True)
    base_url = settings.LOCAL_MEDIA_BASE_URL.rstrip("/")
    urls: dict[str, str] = {}

    for tone, (start, end) in TONES.items():
        size = IMAGE_SIZES["wide"] if tone.startswith("hero-") else IMAGE_SIZES["tile"]
        key = f"seed-{tone}.png"
        path = root / key
        if not path.exists():
            path.write_bytes(gradient_png(*size, hex_to_rgb(start), hex_to_rgb(end)))

        url = f"{base_url}/{key}"
        urls[tone] = url
        asset = db.execute(
            select(MediaAsset).where(MediaAsset.stored_key == key)
        ).scalar_one_or_none()
        if asset is None:
            db.add(
                MediaAsset(
                    original_filename=f"{tone}-placeholder.png",
                    stored_key=key,
                    content_type="image/png",
                    size_bytes=path.stat().st_size,
                    url=url,
                    storage_provider=StorageProviderName.LOCAL.value,
                )
            )
        else:
            asset.url = url
            asset.size_bytes = path.stat().st_size
    db.flush()
    _log(f"artwork: {len(urls)} placeholder images")
    return urls


def ensure_settings(db: Session, images: dict[str, str]) -> None:
    row = settings_service.get_or_create_settings(db)
    row.store_name = row.store_name if row.store_name not in ("", "Store") else "متجر تجريبي"
    row.store_tagline = row.store_tagline or "مستلزمات الريزن والشموع"
    row.logo_url = row.logo_url or images.get("hero-teal")
    row.phone = row.phone or "0000000000"
    row.whatsapp = row.whatsapp or "0000000000"
    row.email = row.email or "info@example.com"
    row.address = row.address or "العنوان يُضبط من لوحة التحكم"
    row.working_hours = row.working_hours or "السبت – الخميس · ٩:٠٠ – ١٩:٠٠"
    row.announcement = row.announcement or "توصيل مجاني للطلبات فوق ٧٥٠"
    row.instagram_url = row.instagram_url or "https://instagram.com/"
    row.facebook_url = row.facebook_url or "https://facebook.com/"
    row.currency_code = row.currency_code or "ILS"
    row.currency_symbol = row.currency_symbol or "₪"
    row.seo_title = row.seo_title or "متجر تجريبي — مستلزمات الريزن والشموع"
    row.seo_description = row.seo_description or (
        "مواد وأدوات الريزن والشمع والتيرازو بأسعار الجملة مع إرشادات بالعربية."
    )
    db.flush()
    _log("store settings")


def ensure_categories(db: Session, images: dict[str, str]) -> dict[str, Category]:
    result: dict[str, Category] = {}
    for order, (slug, name, tone, featured, description) in enumerate(CATEGORIES):
        category = db.execute(
            select(Category).where(Category.slug == slug)
        ).scalar_one_or_none()
        if category is None:
            category = Category(slug=slug)
            db.add(category)
        category.name = name
        category.description = description
        category.image_url = images.get(tone)
        category.is_active = True
        category.is_featured = featured
        category.sort_order = order
        result[slug] = category
    db.flush()

    for order, (slug, name, parent_slug, tone) in enumerate(SUBCATEGORIES):
        category = db.execute(
            select(Category).where(Category.slug == slug)
        ).scalar_one_or_none()
        if category is None:
            category = Category(slug=slug)
            db.add(category)
        category.name = name
        category.parent_id = result[parent_slug].id
        category.image_url = images.get(tone)
        category.is_active = True
        category.is_featured = False
        category.sort_order = order
        result[slug] = category
    db.flush()
    _log(f"categories: {len(result)}")
    return result


def ensure_products(
    db: Session, categories: dict[str, Category], images: dict[str, str]
) -> dict[str, Product]:
    result: dict[str, Product] = {}
    for order, row in enumerate(PRODUCTS):
        slug, name, category_slug, ptype, price, compare_at, stock, flags, tone = row
        product = db.execute(select(Product).where(Product.slug == slug)).scalar_one_or_none()
        if product is None:
            product = Product(slug=slug)
            db.add(product)
        product.name = name
        product.category_id = categories[category_slug].id
        product.product_type = ptype.value
        product.short_description = SHORT_DESCRIPTION
        product.description = DESCRIPTION
        product.sku = f"{category_slug[:3].upper()}-{1000 + order}"
        product.price = Decimal(price)
        product.compare_at_price = Decimal(compare_at) if compare_at else None
        product.cost_price = (Decimal(price) * Decimal("0.65")).quantize(Decimal("0.01"))
        product.stock_quantity = stock
        product.track_inventory = True
        product.low_stock_threshold = 5
        product.is_active = True
        product.is_featured = "f" in flags
        product.is_new = "n" in flags
        product.is_bestseller = "b" in flags
        product.sort_order = order
        product.seo_title = name
        product.seo_description = SHORT_DESCRIPTION[:150]
        catalog_service.refresh_search_text(product)
        db.flush()

        image_url = images.get(tone)
        if image_url and not product.images:
            db.add(
                ProductImage(
                    product_id=product.id,
                    url=image_url,
                    alt_text=name,
                    sort_order=0,
                )
            )

        specs = PRODUCT_SPECS.get(slug, DEFAULT_SPECS)
        if not product.specifications:
            for spec_order, (spec_name, spec_value) in enumerate(specs):
                db.add(
                    ProductSpecification(
                        product_id=product.id,
                        name=spec_name,
                        value=spec_value,
                        sort_order=spec_order,
                    )
                )
        result[slug] = product
    db.flush()
    _log(f"products: {len(result)}")
    return result


def ensure_options_and_variants(db: Session, products: dict[str, Product]) -> None:
    variant_count = 0
    for slug, options in PRODUCT_OPTIONS.items():
        product = products[slug]
        values_by_name: dict[str, ProductOptionValue] = {}
        for order, (option_name, values) in enumerate(options.items()):
            option = db.execute(
                select(ProductOption).where(
                    ProductOption.product_id == product.id, ProductOption.name == option_name
                )
            ).scalar_one_or_none()
            if option is None:
                option = ProductOption(product_id=product.id, name=option_name, sort_order=order)
                db.add(option)
                db.flush()
            existing = {value.value: value for value in option.values}
            for value_order, value in enumerate(values):
                row = existing.get(value)
                if row is None:
                    row = ProductOptionValue(
                        option_id=option.id, value=value, sort_order=value_order
                    )
                    db.add(row)
                    db.flush()
                values_by_name[value] = row

        for title, value_names, price_override, stock in PRODUCT_VARIANTS.get(slug, []):
            variant = db.execute(
                select(ProductVariant).where(
                    ProductVariant.product_id == product.id, ProductVariant.title == title
                )
            ).scalar_one_or_none()
            if variant is None:
                variant = ProductVariant(product_id=product.id, title=title)
                db.add(variant)
            variant.sku = f"{product.sku}-{len(title)}{abs(hash(title)) % 97:02d}"
            variant.price_override = Decimal(price_override) if price_override else None
            variant.stock_quantity = stock
            variant.is_active = True
            variant.option_values = [
                values_by_name[name] for name in value_names if name in values_by_name
            ]
            variant_count += 1
    db.flush()
    _log(f"product options and variants: {variant_count} variants")


def ensure_packages(db: Session, products: dict[str, Product]) -> None:
    count = 0
    for package_slug, contents in PACKAGE_CONTENTS.items():
        package = products[package_slug]
        for order, (included_slug, quantity, note) in enumerate(contents):
            included = products[included_slug]
            item = db.execute(
                select(PackageItem).where(
                    PackageItem.package_product_id == package.id,
                    PackageItem.included_product_id == included.id,
                )
            ).scalar_one_or_none()
            if item is None:
                item = PackageItem(
                    package_product_id=package.id, included_product_id=included.id
                )
                db.add(item)
            item.quantity = quantity
            item.display_note = note
            item.sort_order = order
            count += 1
    db.flush()
    _log(f"package contents: {count} items")


def ensure_hero_slides(db: Session, images: dict[str, str]) -> None:
    for order, (title, subtitle, description, label, url, tone) in enumerate(HERO_SLIDES):
        slide = db.execute(
            select(HeroSlide).where(HeroSlide.title == title)
        ).scalar_one_or_none()
        if slide is None:
            slide = HeroSlide(title=title)
            db.add(slide)
        slide.subtitle = subtitle
        slide.description = description
        slide.button_label = label
        slide.button_url = url
        slide.image_url = images.get(tone)
        slide.is_active = True
        slide.sort_order = order
    db.flush()
    _log(f"hero slides: {len(HERO_SLIDES)}")


def ensure_home_sections(db: Session) -> None:
    for key, section_type, title, description, order, config in HOME_SECTIONS:
        section = db.execute(
            select(HomeSection).where(HomeSection.section_key == key)
        ).scalar_one_or_none()
        if section is None:
            section = HomeSection(section_key=key)
            db.add(section)
        section.section_type = section_type.value
        section.title = title
        section.description = description
        section.sort_order = order
        section.config = config
        if section.is_visible is None:
            section.is_visible = True
    db.flush()
    _log(f"home sections: {len(HOME_SECTIONS)}")


def ensure_coupons(db: Session) -> None:
    now = utcnow()
    for code, description, dtype, value, min_order, max_discount, limit in COUPONS:
        coupon = db.execute(select(Coupon).where(Coupon.code == code)).scalar_one_or_none()
        if coupon is None:
            coupon = Coupon(code=code)
            db.add(coupon)
        coupon.description = description
        coupon.discount_type = dtype.value
        coupon.discount_value = Decimal(value)
        coupon.min_order_amount = Decimal(min_order)
        coupon.max_discount_amount = Decimal(max_discount) if max_discount else None
        coupon.usage_limit = limit
        coupon.starts_at = now - timedelta(days=1)
        coupon.ends_at = now + timedelta(days=365)
        coupon.is_active = True
    db.flush()
    _log(f"coupons: {len(COUPONS)}")


def ensure_delivery_areas(db: Session) -> None:
    for name, fee, free_threshold, eta, order in DELIVERY_AREAS:
        area = db.execute(
            select(DeliveryArea).where(DeliveryArea.name == name)
        ).scalar_one_or_none()
        if area is None:
            area = DeliveryArea(name=name)
            db.add(area)
        area.delivery_fee = Decimal(fee)
        area.free_delivery_threshold = Decimal(free_threshold) if free_threshold else None
        area.estimated_days = eta
        area.is_active = True
        area.sort_order = order
    db.flush()
    _log(f"delivery areas: {len(DELIVERY_AREAS)}")


def ensure_pages(db: Session) -> None:
    for slug, title, lead, content in STATIC_PAGES:
        page = db.execute(select(StaticPage).where(StaticPage.slug == slug)).scalar_one_or_none()
        if page is None:
            page = StaticPage(slug=slug)
            db.add(page)
        page.title = title
        page.lead = lead
        page.content = content
        page.is_published = True
        page.seo_title = title
        page.seo_description = lead[:150]
    db.flush()
    _log(f"static pages: {len(STATIC_PAGES)}")


def ensure_demo_order(db: Session, products: dict[str, Product]) -> None:
    """One example order so the admin order screens are not empty on a fresh install."""
    existing = db.execute(
        select(func.count()).select_from(Order).where(Order.customer_name == "عميل تجريبي")
    ).scalar_one()
    if existing:
        _log("demo order: already present")
        return

    area = db.execute(
        select(DeliveryArea).order_by(DeliveryArea.sort_order.asc())
    ).scalars().first()
    draft = orders_service.OrderDraft(
        customer_name="عميل تجريبي",
        customer_phone="0591234567",
        address="رام الله — شارع الإرسال، بناية ٥",
        delivery_area_id=area.id if area else None,
        customer_notes="طلب تجريبي أنشأه أمر التهيئة.",
        items=[
            (products["resin-clear-1kg"].id, None, 1),
            (products["mold-coaster-rect"].id, None, 2),
        ],
    )
    order = orders_service.create_order(db, draft)
    db.flush()
    _log(f"demo order: {order.order_number}")


def maybe_create_admin(db: Session, email: str, password: str, name: str) -> None:
    if not email or not password:
        _log(
            "admin: skipped (supply --admin-email/--admin-password or "
            "INITIAL_ADMIN_EMAIL/INITIAL_ADMIN_PASSWORD to create one)"
        )
        return
    account, created = upsert_admin(
        db,
        email=email,
        password=password,
        full_name=name,
        role=AdminRole.SUPER_ADMIN.value,
    )
    _log(f"admin: {'created' if created else 'updated'} {account.email}")


def seed(db: Session, *, admin_email: str, admin_password: str, admin_name: str) -> None:
    images = ensure_media(db)
    ensure_settings(db, images)
    categories = ensure_categories(db, images)
    products = ensure_products(db, categories, images)
    ensure_options_and_variants(db, products)
    ensure_packages(db, products)
    ensure_hero_slides(db, images)
    ensure_home_sections(db)
    ensure_coupons(db)
    ensure_delivery_areas(db)
    ensure_pages(db)
    ensure_demo_order(db, products)
    maybe_create_admin(db, admin_email, admin_password, admin_name)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "DEMO SEED (idempotent) — development and demonstration only. "
            "For a real client instance use: python -m scripts.instance_cli apply."
        )
    )
    parser.add_argument("--admin-email", default=settings.INITIAL_ADMIN_EMAIL)
    parser.add_argument("--admin-password", default=settings.INITIAL_ADMIN_PASSWORD)
    parser.add_argument("--admin-name", default=settings.INITIAL_ADMIN_NAME)
    args = parser.parse_args(argv)

    print("Seeding demo data...")
    with SessionLocal() as db:
        seed(
            db,
            admin_email=args.admin_email,
            admin_password=args.admin_password,
            admin_name=args.admin_name,
        )
        db.commit()
    print("Done.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
