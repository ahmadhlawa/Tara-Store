"""Arabic is authoritative. Writes enqueue; public reads only overlay cached copy."""
from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import timedelta
from threading import Event, Thread
from urllib.request import Request, urlopen

from sqlalchemy import delete, event, insert, inspect, or_, select, update
from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.models import (Category, Coupon, DeliveryArea, HomeSection, PackageItem,
    Product, ProductOption, ProductOptionValue, ProductVariant, StaticPage, StoreSettings, Translation)

logger = logging.getLogger(__name__)
FIELDS = {
    Product: ("name", "short_description", "description", "seo_title", "seo_description"),
    Category: ("name", "description"), ProductOption: ("name",),
    ProductOptionValue: ("value", "presentation_title"), ProductVariant: ("title",),
    StaticPage: ("title", "lead", "content", "seo_title", "seo_description"),
    HomeSection: ("title", "description"), DeliveryArea: ("name", "estimated_days"),
    Coupon: ("description",), PackageItem: ("display_note",),
    StoreSettings: ("store_tagline", "address", "working_hours", "announcement",
        "manual_payment_instructions", "seo_title", "seo_description"),
}
TYPES = {model.__tablename__: model for model in FIELDS}
# Explicit public prose keys only; never walk arbitrary config strings.
CONFIG_FIELDS = ("title", "description", "text", "body", "button_label")


def source_hash(text):
    return hashlib.sha256(str(text or "").encode("utf-8")).hexdigest()


def sources(entity):
    result = {field: getattr(entity, field) for field in FIELDS.get(type(entity), ())}
    if isinstance(entity, HomeSection):
        result.update({f"config.{key}": value for key in CONFIG_FIELDS
            if isinstance(value := (entity.config or {}).get(key), str)})
    return result


def stage(connection, entity):
    """Queue in the same transaction as Arabic; no network or provider dependency."""
    table = Translation.__table__
    entity_type = entity.__tablename__
    existing = {row.field: row for row in connection.execute(select(table).where(
        table.c.entity_type == entity_type, table.c.entity_id == entity.id, table.c.locale == "en"))}
    current = sources(entity)
    changed = False
    for field, text in current.items():
        previous = existing.get(field)
        if not isinstance(text, str) or not text.strip():
            if previous:
                connection.execute(delete(table).where(table.c.id == previous.id))
                changed = True
            continue
        digest = source_hash(text)
        if previous and previous.source_hash == digest:
            continue
        values = dict(source_hash=digest, status="pending", attempts=0,
            retry_at=None, updated_at=utcnow())
        changed = True
        if previous:
            connection.execute(update(table).where(table.c.id == previous.id).values(**values))
        else:
            connection.execute(insert(table).values(entity_type=entity_type, entity_id=entity.id,
                field=field, locale="en", **values))
    for field, previous in existing.items():
        if field not in current:
            connection.execute(delete(table).where(table.c.id == previous.id))
            changed = True
    return changed



@event.listens_for(Session, "before_flush")
def remember_sources(session, *_):
    changes = []
    for entity in session.new.union(session.dirty):
        if type(entity) not in FIELDS or entity in session.deleted:
            continue
        fields = FIELDS[type(entity)] + (("config",) if isinstance(entity, HomeSection) else ())
        if entity in session.new or any(inspect(entity).attrs[field].history.has_changes() for field in fields):
            changes.append(entity)
    session.info["translation_changes"] = changes


@event.listens_for(Session, "after_flush_postexec")
def queue_sources(session, *_):
    connection = session.connection()
    changes = session.info.pop("translation_changes", [])
    for entity in changes:
        if not inspect(entity).deleted and stage(connection, entity):
            session.info["translation_queued"] = True


@event.listens_for(Session, "persistent_to_deleted")
def remove_deleted_source(session, entity):
    # Also covers relationship delete-orphan transitions during option replacement.
    if type(entity) in FIELDS:
        session.connection().execute(delete(Translation).where(
            Translation.entity_type == entity.__tablename__, Translation.entity_id == entity.id))


@event.listens_for(Session, "after_rollback")
def forget_rolled_back_sources(session):
    session.info.pop("translation_changes", None)
    session.info.pop("translation_queued", None)


