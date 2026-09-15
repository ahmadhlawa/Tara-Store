import { useCallback, useEffect, useState } from "react";
import { adminApi } from "../../api/adminApi.js";
import sx from "../../sx.js";
import ResourceScreen from "../ResourceScreen.jsx";
import { Badge } from "../ui.jsx";

export function orderCategoriesForAdmin(categories) {
  const createdFirst = (a, b) => {
    const time = String(a.created_at || "").localeCompare(String(b.created_at || ""));
    return time || a.id - b.id;
  };
  const ids = new Set(categories.map((category) => category.id));
  const childrenByParent = new Map();
  const rendered = new Set();
  const ordered = [];

  categories.forEach((category) => {
    if (category.parent_id == null || !ids.has(category.parent_id)) return;
    const children = childrenByParent.get(category.parent_id) || [];
    children.push(category);
    children.sort(createdFirst);
    childrenByParent.set(category.parent_id, children);
  });

  const append = (category, depth = 0) => {
    if (rendered.has(category.id)) return;
    rendered.add(category.id);
    ordered.push({ ...category, __categoryDepth: depth });
    (childrenByParent.get(category.id) || []).forEach((child) => append(child, depth + 1));
  };

  categories
    .filter((category) => category.parent_id == null || !ids.has(category.parent_id))
    .sort(createdFirst)
    .forEach((category) => append(category));
  categories.forEach((category) => append(category));

  return ordered;
}

export function CategoriesPage() {
  const [parents, setParents] = useState([]);

  useEffect(() => {
    adminApi
      .listCategories({ page_size: 100 })
      .then((result) => setParents(result.items || []))
      .catch(() => setParents([]));
  }, []);

  const fetchList = useCallback(async () => {
    const result = await adminApi.listCategories({ page_size: 100 });
    return orderCategoriesForAdmin(result.items || []);
  }, []);

  return (
    <ResourceScreen
      title="الأقسام"
      description="أقسام المتجر وترتيب ظهورها في الواجهة."
      createLabel="إضافة قسم"
      fetchList={fetchList}
      createItem={adminApi.createCategory}
      updateItem={adminApi.updateCategory}
      deleteItem={adminApi.deleteCategory}
      columns={[
        {
          key: "name",
          title: "الاسم",
          render: (row) => {
            const isChild = row.__categoryDepth > 0;
            return (
              <span style={sx`position:relative;display:inline-flex;align-items:center;gap:7px;padding-inline-start:${row.__categoryDepth * 22}px;min-height:28px;font-size:${isChild ? "12.5px" : "13.5px"};font-weight:${isChild ? 500 : 750};color:${isChild ? "#766669" : "#241F20"}`}>
                {Array.from({ length: row.__categoryDepth }, (_, depth) => <span key={depth} aria-hidden="true" style={sx`position:absolute;inset-inline-start:${depth * 22 + 8}px;inset-block:0;border-inline-start:1px solid #D8C8E8`} />)}
                {isChild && <span aria-hidden="true" style={sx`position:absolute;inset-inline-start:${(row.__categoryDepth - 1) * 22 + 8}px;width:15px;border-block-start:1px solid #D8C8E8`} />}
                <span>{row.name}</span>
              </span>
            );
          },
        },
        { key: "slug", title: "الرابط" },
        { key: "product_count", title: "عدد المنتجات" },
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
        { name: "is_featured", title: "قسم مميّز", type: "checkbox" },
        { name: "show_on_home", title: "عرض في الصفحة الرئيسية", type: "checkbox" },
        { name: "is_active", title: "فعّال", type: "checkbox", defaultValue: true },
      ]}
    />
  );
}
