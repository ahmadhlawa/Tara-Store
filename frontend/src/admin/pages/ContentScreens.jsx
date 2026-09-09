import { useCallback, useEffect, useMemo, useState } from "react";
import { adminApi } from "../../api/adminApi.js";
import ResourceScreen from "../ResourceScreen.jsx";
import { Badge } from "../ui.jsx";

const activeColumn = {
  key: "is_active",
  title: "الحالة",
  render: (row) => <Badge tone={row.is_active ? "good" : "bad"}>{row.is_active ? "ظاهر" : "مخفي"}</Badge>,
};

export function HeroSlidesPage() {
  const fetchList = useCallback(() => adminApi.listHeroSlides(), []);
  const [categories, setCategories] = useState([]);
  useEffect(() => {
    adminApi.listCategories({ page_size: 100 })
      .then((result) => setCategories(result.items || []))
      .catch(() => setCategories([]));
  }, []);
  const fields = useMemo(() => [
    { name: "image_url", title: "الصورة", type: "media", required: true, hint: "المقاس الموصى به لسطح المكتب: 2100×800 بكسل (21:8)." },
    {
      name: "target_type", title: "وجهة الإعلان", type: "select", required: true, defaultValue: "none",
      options: [
        { value: "none", label: "بدون وجهة" },
        { value: "shop", label: "كل المنتجات" },
        { value: "offers", label: "العروض" },
        { value: "packages", label: "البكجات" },
        { value: "categories", label: "كل الأقسام" },
        { value: "category", label: "قسم محدد" },
      ],
    },
    {
      name: "target_slug", title: "القسم", type: "select", required: true,
      options: categories.map((category) => ({ value: category.slug, label: `${category.name}${category.is_active ? "" : " — مخفي"}` })),
      showWhen: (values) => values.target_type === "category",
    },
    { name: "sort_order", title: "الترتيب", type: "number", defaultValue: 0 },
    { name: "is_active", title: "ظاهر", type: "checkbox", defaultValue: true },
  ], [categories]);
  return (
    <ResourceScreen
      title="شرائح الواجهة"
      description="اختر صورة الإعلان الجاهزة من مكتبة الوسائط. تُعرض الصورة كما هي في أعلى الصفحة الرئيسية."
      createLabel="إضافة شريحة"
      fetchList={fetchList}
      createItem={adminApi.createHeroSlide}
      updateItem={adminApi.updateHeroSlide}
      deleteItem={adminApi.deleteHeroSlide}
      describeRow={() => "صورة الواجهة"}
      columns={[
        { key: "image_url", title: "الصورة", render: (row) => row.image_url ? "تم اختيار صورة" : "—" },
        { key: "sort_order", title: "الترتيب" },
        activeColumn,
      ]}
      fields={fields}
      preparePayload={(payload) => ({
        ...payload,
        target_slug: payload.target_type === "category" ? payload.target_slug : null,
        button_url: null,
      })}
    />
  );
}
