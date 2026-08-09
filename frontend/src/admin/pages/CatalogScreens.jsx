import { useCallback, useEffect, useState } from "react";
import { adminApi } from "../../api/adminApi.js";
import ResourceScreen from "../ResourceScreen.jsx";
import { Badge } from "../ui.jsx";

export function CategoriesPage() {
  const [parents, setParents] = useState([]);

  useEffect(() => {
    adminApi
      .listCategories({ page_size: 100 })
      .then((result) => setParents(result.items || []))
      .catch(() => setParents([]));
  }, []);

  const fetchList = useCallback((params) => adminApi.listCategories(params), []);

  return (
    <ResourceScreen
      title="الأقسام"
      description="أقسام المتجر وترتيب ظهورها في الواجهة."
      paginated
      createLabel="إضافة قسم"
      fetchList={fetchList}
      createItem={adminApi.createCategory}
      updateItem={adminApi.updateCategory}
      deleteItem={adminApi.deleteCategory}
      columns={[
        { key: "name", title: "الاسم" },
        { key: "slug", title: "الرابط" },
        { key: "product_count", title: "عدد المنتجات" },
        { key: "sort_order", title: "الترتيب" },
        {
          key: "is_active",
          title: "الحالة",
          render: (row) => (
            <Badge tone={row.is_active ? "good" : "bad"}>{row.is_active ? "فعّال" : "مخفي"}</Badge>
          ),
        },
      ]}
      fields={[
        { name: "name", title: "اسم القسم", required: true },
        { name: "slug", title: "الرابط (اختياري)", hint: "يُولَّد من الاسم إذا تُرك فارغاً", omitWhenEmpty: true },
        { name: "description", title: "الوصف", type: "textarea", rows: 3 },
        { name: "image_url", title: "صورة القسم", type: "media", emptyAsNull: true },
        {
          name: "parent_id",
          title: "القسم الأب",
          type: "select",
          emptyAsNull: true,
          options: parents.map((row) => ({ value: row.id, label: row.name })),
        },
        { name: "sort_order", title: "الترتيب", type: "number", defaultValue: 0 },
        { name: "is_featured", title: "قسم مميّز", type: "checkbox" },
        { name: "is_active", title: "فعّال", type: "checkbox", defaultValue: true },
      ]}
    />
  );
}
