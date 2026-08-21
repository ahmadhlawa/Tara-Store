// Shared bulk-upload plumbing for the admin media library.
//
// Storage stays the backend's business: this module only ever hands a `File` to
// `adminApi.uploadMedia` and reads the asset it gets back. No paths, buckets or
// provider names appear here, so moving the storage layer changes nothing above.

import { useCallback, useRef, useState } from "react";
import sx from "../sx.js";
import { adminApi } from "../api/adminApi.js";
import { Button } from "./ui.jsx";

/** Mirrors the backend's allowed types — early UX feedback only; the API still decides. */
export const ALLOWED_UPLOAD_TYPES = [
  "image/jpeg",
  "image/png",
  "image/webp",
  "image/gif",
  "image/x-icon",
  "image/vnd.microsoft.icon",
];
export const UPLOAD_ACCEPT = ALLOWED_UPLOAD_TYPES.join(",");
export const MAX_UPLOAD_BYTES = 5 * 1024 * 1024;
export const UPLOAD_HINT = "الأنواع المسموحة: JPEG و PNG و WebP و GIF و ICO، بحد أقصى ٥ ميغابايت.";
export const DUPLICATE_NAME_MESSAGE = "يوجد ملف بهذا الاسم بالفعل.";

/** How many uploads may be in flight at once. Enough to be quick, few enough to be polite. */
const CONCURRENCY = 4;

/** Returns a reason string when the file cannot possibly be accepted, else `null`. */
export function validateUploadFile(file) {
  if (file.size === 0) return "الملف فارغ.";
  if (file.size > MAX_UPLOAD_BYTES) return "حجم الملف يتجاوز ٥ ميغابايت.";
  // An empty `type` means the browser could not tell; let the backend sniff the bytes.
  if (file.type && !ALLOWED_UPLOAD_TYPES.includes(file.type)) return "نوع الملف غير مدعوم.";
  return null;
}

let nextId = 0;

/**
 * A queue of uploads that survives individual failures: a rejected file is marked
 * and the rest keep going. Failed entries keep their `File`, so retry is a re-run,
 * not a re-pick.
 */
export function useUploadQueue({ onUploaded } = {}) {
  const [items, setItems] = useState([]);
  const [running, setRunning] = useState(false);
  // The queue is mutated from concurrent workers and read while deciding what to
  // enqueue next, so the ref — not the render-time state — is the source of truth.
  const itemsRef = useRef(items);
  const pendingRef = useRef([]);
  const runningRef = useRef(false);
  const uploadedRef = useRef(onUploaded);
  uploadedRef.current = onUploaded;

  const commit = useCallback((next) => {
    itemsRef.current = next;
    setItems(next);
  }, []);

  const patch = useCallback(
    (id, changes) =>
      commit(itemsRef.current.map((item) => (item.id === id ? { ...item, ...changes } : item))),
    [commit],
  );

  const drain = useCallback(async () => {
    if (runningRef.current) return;
    runningRef.current = true;
    setRunning(true);
    const uploaded = [];

    const worker = async () => {
      for (;;) {
        const entry = pendingRef.current.shift();
        if (!entry) return;
        patch(entry.id, { status: "uploading", error: null });
        try {
          const asset = await adminApi.uploadMedia(entry.file);
          uploaded.push(asset);
          patch(entry.id, { status: "success", error: null });
        } catch (error) {
          patch(entry.id, { status: "failed", error: error?.message || "تعذّر رفع الملف." });
        }
      }
    };

    await Promise.all(Array.from({ length: CONCURRENCY }, worker));
    runningRef.current = false;
    setRunning(false);
    if (uploaded.length) await uploadedRef.current?.(uploaded);
  }, [patch]);

  /** Queue a `FileList`/array. Obviously-bad files land as failed without a request. */
  const enqueue = useCallback(
    (files) => {
      const incoming = Array.from(files || []);
      if (incoming.length === 0) return;

      // Names already accounted for in this session, so one batch cannot queue the
      // same name twice and race the backend's uniqueness check.
      const claimed = new Set(
        itemsRef.current.filter((item) => item.status !== "failed").map((item) => item.name),
      );
      const added = incoming.map((file) => {
        const name = file.name || "upload";
        const reason = claimed.has(name) ? DUPLICATE_NAME_MESSAGE : validateUploadFile(file);
        if (!reason) claimed.add(name);
        const entry = {
          id: `u${nextId++}`,
          file,
          name,
          status: reason ? "failed" : "waiting",
          error: reason,
        };
        if (!reason) pendingRef.current.push(entry);
        return entry;
      });

      commit([...itemsRef.current, ...added]);
      drain();
    },
    [commit, drain],
  );

  const retry = useCallback(
    (id = null) => {
      const targets = itemsRef.current.filter(
        (item) => item.status === "failed" && (id === null || item.id === id),
      );
      if (targets.length === 0) return;
      const retried = new Set(targets.map((item) => item.id));
      pendingRef.current.push(...targets.map(({ id: entryId, file }) => ({ id: entryId, file })));
      commit(
        itemsRef.current.map((item) =>
          retried.has(item.id) ? { ...item, status: "waiting", error: null } : item,
        ),
      );
      drain();
    },
    [commit, drain],
  );

  const remove = useCallback(
    (id) => {
      pendingRef.current = pendingRef.current.filter((entry) => entry.id !== id);
      commit(itemsRef.current.filter((item) => item.id !== id));
    },
    [commit],
  );

  const clearFinished = useCallback(
    () => commit(itemsRef.current.filter((item) => item.status !== "success")),
    [commit],
  );

  const succeeded = items.filter((item) => item.status === "success").length;
  const failed = items.filter((item) => item.status === "failed").length;

  return { items, running, succeeded, failed, enqueue, retry, remove, clearFinished };
}

