import { useState } from "react";
import sx from "../sx.js";
import { Button, Field, input } from "./ui.jsx";

/**
 * Variants of a product: one row per real combination of option values.
 *
 * The source of truth for a variant is its `option_value_ids` — the title is
 * display metadata derived from those values, so the generator and the manual
 * form build it the same way.
 */

/** Order-insensitive identity of a combination, used to detect duplicates. */
export const comboKey = (ids) =>
  [...(ids || [])]
    .map(Number)
    .sort((a, b) => a - b)
    .join("-");

/** Deterministic label, e.g. "أحمر / كبير" — values in axis order. */
export function variantTitle(options, valueIds) {
  const chosen = new Set((valueIds || []).map(Number));
  return (options || [])
    .flatMap((option) => (option.values || []).filter((value) => chosen.has(value.id)))
    .map((value) => value.value)
    .join(" / ");
}

/** Cartesian product of every axis, as arrays of option value ids. */
export function combinations(options) {
  return (options || []).reduce(
    (rows, option) => rows.flatMap((row) => (option.values || []).map((value) => [...row, value.id])),
    [[]],
  );
}

/**
 * Turn the edited option rows into the API payload, carrying row ids through so
 * the backend treats a rename as an update instead of delete + insert.
 *
 * Values keep their id when the text is unchanged; the leftovers are paired in
 * order, which is how a rename keeps the same value row (and its variants).
 */
export function buildOptionsPayload(options) {
  return (options || [])
    .filter((option) => (option.name || "").trim())
    .map((option, index) => {
      const texts = (option.values || "")
        .split(/[،,]/)
        .map((value) => value.trim())
        .filter(Boolean);
      const pool = [...(option.rows || [])];
      const take = (text) => {
        const exact = pool.findIndex((row) => row.value === text);
        if (exact >= 0) return pool.splice(exact, 1)[0];
        return null;
      };
      const matched = texts.map(take);
      matched.forEach((row, i) => {
        if (!row && pool.length) matched[i] = pool.shift();
      });
      return {
        ...(option.id ? { id: option.id } : {}),
        name: option.name.trim(),
        sort_order: index,
        values: texts.map((value, valueIndex) => ({
          ...(matched[valueIndex]?.id ? { id: matched[valueIndex].id } : {}),
          value,
          sort_order: valueIndex,
        })),
      };
    });
}

/**
 * Variants the backend would drop for this payload: same rule as the API — a
 * variant survives only while it still holds exactly one value per axis.
 */
export function variantsRemovedByOptions(variants, payload) {
  const axisOf = new Map();
  const axisKeys = new Set();
  (payload || []).forEach((option, index) => {
    const key = option.id ?? `new:${index}`;
    axisKeys.add(key);
    (option.values || []).forEach((value) => {
      if (value.id) axisOf.set(value.id, key);
    });
  });
  return (variants || []).filter((variant) => {
    const ids = variant.option_value_ids || [];
    if (!ids.length) return false;
    if (ids.some((id) => !axisOf.has(id))) return true;
    const axes = new Set(ids.map((id) => axisOf.get(id)));
    return axes.size !== axisKeys.size;
  });
}

const num = (value) => (value === "" || value === null || value === undefined ? null : Number(value));

const row = sx`display:flex;align-items:center;gap:12px;flex-wrap:wrap;border:1px solid #EFEBE4;border-radius:10px;padding:10px 12px`;
const meta = sx`font-size:13px;color:#7C766D`;

