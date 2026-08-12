import { useEffect, useState } from "react";
import sx from "../sx.js";

export const card = sx`background:#fff;border:1px solid #E7DCF2;border-radius:14px;padding:18px`;
export const label = sx`display:flex;flex-direction:column;gap:6px;font-size:13px;font-weight:700;color:#3B3243`;
export const input = sx`height:44px;border:1px solid #DFD2EC;border-radius:10px;background:#FAF7FD;padding:0 12px;font-size:14px;font-weight:400;font-family:inherit;width:100%;box-sizing:border-box`;
export const textarea = sx`border:1px solid #DFD2EC;border-radius:10px;background:#FAF7FD;padding:10px 12px;font-size:14px;font-weight:400;font-family:inherit;width:100%;box-sizing:border-box;resize:vertical`;

export function Button({ variant = "primary", children, style, ...rest }) {
  const variants = {
    primary: "background:#7F568F;color:#fff;border:1px solid #7F568F",
    secondary: "background:#fff;color:#7F568F;border:1px solid #7F568F",
    ghost: "background:#fff;color:#4B4155;border:1px solid #DFD2EC",
    danger: "background:#fff;color:#B4534A;border:1px solid #E5C4BE",
  };
  return (
    <button
      type="button"
      {...rest}
      style={{
        ...sx`min-height:44px;padding:0 18px;border-radius:10px;font-size:14px;font-weight:700;font-family:inherit;cursor:pointer;display:inline-flex;align-items:center;justify-content:center;gap:8px;${variants[variant]}`,
        ...(rest.disabled ? { opacity: 0.6, cursor: "not-allowed" } : null),
        ...style,
      }}
    >
      {children}
    </button>
  );
}

export function PageHeader({ title, description, actions }) {
  return (
    <div style={sx`display:flex;align-items:flex-end;justify-content:space-between;gap:16px;flex-wrap:wrap;margin-bottom:18px`}>
      <div style={sx`display:flex;flex-direction:column;gap:4px`}>
        <h1 style={sx`margin:0;font-size:22px;font-weight:800;color:#3B3243`}>{title}</h1>
        {description && <p style={sx`margin:0;font-size:13.5px;color:#766669`}>{description}</p>}
      </div>
      {actions && <div style={sx`display:flex;gap:10px;flex-wrap:wrap`}>{actions}</div>}
    </div>
  );
}

export function Field({ title, hint, children }) {
  return (
    <label style={label}>
      {title}
      {children}
      {hint && <span style={sx`font-size:11.5px;font-weight:400;color:#8A7F95`}>{hint}</span>}
    </label>
  );
}

export function Notice({ kind = "info", children }) {
  if (!children) return null;
  const styles = {
    info: "background:#F3EAFA;border-color:#DDCAEC;color:#7F568F",
    error: "background:#FBEFEC;border-color:#EBD2CD;color:#8E3B34",
    success: "background:#EEF4EF;border-color:#CCDFD3;color:#3F6B54",
  };
  return (
    <div role={kind === "error" ? "alert" : "status"} style={sx`border:1px solid;border-radius:10px;padding:12px 14px;font-size:13.5px;margin-bottom:14px;${styles[kind]}`}>
      {children}
    </div>
  );
}

/** Small toast used for CRUD feedback across the admin screens. */
export function useFeedback() {
  const [message, setMessage] = useState(null);
  useEffect(() => {
    if (!message) return undefined;
    const timer = setTimeout(() => setMessage(null), 4000);
    return () => clearTimeout(timer);
  }, [message]);
  return {
    message,
    success: (text) => setMessage({ kind: "success", text }),
    error: (text) => setMessage({ kind: "error", text }),
    clear: () => setMessage(null),
    node: message ? <Notice kind={message.kind}>{message.text}</Notice> : null,
  };
}

