import { useCallback, useState } from "react";
import { adminApi } from "../../api/adminApi.js";
import sx from "../../sx.js";
import { CategoryPicker } from "../CategoryPicker.jsx";
import ResourceScreen from "../ResourceScreen.jsx";
import { Badge } from "../ui.jsx";

export function orderCategoriesForAdmin(categories) {
  const siblingOrder = (a, b) => {
    const order = Number(a.sort_order ?? 0) - Number(b.sort_order ?? 0);
    if (order) return order;
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
    children.sort(siblingOrder);
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
    .sort(siblingOrder)
    .forEach((category) => append(category));
  categories.forEach((category) => append(category));

  return ordered;
}

export function reorderedSiblingIds(categories, sourceId, targetId) {
  const source = categories.find((category) => category.id === sourceId);
  const target = categories.find((category) => category.id === targetId);
  if (!source || !target || source.parent_id !== target.parent_id) return null;
  const siblings = orderCategoriesForAdmin(
    categories.filter((category) => category.parent_id === source.parent_id),
  ).map((category) => category.id);
  const from = siblings.indexOf(sourceId);
  const to = siblings.indexOf(targetId);
  siblings.splice(to, 0, siblings.splice(from, 1)[0]);
  return { parentId: source.parent_id ?? null, categoryIds: siblings };
}

export function CategoriesPage() {
  const [parents, setParents] = useState([]);
  const [reloadKey, setReloadKey] = useState(0);
  const [reorderError, setReorderError] = useState("");
  const [draggedId, setDraggedId] = useState(null);

  const fetchList = useCallback(async () => {
    const result = await adminApi.listCategories({ page_size: 100 });
    const categories = result.items || [];
    setParents(categories);
    return orderCategoriesForAdmin(categories);
  }, [reloadKey]);

  const saveCategoryOrder = async (sourceId, targetId) => {
    const reordered = reorderedSiblingIds(parents, sourceId, targetId);
    if (!reordered) {
      setReorderError("يمكن ترتيب الأقسام التابعة للأب نفسه فقط.");
      return;
    }
    setReorderError("");
    try {
      await adminApi.reorderCategories(reordered.parentId, reordered.categoryIds);
      setReloadKey((value) => value + 1);
    } catch (error) {
      setReorderError(error.message || "تعذّر حفظ ترتيب الأقسام.");
    }
  };

  const dropCategory = (event, targetId) => {
    event.preventDefault();
    const transferredId = Number(event.dataTransfer.getData("text/category-id"));
    saveCategoryOrder(transferredId || draggedId, targetId);
    setDraggedId(null);
  };

  const moveCategory = (row, offset) => {
    const siblings = orderCategoriesForAdmin(
      parents.filter((category) => category.parent_id === row.parent_id),
    );
    const index = siblings.findIndex((category) => category.id === row.id);
    const target = siblings[index + offset];
    if (target) saveCategoryOrder(row.id, target.id);
  };

  return (
    <>
      {reorderError && <p role="alert" style={sx`color:#A13E3E;font-size:13px`}>{reorderError}</p>}
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
          key: "__order",
          title: "ترتيب",
          render: (row) => (
            <button
              type="button"
              draggable
              aria-label={`اسحب لترتيب ${row.name}`}
              title="اسحب، أو استخدم سهمي أعلى وأسفل، ضمن المستوى نفسه"
              onDragStart={(event) => {
                setDraggedId(row.id);
                event.dataTransfer.effectAllowed = "move";
                event.dataTransfer.setData("text/category-id", String(row.id));
              }}
              onDragEnd={() => setDraggedId(null)}
              onDragOver={(event) => {
                const source = parents.find((category) => category.id === draggedId);
                if (source?.parent_id === row.parent_id) event.preventDefault();
              }}
              onDrop={(event) => dropCategory(event, row.id)}
              onKeyDown={(event) => {
                if (event.key === "ArrowUp" || event.key === "ArrowDown") {
                  event.preventDefault();
                  moveCategory(row, event.key === "ArrowUp" ? -1 : 1);
                }
              }}
              style={sx`display:inline-grid;place-items:center;width:34px;height:34px;padding:0;background:#fff;border:1px solid #D8C8E8;border-radius:8px;color:#735277;cursor:grab;user-select:none`}
            >
              ↕
            </button>
          ),
        },
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
        { name: "image_url", title: "صورة القسم", type: "media", emptyAsNull: true, hint: "الأبعاد الموصى بها: 1200 × 1500 بكسل — تستخدم لبطاقات الأقسام. حافظ على العناصر المهمة قرب منتصف الصورة." },
        {
          name: "parent_id",
          title: "القسم الأب",
          type: "select",
          emptyAsNull: true,
          renderControl: ({ value, onChange, row }) => <CategoryPicker categories={parents} value={value} onChange={onChange} excludedId={row?.id} emptyLabel="بدون قسم أب" />,
          options: [],
        },
        { name: "is_featured", title: "قسم مميّز", type: "checkbox" },
        { name: "show_on_home", title: "عرض في الصفحة الرئيسية", type: "checkbox" },
        { name: "is_active", title: "فعّال", type: "checkbox", defaultValue: true },
      ]}
      />
    </>
  );
}
