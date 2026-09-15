import { useEffect, useState } from "react";
import { adminApi } from "../../api/adminApi.js";
import sx from "../../sx.js";
import { MediaPickerDialog } from "../MediaPicker.jsx";
import { Button, Notice, PageHeader, Spinner, card, useFeedback } from "../ui.jsx";

const preview = sx`width:160px;height:72px;object-fit:cover;border-radius:10px;border:1px solid #E7DCF2;background:#FAF7FD`;

export default function CategoryBannersPage() {
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [savingId, setSavingId] = useState(null);
  const [picking, setPicking] = useState(null);
  const feedback = useFeedback();

  useEffect(() => {
    let ignore = false;
    adminApi.listCategories({ page_size: 100 }).then((result) => {
      if (!ignore) setCategories((result.items || []).filter((item) => item.parent_id == null));
    }).catch(() => {
      if (!ignore) feedback.error("تعذّر تحميل الأقسام.");
    }).finally(() => {
      if (!ignore) setLoading(false);
    });
    return () => { ignore = true; };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function save(category, bannerImageUrl) {
    setSavingId(category.id);
    try {
      const updated = await adminApi.updateCategory(category.id, { banner_image_url: bannerImageUrl });
      setCategories((items) => items.map((item) => item.id === category.id ? updated : item));
      feedback.success(bannerImageUrl ? "تم حفظ بانر القسم." : "تمت إزالة البانر.");
    } catch {
      feedback.error("تعذّر حفظ بانر القسم.");
    } finally {
      setSavingId(null);
    }
  }

  return (
    <div>
      <PageHeader title="بنرات الأقسام" description="صور مخصّصة لرأس صفحات الأقسام الرئيسية فقط." />
      {feedback.node}
      {loading ? <Spinner /> : categories.length === 0 ? (
        <Notice>لا توجد أقسام رئيسية لإدارة بنراتها.</Notice>
      ) : (
        <div style={sx`display:grid;gap:14px`}>
          {categories.map((category) => (
            <section key={category.id} style={sx`${card};display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:18px`}>
              <div style={sx`min-width:140px;flex:1`}><strong style={sx`display:block;color:#3B3243;margin-bottom:4px`}>{category.name}</strong><span style={sx`font-size:12px;color:#766669`}>صورة القسم الحالية</span></div>
              <div style={sx`display:flex;gap:14px;align-items:center;flex-wrap:wrap`}>
                {category.image_url ? <img src={category.image_url} alt={`صورة قسم ${category.name}`} style={preview} /> : <span style={sx`width:160px;text-align:center;color:#8A7F95;font-size:12px`}>لا توجد صورة قسم</span>}
                {category.banner_image_url ? <img src={category.banner_image_url} alt={`بانر قسم ${category.name}`} style={preview} /> : <span style={sx`width:160px;text-align:center;color:#8A7F95;font-size:12px`}>لا يوجد بانر مخصّص</span>}
              </div>
              <div style={sx`display:flex;gap:8px;flex-wrap:wrap`}>
                <Button variant="secondary" disabled={savingId === category.id} onClick={() => setPicking(category)}>اختيار من مكتبة الوسائط</Button>
                {category.banner_image_url && <Button variant="danger" disabled={savingId === category.id} onClick={() => save(category, null)}>إزالة البانر</Button>}
              </div>
            </section>
          ))}
        </div>
      )}
      {picking && <MediaPickerDialog mode="single" initialUrl={picking.banner_image_url} onClose={() => setPicking(null)} onSelect={(url) => { const category = picking; setPicking(null); save(category, url); }} />}
    </div>
  );
}