export function Table({ columns, rows, empty = "لا توجد بيانات بعد.", rowKey = (row) => row.id }) {
  if (!rows.length) {
    return <div style={sx`padding:40px 20px;text-align:center;color:#766669;font-size:14px`}>{empty}</div>;
  }
  return (
    // The table sizes itself to its content and the wrapper scrolls: a fixed
    // 560px floor was still narrower than a seven-column table needs, so on a
    // phone every column was crushed to a word per line. `min-width:100%` keeps
    // a short table filling the card exactly as before on a wide screen.
    <div style={sx`overflow-x:auto`}>
      <table style={sx`width:max-content;min-width:100%;border-collapse:collapse;font-size:13.5px`}>
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column.key} style={sx`text-align:start;padding:10px 12px;border-bottom:1px solid #E7DCF2;color:#766669;font-weight:700;white-space:nowrap`}>
                {column.title}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={rowKey(row)}>
              {columns.map((column) => (
                <td key={column.key} style={sx`padding:12px;border-bottom:1px solid #F5EDE3;vertical-align:middle;max-width:280px`}>
                  {column.render ? column.render(row) : row[column.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Modal({ title, onClose, children, footer, wide = false }) {
  return (
    <div role="dialog" aria-modal="true" aria-label={title} style={sx`position:fixed;inset:0;z-index:120;background:rgba(26,24,21,.45);display:flex;align-items:center;justify-content:center;padding:16px`}>
      <div style={sx`background:#fff;border-radius:16px;width:min(${wide ? "900px" : "560px"},100%);max-height:90vh;overflow-y:auto;box-shadow:0 30px 70px rgba(26,24,21,.3)`}>
        <div style={sx`display:flex;align-items:center;justify-content:space-between;gap:12px;padding:16px 20px;border-bottom:1px solid #E7DCF2;position:sticky;top:0;background:#fff`}>
          <strong style={sx`font-size:16px`}>{title}</strong>
          <button type="button" onClick={onClose} aria-label="إغلاق" style={sx`width:36px;height:36px;border:1px solid #E7DCF2;border-radius:9px;background:#fff;cursor:pointer;font-size:15px`}>✕</button>
        </div>
        <div style={sx`padding:20px;display:flex;flex-direction:column;gap:14px`}>{children}</div>
        {footer && <div style={sx`padding:14px 20px;border-top:1px solid #E7DCF2;display:flex;gap:10px;justify-content:flex-end;position:sticky;bottom:0;background:#fff`}>{footer}</div>}
      </div>
    </div>
  );
}

/** Destructive actions always ask first. */
export function ConfirmDialog({ title, message, confirmLabel = "تأكيد الحذف", onConfirm, onCancel }) {
  return (
    <Modal
      title={title}
      onClose={onCancel}
      footer={
        <>
          <Button variant="ghost" onClick={onCancel}>إلغاء</Button>
          <Button variant="danger" onClick={onConfirm}>{confirmLabel}</Button>
        </>
      }
    >
      <p style={sx`margin:0;font-size:14px;line-height:1.9;color:#4B4155`}>{message}</p>
    </Modal>
  );
}

export function Pagination({ page, pages, onChange }) {
  if (pages <= 1) return null;
  return (
    <div style={sx`display:flex;align-items:center;justify-content:center;gap:12px;padding:16px 0`}>
      <Button variant="ghost" disabled={page <= 1} onClick={() => onChange(page - 1)}>السابق</Button>
      <span style={sx`font-size:13.5px;color:#766669`}>صفحة {page} من {pages}</span>
      <Button variant="ghost" disabled={page >= pages} onClick={() => onChange(page + 1)}>التالي</Button>
    </div>
  );
}

export function Badge({ tone = "neutral", children }) {
  const tones = {
    neutral: "background:#F5EDE3;color:#4B4155",
    good: "background:#EEF4EF;color:#3F6B54",
    warn: "background:#F8EEDC;color:#8A6329",
    bad: "background:#FBEFEC;color:#8E3B34",
  };
  return (
    <span style={sx`display:inline-flex;align-items:center;padding:4px 10px;border-radius:999px;font-size:12px;font-weight:700;${tones[tone]}`}>
      {children}
    </span>
  );
}

export function Spinner({ label = "جارٍ التحميل…" }) {
  return <p style={sx`padding:30px;text-align:center;color:#766669;font-size:14px`}>{label}</p>;
}
