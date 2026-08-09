"""Spreadsheet -> canonical dataset.

The output of this module is an ordinary preview dataset document: the same YAML shape
`scripts.preview_cli` already validates, plans, seeds and purges. Nothing new imports
anything; this only prepares the file an operator then feeds to the existing importer.

Three things it is careful about.

**It never guesses.** A value it cannot read is an error naming the sheet, the row and
the column. A filename that matches no Media Library file, or more than one, is an error.
Nothing is silently dropped, coerced or picked between.

**It never leaks storage.** Images are referenced by the filename the owner uploaded
them under. No URL, bucket key, local path or provider name reaches the generated file —
the importer resolves the filename against the Media Library when it runs.

**Order is meaning.** `image_1` is the cover. The generated `images:` list keeps
spreadsheet order, and the importer turns that order into `sort_order`, so the first
column named in the spreadsheet is the picture the storefront leads with.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

import yaml
from sqlalchemy.orm import Session

from app.catalog_prep.workbook import CATEGORIES_SHEET, PRODUCTS_SHEET, SheetRow
from app.core.enums import ProductType
from app.preview.dataset import DatasetError, PreviewDataset, parse_dataset
from app.preview.media_library import resolve_many

PREVIEW_SCHEMA_VERSION = 1

TRUE_WORDS = {"true", "yes", "y", "1", "on", "نعم"}
FALSE_WORDS = {"false", "no", "n", "0", "off", "لا"}

# Arabic-Indic and extended Arabic-Indic digits, so a price typed on an Arabic keyboard
# is read rather than rejected.
_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")

_IMAGE_COLUMN = re.compile(r"^image_(\d+)$")
_SPEC_NAME_COLUMN = re.compile(r"^spec_(\d+)_name$")
_OPTION_NAME_COLUMN = re.compile(r"^option_(\d+)_name$")

_PACKAGE_SPLIT = re.compile(r"[;\n]+")
_PACKAGE_ENTRY = re.compile(r"^(?P<ref>.+?)(?:\s*[x×*]\s*(?P<qty>\d+))?$", re.IGNORECASE)
_VALUE_SPLIT = re.compile(r"[,،|]")

_NON_SLUG = re.compile(r"[^a-z0-9]+")


class PreparationError(ValueError):
    """The workbook cannot be turned into a catalog. Carries every issue found."""

    def __init__(self, issues: list[Issue]) -> None:
        self.issues = issues
        super().__init__(f"{len(issues)} validation error(s) in the workbook")


@dataclass(frozen=True, order=True)
class Issue:
    """One reason a workbook was rejected, located precisely enough to fix."""

    sheet: str
    row: int
    field: str
    message: str

    def render(self) -> str:
        where = f"{self.sheet} row {self.row}"
        return f"{where}: {self.field} — {self.message}" if self.field else f"{where}: {self.message}"


@dataclass
class PreparedCatalog:
    document: dict[str, Any]
    dataset: PreviewDataset
    warnings: list[str] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)


# ── cell normalisation ───────────────────────────────────────────────────────
def text(value: Any) -> str | None:
    """A trimmed string, or None for a blank cell.

    Numbers are included: a SKU column of digits arrives from openpyxl as an int, and
    `1001.0` would be the wrong SKU.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    if isinstance(value, Decimal):
        value = format(value.normalize(), "f")
    result = str(value).strip()
    return result or None


def boolean(value: Any, *, default: bool) -> bool:
    if value is None or (isinstance(value, str) and not value.strip()):
        return default
    if isinstance(value, bool):
        return value
    word = str(value).strip().lower().translate(_DIGITS)
    if word in TRUE_WORDS:
        return True
    if word in FALSE_WORDS:
        return False
    raise ValueError(f"{value!r} is not a yes/no value (accepted: true/false, yes/no, 1/0)")


def _numeric_text(value: Any) -> str:
    raw = str(value).strip().translate(_DIGITS)
    # Thousands separators and the Arabic decimal comma; currency symbols are not
    # stripped, because a price column should hold a number and nothing else.
    return raw.replace(",", "").replace("٬", "").replace(" ", "").replace(" ", "")