export default function ProductVariantsEditor({
  options = [],
  variants = [],
  onCreate,
  onUpdate,
  onDelete,
  onReport = () => {},
}) {
  const [choice, setChoice] = useState({});
  const [freeTitle, setFreeTitle] = useState("");
  const [editing, setEditing] = useState(null);
  const [busy, setBusy] = useState(false);

  const axes = options.filter((option) => (option.values || []).length);
  const complete = options.length > 0 && axes.length === options.length;
  const picked = options.map((option) => choice[option.id]).filter((value) => value != null);
  const canAdd = options.length ? picked.length === options.length : !!freeTitle.trim();

  const defaults = (title, valueIds) => ({
    title,
    sku: null,
    price_override: null,
    stock_quantity: 0,
    is_active: true,
    option_value_ids: valueIds,
  });

  const create = async () => {
    const payload = options.length
      ? defaults(variantTitle(options, picked), picked)
      : defaults(freeTitle.trim(), []);
    setBusy(true);
    try {
      await onCreate([payload]);
      setChoice({});
      setFreeTitle("");
    } catch {
      // The page shows the failure; nothing here may pretend it was saved.
    } finally {
      setBusy(false);
    }
  };

  const generate = async () => {
    const existing = new Set(variants.map((variant) => comboKey(variant.option_value_ids)));
    const combos = combinations(options);
    const missing = combos.filter((ids) => !existing.has(comboKey(ids)));
    setBusy(true);
    try {
      if (missing.length) {
        await onCreate(missing.map((ids) => defaults(variantTitle(options, ids), ids)));
      }
      // Reported by the page, whose banner survives the reload this triggers.
      onReport(`تم إنشاء ${missing.length} نسخة — موجودة مسبقاً ${combos.length - missing.length}`);
    } catch {
      // Say nothing rather than claim combinations that never landed.
    } finally {
      setBusy(false);
    }
  };

  const saveEdit = async () => {
    setBusy(true);
    try {
      await onUpdate(editing.id, {
        title: editing.title.trim(),
        sku: editing.sku.trim() || null,
        price_override: num(editing.price_override),
        stock_quantity: Number(editing.stock_quantity) || 0,
        is_active: !!editing.is_active,
        option_value_ids: editing.option_value_ids,
      });
      setEditing(null);
    } catch {
      // Stay in edit mode so the unsaved values remain visible as unsaved.
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <div style={sx`display:flex;gap:10px;flex-wrap:wrap;align-items:flex-end`}>
        {options.length ? (
          options.map((option) => (
            <Field key={option.id} title={option.name}>
              <select
                value={choice[option.id] ?? ""}
                onChange={(event) =>
                  setChoice((current) => ({
                    ...current,
                    [option.id]: event.target.value ? Number(event.target.value) : undefined,
                  }))
                }
                style={{ ...input, ...sx`min-width:150px` }}
              >
                <option value="">اختر…</option>
                {(option.values || []).map((value) => (
                  <option key={value.id} value={value.id}>
                    {value.value}
                  </option>
                ))}
              </select>
            </Field>
          ))
        ) : (
          <Field title="اسم نسخة جديدة">
            <input value={freeTitle} onChange={(event) => setFreeTitle(event.target.value)} style={input} />
          </Field>
        )}
        <Button disabled={!canAdd || busy} onClick={create}>
          إضافة نسخة
        </Button>
        {!!options.length && (
          <Button variant="secondary" disabled={!complete || busy} onClick={generate}>
            توليد المتغيرات من الخيارات
          </Button>
        )}
      </div>
      {!!options.length && (
        <p style={sx`margin:0;font-size:12.5px;color:#9C958A`}>
          التوليد ينشئ التركيبات الناقصة فقط بسعر المنتج ومخزون صفر، ولا يغيّر النسخ الموجودة.
        </p>
      )}

      <div style={sx`display:flex;flex-direction:column;gap:8px`}>
        {variants.map((variant) =>
          editing?.id === variant.id ? (
            <div key={variant.id} style={{ ...row, ...sx`align-items:flex-end` }}>
              <Field title="اسم النسخة">
                <input
                  value={editing.title}
                  onChange={(event) => setEditing({ ...editing, title: event.target.value })}
                  style={{ ...input, ...sx`min-width:140px` }}
                />
              </Field>
              <Field title="SKU النسخة">
                <input
                  value={editing.sku}
                  onChange={(event) => setEditing({ ...editing, sku: event.target.value })}
                  style={{ ...input, ...sx`min-width:120px` }}
                />
              </Field>
              <Field title="سعر النسخة الخاص">
                <input
                  type="number"
                  step="0.01"
                  value={editing.price_override}
                  onChange={(event) => setEditing({ ...editing, price_override: event.target.value })}
                  style={{ ...input, ...sx`min-width:110px` }}
                />
              </Field>
              <Field title="مخزون النسخة">
                <input
                  type="number"
                  value={editing.stock_quantity}
                  onChange={(event) => setEditing({ ...editing, stock_quantity: event.target.value })}
                  style={{ ...input, ...sx`min-width:100px` }}
                />
              </Field>
              <label style={sx`display:flex;align-items:center;gap:8px;font-size:13px;font-weight:700;cursor:pointer;min-height:44px`}>
                <input
                  type="checkbox"
                  checked={editing.is_active}
                  onChange={(event) => setEditing({ ...editing, is_active: event.target.checked })}
                  style={sx`width:18px;height:18px;accent-color:#1F4E4A`}
                />
                فعّالة
              </label>
              <Button disabled={busy} onClick={saveEdit}>
                حفظ النسخة
              </Button>
              <Button variant="ghost" disabled={busy} onClick={() => setEditing(null)}>
                إلغاء
              </Button>
            </div>
          ) : (
            <div key={variant.id} style={row}>
              <strong style={sx`font-size:14px`}>{variant.title}</strong>
              <span style={meta}>السعر: {variant.price_override ?? "سعر المنتج"}</span>
              <span style={meta}>المخزون: {variant.stock_quantity}</span>
              <span style={meta}>SKU: {variant.sku || "—"}</span>
              <span style={meta}>{variant.is_active ? "فعّالة" : "متوقفة"}</span>
              <Button
                variant="secondary"
                aria-label={`تعديل ${variant.title}`}
                style={sx`margin-inline-start:auto;min-height:34px;font-size:12.5px`}
                onClick={() =>
                  setEditing({
                    id: variant.id,
                    title: variant.title ?? "",
                    sku: variant.sku ?? "",
                    price_override: variant.price_override ?? "",
                    stock_quantity: variant.stock_quantity ?? 0,
                    is_active: !!variant.is_active,
                    option_value_ids: variant.option_value_ids || [],
                  })
                }
              >
                تعديل
              </Button>
              <Button
                variant="danger"
                aria-label={`حذف ${variant.title}`}
                style={sx`min-height:34px;font-size:12.5px`}
                onClick={() => onDelete(variant.id).catch(() => {})}
              >
                حذف
              </Button>
            </div>
          ),
        )}
        {!variants.length && (
          <span style={sx`font-size:13px;color:#9C958A`}>
            {options.length
              ? "لا توجد نسخ — المنتج له خيارات ولن يمكن شراؤه حتى تُولَّد النسخ."
              : "لا توجد نسخ — سيُباع المنتج بسعر ومخزون واحد."}
          </span>
        )}
      </div>
    </>
  );
}
