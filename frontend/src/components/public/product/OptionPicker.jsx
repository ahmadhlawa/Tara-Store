import { useEffect, useMemo, useState } from "react";

/**
 * Variant chooser.
 *
 * A product whose variants each name exactly one value per option axis is shown
 * as one row of choices per axis — colour and size stay separate questions — and
 * the picked values resolve to the single variant that carries that combination.
 *
 * Older rows that do not describe a clean combination (no option values, a value
 * missing for an axis, or two rows on the same combination) cannot be resolved
 * that way, so they keep the flat list of variant titles instead of silently
 * resolving to the wrong row.
 */

const comboKey = (ids) =>
  [...(ids || [])]
    .map(Number)
    .sort((a, b) => a - b)
    .join("-");

export default function OptionPicker({ product, variants, variantId, onPick, error }) {
  const axes = useMemo(
    () => (product?.options || []).filter((option) => (option.values || []).length),
    [product],
  );

  const resolvable = useMemo(() => {
    if (!axes.length || !variants.length) return false;
    const seen = new Set();
    return variants.every((variant) => {
      const ids = (variant.option_value_ids || []).map(Number);
      if (ids.length !== axes.length) return false;
      if (!axes.every((axis) => axis.values.filter((value) => ids.includes(value.id)).length === 1)) {
        return false;
      }
      const key = comboKey(ids);
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }, [axes, variants]);

  const [choice, setChoice] = useState({});
  useEffect(() => setChoice({}), [product?.id]);

  if (!variants.length) return null;
  const errorId = error ? "vs-option-error" : undefined;

  if (!resolvable) {
    const groupName = product?.options?.[0]?.name || "الخيار";
    return (
      <fieldset className="vs-options" aria-describedby={errorId}>
        <legend className="vs-options__legend">
          {groupName}
          <span className="vs-options__required" aria-hidden="true">
            *
          </span>
        </legend>
        <div className="vs-options__row">
          {variants.map((variant) => {
            const out = variant.stock_quantity <= 0;
            return (
              <button
                key={variant.id}
                type="button"
                className="vs-option"
                aria-pressed={variant.id === variantId}
                data-out={out}
                onClick={() => onPick(variant.id)}
              >
                {variant.title}
                {out && <span className="vs-option__out"> — نفد</span>}
              </button>
            );
          })}
        </div>
        {error && (
          <p className="vs-options__error" id="vs-option-error" role="alert">
            {error}
          </p>
        )}
      </fieldset>
    );
  }

  // Variants that still fit every choice made on the other axes.
  const candidatesFor = (axis, value) =>
    variants.filter((variant) => {
      const ids = (variant.option_value_ids || []).map(Number);
      if (!ids.includes(value.id)) return false;
      return axes.every(
        (other) => other.id === axis.id || choice[other.id] == null || ids.includes(choice[other.id]),
      );
    });

  const pick = (axis, value) => {
    const next = { ...choice, [axis.id]: value.id };
    setChoice(next);
    const ids = axes.map((item) => next[item.id]).filter((id) => id != null);
    const match =
      ids.length === axes.length
        ? variants.find((variant) => comboKey(variant.option_value_ids) === comboKey(ids))
        : null;
    onPick(match ? match.id : null);
  };

  return (
    <fieldset className="vs-options" aria-describedby={errorId}>
      {axes.map((axis) => (
        <div key={axis.id} className="vs-options__axis" role="group" aria-label={axis.name}>
          <span className="vs-options__legend">
            {axis.name}
            <span className="vs-options__required" aria-hidden="true">
              *
            </span>
          </span>
          <div className="vs-options__row">
            {axis.values.map((value) => {
              const candidates = candidatesFor(axis, value);
              const unavailable = candidates.length === 0;
              const out = !unavailable && candidates.every((variant) => variant.stock_quantity <= 0);
              return (
                <button
                  key={value.id}
                  type="button"
                  className="vs-option"
                  aria-pressed={choice[axis.id] === value.id}
                  data-out={out || unavailable}
                  disabled={unavailable}
                  onClick={() => pick(axis, value)}
                >
                  {value.value}
                  {out && <span className="vs-option__out"> — نفد</span>}
                </button>
              );
            })}
          </div>
        </div>
      ))}
      {error && (
        <p className="vs-options__error" id="vs-option-error" role="alert">
          {error}
        </p>
      )}
    </fieldset>
  );
}