class LibreTranslator:
    """Private LibreTranslate REST boundary; no paid or external fallback."""
    def __init__(self, config):
        self.config = config

    def translate(self, text, source="ar", target="en"):
        if (source, target) not in (("ar", "en"), ("en", "ar")):
            raise ValueError("Only Arabic ↔ English is supported")
        if not self.config.LIBRETRANSLATE_URL:
            raise RuntimeError("LibreTranslate is not configured")
        # Preserve account numbers, numeric measurements and codes byte-for-byte.
        numbers = []
        def protect(match):
            numbers.append(match.group())
            return f"TARANUMBER{len(numbers) - 1}TOKEN"
        protected = re.sub(r"[0-9٠-٩]+(?:[ .,/–:-][0-9٠-٩]+)*", protect, text)
        translated = []
        # Preserve policy paragraph boundaries and avoid splitting protected numbers.
        chunks = []
        for paragraph in re.split(r"(\n+)", protected):
            if not paragraph:
                continue
            if paragraph.isspace():
                chunks.append((None, paragraph))
                continue
            while len(paragraph) > 4000:
                boundary = paragraph.rfind(" ", 0, 4000)
                separator = " " if boundary > 0 else ""
                boundary = boundary if boundary > 0 else 4000
                for token in re.finditer(r"TARANUMBER\d+TOKEN", paragraph):
                    if token.start() < boundary < token.end():
                        boundary, separator = token.start(), ""
                        break
                chunks.append((paragraph[:boundary], separator))
                paragraph = paragraph[boundary + len(separator):]
            if paragraph:
                chunks.append((paragraph, ""))
        for chunk, separator in chunks:
            if chunk is None:
                translated.append(separator)
                continue
            body = {"q": chunk, "source": source, "target": target, "format": "text"}
            if self.config.LIBRETRANSLATE_API_KEY:
                body["api_key"] = self.config.LIBRETRANSLATE_API_KEY
            payload = json.dumps(body).encode()
            request = Request(self.config.LIBRETRANSLATE_URL.rstrip("/") + "/translate",
                data=payload, headers={"Content-Type": "application/json"}, method="POST")
            with urlopen(request, timeout=self.config.TRANSLATION_TIMEOUT_SECONDS) as response:
                result = json.load(response)["translatedText"]
                if not isinstance(result, str) or not result.strip():
                    raise ValueError("Empty or invalid translation")
                translated.append(result + separator)
        result = "".join(translated)
        for index, number in enumerate(numbers):
            token = f"TARANUMBER{index}TOKEN"
            if token not in result:
                raise ValueError("Translation did not preserve a numeric placeholder")
            result = result.replace(token, number)
        if not result.strip():
            raise ValueError("Empty translation")
        return result


def process_pending(factory, translator, *, limit=20, force_retry=False):
    """Network runs outside DB transactions. Compare-and-set rejects obsolete results."""
    with factory() as db:
        due = or_(Translation.retry_at.is_(None), Translation.retry_at <= utcnow())
        waiting = Translation.status.in_(("pending", "failed"))
        stmt = select(Translation).where(or_(waiting if force_retry else waiting & due, (Translation.status == "processing") & due))
        rows = list(db.scalars(stmt.order_by(Translation.id).limit(limit)))
        work = []
        for row in rows:
            model = TYPES.get(row.entity_type)
            entity = db.get(model, row.entity_id) if model else None
            text = sources(entity).get(row.field) if entity else None
            if not text:
                db.delete(row)
            elif source_hash(text) != row.source_hash:
                stage(db.connection(), entity)
            else:
                # Lease prevents multiple API processes claiming the same work.
                claim = db.execute(update(Translation).where(Translation.id == row.id,
                    Translation.source_hash == row.source_hash, Translation.status == row.status,
                    Translation.attempts == row.attempts,
                    Translation.retry_at == row.retry_at).values(status="processing",
                        attempts=row.attempts + 1, retry_at=utcnow() + timedelta(hours=1)),
                    execution_options={"synchronize_session": False})
                if claim.rowcount:
                    work.append((row.id, row.entity_type, row.entity_id, row.field,
                        row.source_hash, row.attempts + 1, text))
        db.commit()
    completed = 0
    for row_id, kind, entity_id, field, digest, attempts, text in work:
        try:
            translated = translator.translate(text) if re.search(r"[\u0600-\u06ff]", text) else text
            values = dict(status="ready", translated_text=translated, retry_at=None, updated_at=utcnow())
        except Exception:
            # Never log credentials, provider URLs or customer/account prose.
            logger.warning("Translation failed: %s/%s/%s", kind, entity_id, field)
            values = dict(status="failed",
                retry_at=utcnow() + timedelta(seconds=min(3600, 30 * 2 ** min(attempts - 1, 7))), updated_at=utcnow())
        with factory() as db:
            entity = db.get(TYPES[kind], entity_id)
            if entity and source_hash(sources(entity).get(field)) == digest:
                result = db.execute(update(Translation).where(Translation.id == row_id,
                    Translation.source_hash == digest, Translation.status == "processing",
                    Translation.attempts == attempts).values(**values))
                completed += int(result.rowcount > 0 and values["status"] == "ready")
            db.commit()
    return len(work), completed


class TranslationWorker:
    """One bounded poller per API process; persisted rows survive shutdown/restart."""
    def __init__(self, factory, config):
        self.factory, self.config = factory, config
        self.stop = Event()
        self.wake = Event()
        self.thread = Thread(target=self.run, name="tara-translations", daemon=True)
        def committed(session):
            if session.info.pop("translation_queued", False):
                self.wake.set()
        self.committed = committed
        event.listen(self.factory, "after_commit", committed)

    def run(self):
        while not self.stop.is_set():
            self.wake.clear()
            try:
                process_pending(self.factory, LibreTranslator(self.config), limit=self.config.TRANSLATION_BATCH_SIZE)
            except Exception:
                logger.warning("Translation queue unavailable; retrying later")
            self.wake.wait(self.config.TRANSLATION_POLL_SECONDS)

    def close(self):
        self.stop.set()
        self.wake.set()
        self.thread.join(timeout=2)
        event.remove(self.factory, "after_commit", self.committed)


