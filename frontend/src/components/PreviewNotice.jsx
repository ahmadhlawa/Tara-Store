import sx from "../sx.js";

/**
 * A build-time notice that this storefront is showing demonstration content.
 *
 * Controlled entirely by `VITE_PREVIEW_NOTICE`. Unset or blank renders nothing at all,
 * so a production build carries neither the markup nor the text — this is a preview
 * affordance, never part of the store's identity. To turn it off, remove the variable
 * from `frontend/.env` (or `.env.production`) and rebuild.
 *
 * It says nothing about the business, quotes no policy and makes no commercial claim:
 * it only warns that what follows is not real data.
 */
export function previewNoticeText(env = import.meta.env) {
  const value = env?.VITE_PREVIEW_NOTICE;
  return typeof value === "string" && value.trim() ? value.trim() : "";
}

export default function PreviewNotice({ text = previewNoticeText() }) {
  if (!text) return null;

  return (
    <div
      role="status"
      data-testid="preview-notice"
      style={sx`background:#3F2A63;color:#F6E3A1;text-align:center;padding:7px 14px;font-size:12.5px;line-height:1.7;letter-spacing:.01em`}
    >
      {text}
    </div>
  );
}
