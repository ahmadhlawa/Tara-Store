import { useScrollLock } from "../../../hooks/useScrollLock.js";
import { useFocusTrap } from "../../../hooks/useFocusTrap.js";

/**
 * The scrim. Not focusable: every overlay carries its own close button, so a
 * second tab stop that reads as "button" would only add noise.
 */
function Scrim({ onClose }) {
  return <div className="vs-scrim" aria-hidden="true" onClick={onClose} />;
}

/**
 * Side panel. `side` is physical and deliberate: "right" for navigation and
 * filters, which is where their triggers live in this RTL layout, "left" for the
 * cart so the two can never collide, "top" for the search sheet.
 */
export function Drawer({
  open,
  onClose,
  side = "right",
  label,
  title,
  wide = false,
  head = null,
  footer = null,
  bodyClass = "",
  className = "",
  id,
  hoverProps = null,
  autoFocus = true,
  children,
}) {
  useScrollLock(open);
  const ref = useFocusTrap(open, { onEscape: onClose, autoFocus });
  if (!open) return null;

  return (
    <>
      <Scrim onClose={onClose} />
      <aside
        ref={ref}
        id={id}
        role="dialog"
        aria-modal="true"
        aria-label={label || title}
        className={`vs-drawer vs-drawer--${side}${wide ? " vs-drawer--wide" : ""}${
          className ? ` ${className}` : ""
        }`}
        {...(hoverProps || {})}
      >
        <div className="vs-drawer__head">
          {head}
          {title && <strong className="vs-drawer__title">{title}</strong>}
          <button
            type="button"
            className="vs-iconbtn vs-drawer__close"
            onClick={onClose}
            aria-label="إغلاق"
          >
            <CloseIcon />
          </button>
        </div>
        <div className={`vs-drawer__body ${bodyClass}`.trim()}>{children}</div>
        {footer && <div className="vs-drawer__foot">{footer}</div>}
      </aside>
    </>
  );
}

/** Centred dialog on desktop, bottom sheet on mobile. */
export function Modal({ open, onClose, label, children }) {
  useScrollLock(open);
  const ref = useFocusTrap(open, { onEscape: onClose });
  if (!open) return null;

  return (
    <>
      <Scrim onClose={onClose} />
      <div className="vs-modal-wrap">
        <div ref={ref} role="dialog" aria-modal="true" aria-label={label} className="vs-modal">
          <button
            type="button"
            className="vs-iconbtn vs-modal__close"
            onClick={onClose}
            aria-label="إغلاق"
          >
            <CloseIcon />
          </button>
          <div className="vs-modal__body">{children}</div>
        </div>
      </div>
    </>
  );
}

export function CloseIcon() {
  return (
    <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
      <path d="M6 6l12 12M18 6 6 18" />
    </svg>
  );
}