def localize(db, payload, entities, locale, kind):
    """Copy serialized public data and overlay in one batched lookup. Never writes."""
    if locale != "en":
        return payload
    entities = {(entity.__tablename__, entity.id): entity for entity in entities if entity is not None}
    if not entities:
        return payload
    ids_by_type = {}
    for entity_type, entity_id in entities:
        ids_by_type.setdefault(entity_type, []).append(entity_id)
    rows = db.scalars(select(Translation).where(Translation.locale == "en", Translation.status == "ready",
        or_(*((Translation.entity_type == kind) & Translation.entity_id.in_(ids)
            for kind, ids in ids_by_type.items()))))
    replacements = {}
    by_entity = {}
    for row in rows:
        text = sources(entities[(row.entity_type, row.entity_id)]).get(row.field)
        if text and row.source_hash == source_hash(text) and row.translated_text:
            replacements[(row.entity_type, row.entity_id, row.field)] = row.translated_text
            by_entity.setdefault((row.entity_type, row.entity_id), {})[row.field] = row.translated_text

    def overlay(data, kind=None):
        if isinstance(data, list):
            return [overlay(item, kind) for item in data]
        if not isinstance(data, dict):
            return data
        result = dict(data)
        entity_id = data.get("id")
        if kind:
            for field, translated in by_entity.get((kind, entity_id), {}).items():
                if field.startswith("config."):
                    key = field.split(".", 1)[1]
                    result["config"] = {**result.get("config", {}), key: translated}
                else:
                    result[field] = translated
        for key, nested_kind in {"children": "categories", "images": "product_images",
            "options": "product_options", "values": "product_option_values", "variants": "product_variants",
            "package_items": "package_items", "products": "products", "area": "delivery_areas"}.items():
            if key in result:
                result[key] = overlay(result[key], nested_kind)
        if kind == "products":
            result["category_name"] = replacements.get(("categories", data.get("category_id"), "name"), data.get("category_name"))
        if kind == "package_items":
            result["included_product_name"] = replacements.get(("products", data.get("included_product_id"), "name"), data.get("included_product_name"))
        return result

    # Callers select the root type explicitly; no guesswork from shared field names.
    return overlay(payload, kind)


def product_entities(products):
    result = []
    for product in products:
        result.extend([product, product.category])
        for option in product.options:
            result.extend([option, *option.values])
        result.extend(product.variants)
        for item in product.package_items:
            result.extend([item, item.included_product, item.included_variant])
    return result


def localized_products(db, products, locale, *, detail=False):
    from app.schemas.catalog import ProductPublicDetail, ProductPublicOut
    from app.services.catalog import product_payload
    schema = ProductPublicDetail if detail else ProductPublicOut
    data = [schema.model_validate(product_payload(product, include_relations=detail)).model_dump() for product in products]
    entities = product_entities(products) if detail else [entity for product in products for entity in (product, product.category)]
    return localize(db, data, entities, locale, "products")


def localized_checkout(db, data, products, locale, *, area=None, selected_ids=None):
    """Localize response labels without changing prices or persisted order snapshots."""
    if locale != "en":
        return data
    from app.services.catalog import product_payload
    from app.schemas.catalog import ProductPublicDetail
    products = list({product.id: product for product in products}.values())
    payloads = [ProductPublicDetail.model_validate(product_payload(product, include_relations=True)).model_dump()
        for product in products]
    entities = product_entities(products) + ([area] if area else [])
    overlay = localize(db, {"products": payloads, "area": {"id": area.id, "name": area.name} if area else None},
        entities, locale, None)
    localized = overlay["products"]
    by_id = {product.id: (product, copy) for product, copy in zip(products, localized)}
    selected_ids = selected_ids or {}
    result = dict(data)
    line_key = "lines" if "lines" in data else "items"
    result[line_key] = []
    for line in data.get(line_key, []):
        copy = dict(line)
        source, translated = by_id.get(line.get("product_id"), (None, None))
        if source and line.get("product_name") == source.name:
            copy["product_name"] = translated["name"]
        if source:
            ids = line.get("selected_option_value_ids") or selected_ids.get(source.id, [])
            variant = next((variant for variant in source.variants if variant.id == line.get("variant_id")), None)
            if not ids and variant:
                ids = [value.id for value in variant.option_values]
            original_labels = [f"{option.name}: {value.value}" for option in source.options
                for value in option.values if value.id in ids]
            if original_labels and line.get("variant_description") == "، ".join(original_labels):
                copy["variant_description"] = ", ".join(f"{option['name']}: {value['value']}"
                    for option in translated["options"] for value in option["values"] if value["id"] in ids)
            elif variant and line.get("variant_description") == variant.title:
                copy["variant_description"] = next(item["title"] for item in translated["variants"] if item["id"] == variant.id)
        result[line_key].append(copy)
    # Preserve historical area snapshots after renames, just as product snapshots.
    if area and data.get("delivery_area_name") == area.name:
        result["delivery_area_name"] = overlay["area"]["name"]
    return result
