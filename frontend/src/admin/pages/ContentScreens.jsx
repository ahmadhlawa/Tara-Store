import { useCallback } from "react";
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
      fields={[
        { name: "image_url", title: "الصورة", type: "media", required: true },
        { name: "sort_order", title: "الترتيب", type: "number", defaultValue: 0 },
        { name: "is_active", title: "ظاهر", type: "checkbox", defaultValue: true },
      ]}
    />
  );
}
