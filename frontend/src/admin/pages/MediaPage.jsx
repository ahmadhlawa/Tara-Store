import { useCallback, useEffect, useState } from "react";
import sx from "../../sx.js";
import { adminApi } from "../../api/adminApi.js";
import { MediaUploader } from "../mediaUpload.jsx";
import {
  Button,
  ConfirmDialog,
  PageHeader,
  Pagination,
  Spinner,
  card,
  useFeedback,
} from "../ui.jsx";

export default function MediaPage() {
  const feedback = useFeedback();
  const [items, setItems] = useState([]);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [confirming, setConfirming] = useState(null);
  const [copied, setCopied] = useState(null);
  const [editing, setEditing] = useState(null);
  const [filename, setFilename] = useState("");
  const [renaming, setRenaming] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const result = await adminApi.listMedia({ page, page_size: 24, q: query || undefined });
      setItems(result.items);
      setPages(result.pages);
    } catch (error) {
      feedback.error(error.message || "تعذّر تحميل الملفات.");
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, query]);

  useEffect(() => {
    load();
  }, [load]);

  // Uploads are done by the time this runs; the library just has to catch up. Newly
  // uploaded assets are the newest rows, so page one is where they show.
  const uploaded = async (assets) => {
    feedback.success(`تم رفع ${assets.length} ملفاً.`);
    if (page !== 1) setPage(1);
    else await load();
  };

  const remove = async () => {
    const asset = confirming;
    setConfirming(null);
    try {
      await adminApi.deleteMedia(asset.id);
      feedback.success("تم حذف الملف.");
      await load();
    } catch (error) {
      feedback.error(error.message || "تعذّر حذف الملف.");
    }
  };

  const beginRename = (asset) => {
    setEditing(asset.id);
    setFilename(asset.original_filename);
  };

  const rename = async () => {
    setRenaming(true);
    try {
      await adminApi.renameMedia(editing, { original_filename: filename });
      setEditing(null);
      await load();
    } catch (error) {
      feedback.error(error.message || "تعذّر تعديل اسم الملف.");
    } finally {
      setRenaming(false);
    }
  };

  const copy = async (url) => {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(url);
      setTimeout(() => setCopied(null), 2000);
    } catch {
      feedback.error("تعذّر النسخ — انسخ الرابط يدوياً.");
    }
  };

  return (
    <>
      <PageHeader
        title="الوسائط"
        description="مكتبة صور المتجر. تُختار هذه الصور مباشرة من حقول الصور في لوحة الإدارة، ويبقى نسخ الرابط متاحاً عند الحاجة."
      />
      {feedback.node}

      <div style={{ ...card, marginBottom: "14px" }}>
        <MediaUploader onUploaded={uploaded} />
      </div>

      <div style={card}>
        <div style={sx`margin-bottom:14px`}>
          <input
            aria-label="بحث باسم الملف"
            type="search"
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setPage(1);
            }}
            placeholder="بحث باسم الملف"
            style={sx`width:100%;max-width:320px;padding:10px 12px;border:1px solid #DCCDBC;border-radius:9px;font:inherit`}
          />
        </div>
        {loading ? (
          <Spinner />
        ) : items.length === 0 ? (
          <p style={sx`padding:36px;text-align:center;color:#766669;font-size:14px`}>
            {query ? "لا توجد وسائط مطابقة." : "لم تُرفع أي ملفات بعد."}
          </p>
        ) : (
          <div style={sx`display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:14px`}>
            {items.map((asset) => (
              <div key={asset.id} style={sx`border:1px solid #E7DCF2;border-radius:12px;overflow:hidden;display:flex;flex-direction:column`}>
                <span style={sx`aspect-ratio:1 / 1;background:url("${asset.url}") center/cover no-repeat;background-color:#F5EDE3`}></span>
                <div style={sx`padding:10px;display:flex;flex-direction:column;gap:8px`}>
                  <span style={sx`font-size:12px;color:#766669;overflow:hidden;text-overflow:ellipsis;white-space:nowrap`}>{asset.original_filename}</span>
                  <span style={sx`font-size:11.5px;color:#8A7F95`}>{Math.round(asset.size_bytes / 1024)} كيلوبايت</span>
                  {editing === asset.id ? (
                    <>
                      <input aria-label="اسم الملف" value={filename} onChange={(event) => setFilename(event.target.value)} style={sx`width:100%;padding:8px;border:1px solid #DCCDBC;border-radius:8px;font:inherit;font-size:12px`} />
                      <div style={sx`display:flex;gap:8px`}>
                        <Button disabled={renaming} style={sx`min-height:34px;font-size:12.5px`} onClick={rename}>حفظ</Button>
                        <Button variant="ghost" disabled={renaming} style={sx`min-height:34px;font-size:12.5px`} onClick={() => setEditing(null)}>إلغاء</Button>
                      </div>
                    </>
                  ) : (
                    <Button variant="secondary" style={sx`min-height:34px;font-size:12.5px`} onClick={() => beginRename(asset)}>تعديل الاسم</Button>
                  )}
                  <Button variant="secondary" style={sx`min-height:34px;font-size:12.5px`} onClick={() => copy(asset.url)}>
                    {copied === asset.url ? "تم النسخ ✓" : "نسخ الرابط"}
                  </Button>
                  <Button variant="danger" style={sx`min-height:34px;font-size:12.5px`} onClick={() => setConfirming(asset)}>حذف</Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
      <Pagination page={page} pages={pages} onChange={setPage} />

      {confirming && (
        <ConfirmDialog
          title="تأكيد الحذف"
          message={`سيُحذف الملف «${confirming.original_filename}» نهائياً. تأكد من أنه غير مستخدم في أي منتج.`}
          onConfirm={remove}
          onCancel={() => setConfirming(null)}
        />
      )}
    </>
  );
}
