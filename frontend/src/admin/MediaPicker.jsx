import { useCallback, useEffect, useRef, useState } from "react";
import sx from "../sx.js";
import { adminApi } from "../api/adminApi.js";
import { Button, Modal, Notice, Pagination, Spinner, input, label } from "./ui.jsx";

// The picker only ever speaks the media API's contract: it reads `url` off an asset
// and hands that back to the field. Where the bytes actually live (local disk today,
// object storage later) is the backend media layer's business, never this component's.

const PAGE_SIZE = 24;

/** The library browser. Nothing is handed back until the admin confirms a choice. */
export function MediaPickerDialog({ onSelect, onClose, initialUrl = null, mode = "single", excludeUrls = [] }) {
  const fileRef = useRef(null);
  const pageCache = useRef(new Map());
  const [items, setItems] = useState([]);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [listError, setListError] = useState(null);
  const [uploadError, setUploadError] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [selected, setSelected] = useState(initialUrl ? [initialUrl] : []);

  useEffect(() => { const timer = setTimeout(() => { setSearch(query); setPage(1); }, 300); return () => clearTimeout(timer); }, [query]);

  const load = useCallback(async () => {
    setLoading(true);
    setListError(null);
    try {
      const key = `${page}:${search}`;
      const result = pageCache.current.get(key) || await adminApi.listMedia({ page, page_size: PAGE_SIZE, q: search || undefined });
      pageCache.current.set(key, result);
      setItems(result.items || []);
      setPages(result.pages || 1);
    } catch (error) {
      setListError(error.message || "تعذّر تحميل مكتبة الوسائط.");
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [page, search]);

  useEffect(() => {
    load();
  }, [load]);

  const upload = async (event) => {
    const file = event.target.files?.[0];
    if (fileRef.current) fileRef.current.value = "";
    if (!file) return;
    setUploading(true);
    setUploadError(null);
    try {
      const asset = await adminApi.uploadMedia(file);
      // Show it straight away and pre-select it — the admin uploaded it to use it.
      setItems((current) => [asset, ...current]);
      pageCache.current.clear();
      setSelected([asset.url]);
    } catch (error) {
      setUploadError(error.message || "تعذّر رفع الصورة.");
    } finally {
      setUploading(false);
    }
  };

  return (
    <Modal
      title="مكتبة الوسائط"
      wide
      onClose={onClose}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>إلغاء</Button>
          <Button aria-label={mode === "multiple" && selected.length === 1 ? "اختيار" : undefined} disabled={!selected.length} onClick={() => onSelect(mode === "multiple" ? selected : selected[0])}>{mode === "multiple" ? `إضافة ${selected.length} صور` : "اختيار"}</Button>
        </>
      }
    >
      <div style={sx`display:flex;gap:10px;flex-wrap:wrap;align-items:center`}>
        <input ref={fileRef} type="file" accept="image/*" onChange={upload} aria-label="رفع صورة جديدة" style={sx`display:none`} />
        <Button variant="secondary" disabled={uploading} onClick={() => fileRef.current?.click()}>
          {uploading ? "جارٍ الرفع…" : "رفع صورة جديدة"}
        </Button>
        <span style={sx`font-size:12px;color:#8A7F95`}>JPEG، PNG، WebP، GIF، ICO — بحد أقصى ٥ ميغابايت.</span>
      </div>

      <input
        aria-label="بحث باسم الملف"
        type="search"
        value={query}
        onChange={(event) => {
          setQuery(event.target.value);
        }}
        placeholder="بحث باسم الملف"
        style={sx`width:100%;margin-top:12px;padding:10px 12px;border:1px solid #DCCDBC;border-radius:9px;font:inherit`}
      />

      {uploadError && <Notice kind="error">{uploadError}</Notice>}

      {loading ? (
        <Spinner />
      ) : listError ? (
        <div style={sx`display:flex;flex-direction:column;gap:10px;align-items:flex-start`}>
          <Notice kind="error">{listError}</Notice>
          <Button variant="secondary" onClick={load}>إعادة المحاولة</Button>
        </div>
      ) : items.length === 0 ? (
        <p style={sx`padding:28px;text-align:center;color:#766669;font-size:14px`}>
          {query ? "لا توجد وسائط مطابقة." : "لا توجد صور في المكتبة بعد — ارفع صورة جديدة."}
        </p>
      ) : (
        <div className="admin-media-picker-grid" style={sx`max-height:var(--admin-media-picker-max-height,min(52vh,420px));overflow-y:auto;display:grid;grid-template-columns:repeat(auto-fill,minmax(var(--admin-media-picker-card-min,130px),1fr));gap:var(--admin-media-picker-grid-gap,12px);padding:2px`}>
          {items.filter((asset) => !query || asset.original_filename.toLocaleLowerCase().includes(query.toLocaleLowerCase())).map((asset) => {
            const active = selected.includes(asset.url);
            const excluded = excludeUrls.includes(asset.url);
            return (
              <button
                key={asset.id}
                type="button"
                aria-pressed={active}
                disabled={excluded}
                onClick={() => setSelected((current) => mode === "multiple" ? (current.includes(asset.url) ? current.filter((url) => url !== asset.url) : [...current, asset.url]) : [asset.url])}
                onDoubleClick={() => mode === "single" && onSelect(asset.url)}
                style={sx`text-align:start;padding:0;background:#fff;cursor:pointer;border-radius:12px;overflow:hidden;font-family:inherit;display:flex;flex-direction:column;border:2px solid ${active ? "var(--admin-selection-border)" : "#E7DCF2"};box-shadow:${active ? "0 0 0 3px var(--admin-primary-16)" : "none"}`}
              >
                <span style={sx`position:relative;aspect-ratio:1 / 1;background:#F5EDE3`}><img src={asset.thumbnail_url || asset.url} alt="" loading="lazy" decoding="async" width="320" height="320" style={sx`width:100%;height:100%;object-fit:cover`} />{active && <b aria-hidden="true" style={sx`position:absolute;inset-block-start:7px;inset-inline-end:7px;width:24px;height:24px;border-radius:50%;display:grid;place-items:center;background:var(--admin-primary);color:white`}>✓</b>}</span>
                <span style={sx`padding:8px;font-size:11.5px;color:#4B4155;overflow:hidden;text-overflow:ellipsis;white-space:nowrap`}>
                  {asset.original_filename}
                </span>
              </button>
            );
          })}
        </div>
      )}

      <Pagination page={page} pages={pages} onChange={setPage} />
    </Modal>
  );
}

/**
 * An image field backed by the media library. The stored value stays what it always
 * was — a plain URL string — so existing external links keep working and nothing
 * downstream needs to know a picker exists.
 */
export function MediaField({ title, hint, value, onChange }) {
  const [picking, setPicking] = useState(false);
  const [manual, setManual] = useState(false);

  return (
    <div style={{ ...label, gap: "8px" }}>
      <span>{title}</span>
      {value ? (
        <div style={sx`display:flex;gap:10px;align-items:center;border:1px solid #E7DCF2;border-radius:10px;padding:8px;background:#FAF7FD`}>
          <span style={sx`width:56px;height:56px;flex:0 0 auto;border-radius:8px;background:#F5EDE3 url("${value}") center/cover no-repeat`}></span>
          <span style={sx`flex:1;min-width:0;font-size:11.5px;font-weight:400;color:#766669;overflow:hidden;text-overflow:ellipsis;white-space:nowrap`} title={value}>
            {value}
          </span>
          <Button variant="danger" style={sx`min-height:34px;padding:0 12px;font-size:12.5px`} onClick={() => onChange("")}>
            إزالة
          </Button>
        </div>
      ) : (
        <span style={sx`font-size:12px;font-weight:400;color:#8A7F95`}>لا توجد صورة محددة.</span>
      )}

      <div style={sx`display:flex;gap:8px;flex-wrap:wrap`}>
        <Button variant="secondary" style={sx`min-height:38px;font-size:13px`} onClick={() => setPicking(true)}>
          اختيار من مكتبة الوسائط
        </Button>
        <Button variant="ghost" style={sx`min-height:38px;font-size:13px`} onClick={() => setManual((current) => !current)}>
          إدخال رابط صورة يدويًا
        </Button>
      </div>

      {manual && (
        <input
          type="text"
          value={value ?? ""}
          aria-label={`${title} — رابط يدوي`}
          placeholder="https://…"
          onChange={(event) => onChange(event.target.value)}
          style={input}
        />
      )}

      {hint && <span style={sx`font-size:11.5px;font-weight:400;color:#8A7F95`}>{hint}</span>}

      {picking && (
        <MediaPickerDialog
          initialUrl={value || null}
          onClose={() => setPicking(false)}
          onSelect={(url) => {
            onChange(url);
            setPicking(false);
          }}
        />
      )}
    </div>
  );
}

export default MediaField;
