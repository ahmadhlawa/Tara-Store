import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import sx from "../../sx.js";
import { adminApi } from "../../api/adminApi.js";
import {
  Badge,
  Button,
  ConfirmDialog,
  PageHeader,
  Pagination,
  Spinner,
  Table,
  card,
  input,
  useFeedback,
} from "../ui.jsx";

const TYPE_LABELS = {
  standard: "منتج عادي",
  package: "بكج",
  silicone_mold: "قالب سيليكون",
};

export default function ProductsPage() {
  const navigate = useNavigate();
  const feedback = useFeedback();
  const [rows, setRows] = useState([]);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [query, setQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [activeFilter, setActiveFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [confirming, setConfirming] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const result = await adminApi.listProducts({
        page,
        page_size: 20,
        q: query || undefined,
        product_type: typeFilter || undefined,
        is_active: activeFilter === "" ? undefined : activeFilter === "true",
      });
      setRows(result.items);
      setPages(result.pages);
    } catch (error) {
      feedback.error(error.message || "تعذّر تحميل المنتجات.");
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, query, typeFilter, activeFilter]);

  useEffect(() => {
    load();
  }, [load]);

  const remove = async () => {
    const row = confirming;
    setConfirming(null);
    try {
      await adminApi.deleteProduct(row.id);
      feedback.success("تم حذف المنتج.");
      load();
    } catch (error) {
      feedback.error(error.message || "تعذّر حذف المنتج.");
    }
  };

  return (
    <>
      <PageHeader
        title="المنتجات"
        description="أضف المنتجات والبكجات وقوالب السيليكون وعدّل أسعارها ومخزونها."
        actions={<Button onClick={() => navigate("/admin/products/new")}>منتج جديد</Button>}
      />
      {feedback.node}

      <div style={{ ...card, ...sx`display:flex;gap:10px;flex-wrap:wrap;margin-bottom:14px` }}>
        <input
          type="search"
          value={query}
          onChange={(event) => { setPage(1); setQuery(event.target.value); }}
          placeholder="ابحث بالاسم أو رقم SKU…"
          style={{ ...input, ...sx`flex:1;min-width:200px` }}
        />
        <select value={typeFilter} onChange={(event) => { setPage(1); setTypeFilter(event.target.value); }} style={{ ...input, ...sx`width:auto` }}>
          <option value="">كل الأنواع</option>
          {Object.entries(TYPE_LABELS).map(([value, label]) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </select>
        <select value={activeFilter} onChange={(event) => { setPage(1); setActiveFilter(event.target.value); }} style={{ ...input, ...sx`width:auto` }}>
          <option value="">كل الحالات</option>
          <option value="true">فعّال</option>
          <option value="false">مخفي</option>
        </select>
      </div>

      <div style={card}>
        {loading ? (
          <Spinner />
        ) : (
          <Table
            rows={rows}
            empty="لا توجد منتجات مطابقة."
            columns={[
              {
                key: "name",
                title: "المنتج",
                render: (row) => (
                  <div style={sx`display:flex;align-items:center;gap:10px`}>
                    <span style={sx`width:40px;height:40px;border-radius:8px;background:${row.primary_image_url ? `url("${row.primary_image_url}") center/cover no-repeat` : "#F2EFE9"};flex:0 0 auto`}></span>
                    <Link to={`/admin/products/${row.id}`} style={sx`font-weight:700`}>{row.name}</Link>
                  </div>
                ),
              },
              { key: "product_type", title: "النوع", render: (row) => TYPE_LABELS[row.product_type] },
              { key: "category_name", title: "القسم", render: (row) => row.category_name || "—" },
              { key: "price", title: "السعر", render: (row) => Math.round(row.price) },
              {
                key: "stock_quantity",
                title: "المخزون",
                render: (row) =>
                  !row.track_inventory ? (
                    <Badge>غير متتبّع</Badge>
                  ) : row.stock_quantity <= 0 ? (
                    <Badge tone="bad">نفد</Badge>
                  ) : row.stock_quantity <= row.low_stock_threshold ? (
                    <Badge tone="warn">{row.stock_quantity}</Badge>
                  ) : (
                    row.stock_quantity
                  ),
              },
              {
                key: "is_active",
                title: "الحالة",
                render: (row) => (
                  <Badge tone={row.is_active ? "good" : "bad"}>{row.is_active ? "فعّال" : "مخفي"}</Badge>
                ),
              },
              {
                key: "actions",
                title: "إجراءات",
                render: (row) => (
                  <div style={sx`display:flex;gap:8px`}>
                    <Button variant="ghost" onClick={() => navigate(`/admin/products/${row.id}`)} style={sx`min-height:36px;padding:0 12px;font-size:13px`}>تعديل</Button>
                    <Button variant="danger" onClick={() => setConfirming(row)} style={sx`min-height:36px;padding:0 12px;font-size:13px`}>حذف</Button>
                  </div>
                ),
              },
            ]}
          />
        )}
      </div>
      <Pagination page={page} pages={pages} onChange={setPage} />

      {confirming && (
        <ConfirmDialog
          title="تأكيد الحذف"
          message={`سيتم حذف «${confirming.name}» نهائياً مع صوره ومواصفاته وخياراته.`}
          onConfirm={remove}
          onCancel={() => setConfirming(null)}
        />
      )}
    </>
  );
}