def decimal(value: Any) -> Decimal | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, bool):
        raise ValueError(f"{value!r} is not a number")
    if isinstance(value, (int, float, Decimal)):
        return Decimal(str(value))
    try:
        return Decimal(_numeric_text(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{value!r} is not a number") from exc


def integer(value: Any) -> int | None:
    number = decimal(value)
    if number is None:
        return None
    if number != number.to_integral_value():
        raise ValueError(f"{value!r} is not a whole number")
    return int(number)


def ascii_slug(value: str | None) -> str:
    """The project's slug shape for a canonical dataset: ASCII, lowercase, hyphenated.

    `app.services.slugs.slugify` keeps Arabic letters, which is right for a slug written
    through Admin but not for a dataset key, whose grammar is ASCII. An Arabic name
    therefore yields nothing here and the caller falls back to the SKU or asks for an
    explicit `slug` column.
    """
    if not value:
        return ""
    folded = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return _NON_SLUG.sub("-", folded.lower()).strip("-")[:78]


def money_2dp(value: Decimal) -> str:
    """A price as the dataset stores it: a plain 2-place string, no float rounding."""
    return f"{value.quantize(Decimal('0.01')):f}"


# ── column discovery ─────────────────────────────────────────────────────────
def _numbered(headers: set[str], pattern: re.Pattern[str]) -> list[tuple[int, str]]:
    """Every `image_3`-style column present, in numeric order. No fixed upper bound."""
    found = [(int(match.group(1)), header) for header in headers if (match := pattern.match(header))]
    return sorted(found)


# ── the preparer ─────────────────────────────────────────────────────────────
class _Preparer:
    def __init__(
        self,
        db: Session,
        sheets: dict[str, list[SheetRow]],
        *,
        batch_key: str,
        source_label: str,
        media_prefix: str,
        origin: str,
    ) -> None:
        self.db = db
        self.sheets = sheets
        self.batch_key = batch_key
        self.source_label = source_label
        self.media_prefix = media_prefix
        self.origin = origin
        self.issues: list[Issue] = []
        self.warnings: list[str] = []
        # filename -> media key, filled as references are seen, in first-seen order.
        self.media_keys: dict[str, str] = {}

    # -- issue helpers --
    def fail(self, row: SheetRow, column: str, message: str) -> None:
        self.issues.append(Issue(row.sheet, row.number, column, message))

    def _cell(self, row: SheetRow, column: str, reader, *, default=None):
        try:
            value = reader(row.raw(column))
        except ValueError as exc:
            self.fail(row, column, str(exc))
            return default
        return default if value is None else value

    def string(self, row: SheetRow, column: str) -> str | None:
        return text(row.raw(column))

    def flag(self, row: SheetRow, column: str, *, default: bool) -> bool:
        try:
            return boolean(row.raw(column), default=default)
        except ValueError as exc:
            self.fail(row, column, str(exc))
            return default

    def number(self, row: SheetRow, column: str) -> Decimal | None:
        return self._cell(row, column, decimal)

    def count(self, row: SheetRow, column: str, *, default: int | None = None) -> int | None:
        return self._cell(row, column, integer, default=default)

    # -- media --
    def media_key(self, filename: str) -> str:
        """A stable dataset key for a filename. Deterministic and collision-free."""
        if filename in self.media_keys:
            return self.media_keys[filename]
        base = ascii_slug(filename) or f"media-{len(self.media_keys) + 1}"
        candidate = base
        suffix = 1
        taken = set(self.media_keys.values())
        while candidate in taken:
            suffix += 1
            candidate = f"{base}-{suffix}"
        self.media_keys[filename] = candidate
        return candidate

    # ── categories ───────────────────────────────────────────────────────────
    def categories(self) -> list[dict[str, Any]]:
        rows = self.sheets.get(CATEGORIES_SHEET, [])
        drafts: list[dict[str, Any]] = []
        by_name: dict[str, str] = {}
        seen_slugs: dict[str, int] = {}

        for row in rows:
            name = self.string(row, "name")
            if not name:
                self.fail(row, "name", "a category needs a name")
                continue

            slug = self.string(row, "slug") or ascii_slug(name)
            if not slug:
                self.fail(
                    row,
                    "slug",
                    f"cannot derive an ASCII slug from {name!r}; add a `slug` column value",
                )
                continue
            slug = ascii_slug(slug)
            if slug in seen_slugs:
                self.fail(row, "slug", f"slug {slug!r} is already used by row {seen_slugs[slug]}")
                continue
            seen_slugs[slug] = row.number
            by_name[name] = slug

            image = self.string(row, "image_filename")
            sort_order = self.count(row, "sort_order", default=len(drafts))

            drafts.append(
                {
                    "slug": slug,
                    "name": name,
                    "description": self.string(row, "description"),
                    "image": self.media_key(image) if image else None,
                    "parent": self.string(row, "parent_slug") or self.string(row, "parent_name"),
                    "is_active": self.flag(row, "is_active", default=True),
                    "is_featured": self.flag(row, "is_featured", default=False),
                    "sort_order": sort_order,
                    "origin": self.origin,
                    "_row": row,
                }
            )

        # Parents are written by name in the sheet and by slug in the dataset.
        for draft in drafts:
            parent = draft.pop("parent")
            row = draft["_row"]
            if parent is None:
                draft["parent"] = None
                continue
            resolved = by_name.get(parent) or (ascii_slug(parent) if ascii_slug(parent) in seen_slugs else None)
            if resolved is None:
                self.fail(row, "parent_name", f"no category named or slugged {parent!r} in this sheet")
                draft["parent"] = None
                continue
            draft["parent"] = resolved

        self.category_slugs = set(seen_slugs)
        self.category_by_name = by_name
        return [{key: value for key, value in draft.items() if key != "_row"} for draft in drafts]

    # ── products ─────────────────────────────────────────────────────────────
    def products(self) -> list[dict[str, Any]]:
        rows = self.sheets.get(PRODUCTS_SHEET, [])
        headers: set[str] = set()
        for row in rows:
            headers.update(row.values)

        image_columns = _numbered(headers, _IMAGE_COLUMN)
        spec_columns = _numbered(headers, _SPEC_NAME_COLUMN)
        option_columns = _numbered(headers, _OPTION_NAME_COLUMN)

        drafts: list[dict[str, Any]] = []
        seen_slugs: dict[str, int] = {}
        seen_skus: dict[str, int] = {}
        self.slug_by_sku: dict[str, str] = {}
        self.package_rows: dict[str, SheetRow] = {}

        for row in rows:
            name = self.string(row, "name")
            if not name:
                self.fail(row, "name", "a product needs a name")
                continue
            sku = self.string(row, "sku")

            slug = self.string(row, "slug") or ascii_slug(name) or ascii_slug(sku)
            if not slug:
                self.fail(
                    row,
                    "slug",
                    f"cannot derive an ASCII slug from {name!r}; add a `sku` or a `slug` column value",
                )
                continue
            slug = ascii_slug(slug)
            if slug in seen_slugs:
                self.fail(row, "slug", f"slug {slug!r} is already used by row {seen_slugs[slug]}")
                continue
            seen_slugs[slug] = row.number

            if sku is not None:
                if sku in seen_skus:
                    self.fail(row, "sku", f"sku {sku!r} is already used by row {seen_skus[sku]}")
                    continue
                seen_skus[sku] = row.number
                self.slug_by_sku[sku] = slug

            category = self.string(row, "category_slug") or self.string(row, "category_name")
            if not category:
                self.fail(row, "category_slug", "a product needs a category")
            else:
                resolved = (
                    category
                    if ascii_slug(category) in self.category_slugs
                    else self.category_by_name.get(category)
                )
                resolved = ascii_slug(resolved) if resolved else None
                if resolved is None:
                    self.fail(
                        row,
                        "category_slug",
                        f"no category named or slugged {category!r} in the {CATEGORIES_SHEET} sheet",
                    )
                category = resolved

            product_type = (self.string(row, "product_type") or ProductType.STANDARD.value).lower()
            allowed = {member.value for member in ProductType}
            if product_type not in allowed:
                self.fail(
                    row,
                    "product_type",
                    f"{product_type!r} is not a product type (allowed: {', '.join(sorted(allowed))})",
                )

            price = self.number(row, "price")
            if price is None:
                self.fail(row, "price", "a product needs a price")
            elif price <= 0:
                self.fail(row, "price", "price must be greater than zero")

            compare_at = self.number(row, "compare_at_price")
            if compare_at is not None and price is not None and compare_at <= price:
                self.fail(
                    row,
                    "compare_at_price",
                    "must be above price, or the storefront advertises a discount that is not one",
                )

            draft: dict[str, Any] = {
                "slug": slug,
                "name": name,
                "category": category,
                "sku": sku,
                "product_type": product_type,
                "price": money_2dp(price) if price is not None else None,
                "compare_at_price": money_2dp(compare_at) if compare_at is not None else None,
                "cost_price": None,
                "stock_quantity": self.count(row, "stock_quantity", default=0),
                "track_inventory": self.flag(row, "track_inventory", default=True),
                "low_stock_threshold": self.count(row, "low_stock_threshold", default=3),
                "short_description": self.string(row, "short_description"),
                "description": self.string(row, "description"),
                "images": self._images(row, image_columns),
                "is_active": self.flag(row, "is_active", default=True),
                "is_featured": self.flag(row, "is_featured", default=False),
                "is_new": self.flag(row, "is_new", default=False),
                "is_bestseller": self.flag(row, "is_bestseller", default=False),
                "sort_order": self.count(row, "sort_order", default=len(drafts)),
                "seo_title": self.string(row, "seo_title"),
                "seo_description": self.string(row, "seo_description"),
                "origin": self.origin,
                "specifications": self._specifications(row, spec_columns),
                "options": self._options(row, option_columns),
                "package_items": [],
            }
            cost = self.number(row, "cost_price")
            draft["cost_price"] = money_2dp(cost) if cost is not None else None

            package_items = self.string(row, "package_items")
            if package_items and product_type != ProductType.PACKAGE.value:
                self.fail(
                    row,
                    "package_items",
                    f"only a product_type of {ProductType.PACKAGE.value!r} may list package items",
                )
            elif product_type == ProductType.PACKAGE.value:
                if not package_items:
                    self.fail(row, "package_items", "a package must list what it contains")
                else:
                    draft["package_items"] = self._package_items(row, package_items)
                    self.package_rows[slug] = row

            drafts.append(draft)

        self.product_slugs = set(seen_slugs)
        return drafts

    def _images(self, row: SheetRow, columns: list[tuple[int, str]]) -> list[str]:
        """The gallery, in column order. Blank columns are skipped, not padded."""
        keys: list[str] = []
        for _, column in columns:
            filename = self.string(row, column)
            if not filename:
                continue
            key = self.media_key(filename)
            if key in keys:
                self.fail(row, column, f"{filename!r} is already used by an earlier image column")
                continue
            keys.append(key)
        return keys

    def _specifications(self, row: SheetRow, columns: list[tuple[int, str]]) -> list[dict[str, str]]:
        specs: list[dict[str, str]] = []
        for number, column in columns:
            name = self.string(row, column)
            value = self.string(row, f"spec_{number}_value")
            if name is None and value is None:
                continue
            if name is None or value is None:
                self.fail(
                    row,
                    column if name is None else f"spec_{number}_value",
                    "a specification needs both a name and a value",
                )
                continue
            specs.append({"name": name, "value": value})
        return specs

    def _options(self, row: SheetRow, columns: list[tuple[int, str]]) -> list[dict[str, Any]]:
        options: list[dict[str, Any]] = []
        for number, column in columns:
            name = self.string(row, column)
            raw_values = self.string(row, f"option_{number}_values")
            if name is None and raw_values is None:
                continue
            if name is None or raw_values is None:
                self.fail(
                    row,
                    column if name is None else f"option_{number}_values",
                    "an option needs both a name and a comma-separated list of values",
                )
                continue
            values = [part.strip() for part in _VALUE_SPLIT.split(raw_values) if part.strip()]
            if not values:
                self.fail(row, f"option_{number}_values", "no values were listed")
                continue
            options.append({"name": name, "values": values})
        return options

    def _package_items(self, row: SheetRow, raw: str) -> list[dict[str, Any]]:
        """`VST-1001 x2; VST-1005` -> package item drafts, still keyed by SKU."""
        items: list[dict[str, Any]] = []
        for chunk in _PACKAGE_SPLIT.split(raw):
            entry = chunk.strip()
            if not entry:
                continue
            match = _PACKAGE_ENTRY.match(entry)
            if match is None:  # pragma: no cover - the pattern accepts any non-empty text
                self.fail(row, "package_items", f"cannot read {entry!r}")
                continue
            quantity_text = match.group("qty")
            quantity = int(quantity_text) if quantity_text else 1
            if quantity < 1:
                self.fail(row, "package_items", f"{entry!r}: quantity must be at least 1")
                continue
            items.append({"product": match.group("ref").strip(), "quantity": quantity})
        if not items:
            self.fail(row, "package_items", "no package contents could be read")
        return items

    def resolve_package_references(self, products: list[dict[str, Any]]) -> None:
        """Turn the SKU (or slug) each package names into the product's dataset slug."""
        for product in products:
            if not product["package_items"]:
                continue
            row = self.package_rows.get(product["slug"])
            resolved: list[dict[str, Any]] = []
            for item in product["package_items"]:
                reference = item["product"]
                slug = self.slug_by_sku.get(reference)
                if slug is None and ascii_slug(reference) in self.product_slugs:
                    slug = ascii_slug(reference)
                if slug is None:
                    if row is not None:
                        self.fail(
                            row,
                            "package_items",
                            f"{reference!r} is not the SKU or slug of any product in this sheet",
                        )
                    continue
                if slug == product["slug"]:
                    if row is not None:
                        self.fail(row, "package_items", "a package cannot contain itself")
                    continue
                resolved.append({"product": slug, "quantity": item["quantity"]})
            product["package_items"] = resolved

    # ── media resolution ─────────────────────────────────────────────────────
    def media(self) -> list[dict[str, Any]]:
        """Every referenced filename, resolved against the Media Library.

        Resolution happens here so a dry run fails on a missing picture, but the
        generated file still carries only the filename: the importer resolves it again
        at seed time, against whatever storage provider is configured then.
        """
        resolved, errors = resolve_many(self.db, self.media_keys)
        for filename, message in errors.items():
            self.issues.append(Issue(PRODUCTS_SHEET, 0, "image", message))
        self.resolved_media = resolved
        return [
            {
                "key": key,
                "library_filename": filename,
                "alt_text": filename[:250],
                "origin": self.origin,
            }
            for filename, key in sorted(self.media_keys.items(), key=lambda pair: pair[1])
        ]

    def run(self) -> PreparedCatalog:
        categories = self.categories()
        products = self.products()
        self.resolve_package_references(products)
        media = self.media()

        if self.issues:
            raise PreparationError(sorted(self.issues))

        document = {
            "preview_schema_version": PREVIEW_SCHEMA_VERSION,
            "batch_key": self.batch_key,
            "source_label": self.source_label,
            "media_prefix": self.media_prefix,
            "media": media,
            "categories": [
                {key: value for key, value in category.items() if not _is_default(key, value)}
                for category in categories
            ],
            "products": [
                {key: value for key, value in product.items() if not _is_default(key, value)}
                for product in products
            ],
        }

        try:
            dataset = parse_dataset(document, source="<prepared workbook>")
        except DatasetError as exc:
            # The row-level checks above are the ones with a sheet and a row number; this
            # is the canonical schema having the last word, and it is worth surfacing.
            raise PreparationError([Issue("dataset", 0, "", str(exc))]) from exc

        images = sum(len(product.get("images", [])) for product in products)
        images += sum(1 for category in categories if category.get("image"))
        counts = {
            "categories": len(categories),
            "products": len(products),
            "images_referenced": images,
            "media_resolved": len(self.resolved_media),
            "packages": sum(1 for product in products if product["package_items"]),
            "specifications": sum(len(product["specifications"]) for product in products),
            "options": sum(len(product["options"]) for product in products),
        }
        return PreparedCatalog(
            document=document, dataset=dataset, warnings=self.warnings, counts=counts
        )


_OMITTABLE_DEFAULTS = {
    "compare_at_price": None,
    "cost_price": None,
    "sku": None,
    "short_description": None,
    "description": None,
    "seo_title": None,
    "seo_description": None,
    "specifications": [],
    "options": [],
    "package_items": [],
    "images": [],
    "image": None,
    "parent": None,
    "low_stock_threshold": 3,
    "is_featured": False,
    "is_new": False,
    "is_bestseller": False,
    "is_active": True,
    "track_inventory": True,
}


def _is_default(key: str, value: Any) -> bool:
    """Keep the generated file readable: a column nobody filled in leaves no line."""
    return key in _OMITTABLE_DEFAULTS and value == _OMITTABLE_DEFAULTS[key]


def prepare_catalog(
    db: Session,
    sheets: dict[str, list[SheetRow]],
    *,
    batch_key: str,
    source_label: str,
    media_prefix: str,
    origin: str = "confirmed",
) -> PreparedCatalog:
    """Validate a workbook and build the canonical dataset it describes.

    Reads the Media Library. Writes nothing, anywhere.
    """
    return _Preparer(
        db,
        sheets,
        batch_key=batch_key,
        source_label=source_label,
        media_prefix=media_prefix,
        origin=origin,
    ).run()


def render_yaml(document: dict[str, Any]) -> str:
    """The dataset as YAML. Deterministic: same workbook and library, same bytes.

    Key order follows the document, not the alphabet, and no timestamp or environment
    detail is written — so a regenerated file diffs only where the catalog changed.
    """
    header = (
        "# Generated from a client workbook by `python -m scripts.catalog_prep_cli prepare`.\n"
        "# Images are named by their Media Library filename and resolved at import time.\n"
        "# Import with: python -m scripts.preview_cli seed --dataset <this file>\n"
    )
    body = yaml.safe_dump(
        document,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        width=100,
    )
    return header + body