const STATUS_LABEL = {
  waiting: "في الانتظار",
  uploading: "جارٍ الرفع…",
  success: "تم الرفع ✓",
  failed: "فشل",
};

const STATUS_COLOR = {
  waiting: "#766669",
  uploading: "var(--admin-primary)",
  success: "#4C7C63",
  failed: "#A33F37",
};

const dropzone = (active) =>
  sx`display:flex;flex-direction:column;align-items:center;gap:10px;text-align:center;padding:22px 14px;border:2px dashed ${active ? "var(--admin-primary)" : "#DFD2EC"};border-radius:14px;background:${active ? "var(--brand-soft)" : "#FAF7FD"}`;

/**
 * Drop zone + queue. The parent hears about finished uploads through `onUploaded`
 * and decides what to refresh.
 */
export function MediaUploader({ onUploaded }) {
  const fileRef = useRef(null);
  const [dragging, setDragging] = useState(false);
  const queue = useUploadQueue({ onUploaded });

  const pick = (event) => {
    queue.enqueue(event.target.files);
    if (fileRef.current) fileRef.current.value = "";
  };

  const drop = (event) => {
    event.preventDefault();
    setDragging(false);
    queue.enqueue(event.dataTransfer?.files);
  };

  return (
    <div style={sx`display:flex;flex-direction:column;gap:12px`}>
      <div
        data-testid="media-dropzone"
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={drop}
        style={dropzone(dragging)}
      >
        <input
          ref={fileRef}
          type="file"
          multiple
          accept={UPLOAD_ACCEPT}
          aria-label="اختيار صور للرفع"
          onChange={pick}
          style={sx`display:none`}
        />
        <span style={sx`font-size:13.5px;color:#4B4155`}>اسحب الصور إلى هنا، أو</span>
        <Button variant="secondary" onClick={() => fileRef.current?.click()}>
          اختيار صور
        </Button>
        <span style={sx`font-size:11.5px;color:#8A7F95;max-width:100%`}>{UPLOAD_HINT}</span>
      </div>

      {queue.items.length > 0 && (
        <div style={sx`display:flex;flex-direction:column;gap:10px`}>
          <div style={sx`display:flex;flex-wrap:wrap;gap:8px;align-items:center;justify-content:space-between`}>
            <span data-testid="upload-summary" style={sx`font-size:13px;color:#4B4155`}>
              {queue.running
                ? `جارٍ الرفع… (${queue.succeeded} تم رفعه، ${queue.failed} فشل)`
                : `${queue.succeeded} تم رفعه، ${queue.failed} فشل`}
            </span>
            <span style={sx`display:flex;gap:8px;flex-wrap:wrap`}>
              {queue.failed > 0 && (
                <Button
                  variant="secondary"
                  style={sx`min-height:34px;font-size:12.5px`}
                  disabled={queue.running}
                  onClick={() => queue.retry()}
                >
                  إعادة محاولة الفاشل
                </Button>
              )}
              {queue.succeeded > 0 && (
                <Button
                  variant="ghost"
                  style={sx`min-height:34px;font-size:12.5px`}
                  onClick={queue.clearFinished}
                >
                  إخفاء المكتمل
                </Button>
              )}
            </span>
          </div>

          <ul
            data-testid="upload-queue"
            style={sx`list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:6px;max-height:min(46vh,340px);overflow-y:auto;overflow-x:hidden`}
          >
            {queue.items.map((item) => (
              <li
                key={item.id}
                data-testid="upload-item"
                style={sx`display:flex;flex-wrap:wrap;gap:8px;align-items:center;border:1px solid #E7DCF2;border-radius:10px;padding:8px 10px;background:#fff`}
              >
                <span
                  title={item.name}
                  style={sx`flex:1 1 140px;min-width:0;font-size:12.5px;color:#3B3243;overflow:hidden;text-overflow:ellipsis;white-space:nowrap`}
                >
                  {item.name}
                </span>
                <span style={sx`font-size:12px;flex:0 0 auto;color:${STATUS_COLOR[item.status]}`}>
                  {STATUS_LABEL[item.status]}
                </span>
                {item.error && (
                  <span style={sx`flex:1 1 100%;font-size:11.5px;color:#A33F37;overflow-wrap:anywhere`}>
                    {item.error}
                  </span>
                )}
                <span style={sx`display:flex;gap:6px;flex:0 0 auto`}>
                  {item.status === "failed" && (
                    <Button
                      variant="secondary"
                      style={sx`min-height:30px;padding:0 10px;font-size:12px`}
                      onClick={() => queue.retry(item.id)}
                    >
                      إعادة المحاولة
                    </Button>
                  )}
                  {item.status !== "uploading" && (
                    <Button
                      variant="ghost"
                      style={sx`min-height:30px;padding:0 10px;font-size:12px`}
                      aria-label={`إزالة ${item.name} من القائمة`}
                      onClick={() => queue.remove(item.id)}
                    >
                      إزالة
                    </Button>
                  )}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export default MediaUploader;
