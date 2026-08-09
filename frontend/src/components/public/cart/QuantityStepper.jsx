import { MinusIcon, PlusIcon } from "../shell/icons.jsx";

/** The one quantity control: cart lines, quick view, product page. */
export default function QuantityStepper({ value, onDecrease, onIncrease, size = "md", label }) {
  return (
    <div className={`vs-qty vs-qty--${size}`} role="group" aria-label={label || "الكمية"}>
      <button
        type="button"
        onClick={onDecrease}
        aria-label="إنقاص الكمية"
        disabled={value <= 1}
      >
        <MinusIcon size={15} />
      </button>
      <span className="vs-qty__value" aria-live="polite">
        {value}
      </span>
      <button type="button" onClick={onIncrease} aria-label="زيادة الكمية">
        <PlusIcon size={15} />
      </button>
    </div>
  );
}
