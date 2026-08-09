import { useCallback, useEffect, useState } from "react";
import sx from "../../sx.js";
import { adminApi } from "../../api/adminApi.js";
import { formatDateTime } from "../../utils/format.js";
import ResourceScreen from "../ResourceScreen.jsx";
import { Badge, Notice, PageHeader, Pagination, Spinner, Table, card, input, useFeedback } from "../ui.jsx";

export function AdminsPage() {
  const fetchList = useCallback((params) => adminApi.listAdmins(params), []);
  return (
    <>
      <Notice>حسابات الإدارة متاحة لمدير النظام الأعلى فقط. كلمة المرور لا تُعرض أبداً بعد الحفظ.</Notice>
      <ResourceScreen
        title="حسابات الإدارة"
        description="أنشئ حسابات للفريق وحدّد صلاحياتها."
        paginated
        createLabel="حساب جديد"
        fetchList={fetchList}
        createItem={adminApi.createAdmin}
        updateItem={adminApi.updateAdmin}
        deleteItem={adminApi.deleteAdmin}
        describeRow={(row) => row.email}
        columns={[
          { key: "full_name", title: "الاسم" },
          { key: "email", title: "البريد" },
          {
            key: "role",
            title: "الصلاحية",
            render: (row) => (
              <Badge tone={row.role === "super_admin" ? "good" : "neutral"}>
                {row.role === "super_admin" ? "مدير أعلى" : "مدير"}
              </Badge>
            ),
          },
          {
            key: "is_active",
            title: "الحالة",
            render: (row) => <Badge tone={row.is_active ? "good" : "bad"}>{row.is_active ? "مفعّل" : "موقوف"}</Badge>,
          },
          { key: "last_login_at", title: "آخر دخول", render: (row) => formatDateTime(row.last_login_at) || "—" },
        ]}
        fields={[
          { name: "email", title: "البريد الإلكتروني", required: true },
          { name: "full_name", title: "الاسم الكامل", required: true },
          {
            name: "password",
            title: "كلمة المرور",
            hint: "١٠ أحرف على الأقل. اتركها فارغة عند التعديل للإبقاء على الحالية.",
            omitWhenEmpty: true,
          },
          {
            name: "role",
            title: "الصلاحية",
            type: "select",
            required: true,
            defaultValue: "admin",
            options: [
              { value: "admin", label: "مدير" },
              { value: "super_admin", label: "مدير أعلى" },
            ],
          },
          { name: "is_active", title: "مفعّل", type: "checkbox", defaultValue: true },
        ]}
      />
    </>
  );
}

export function AuditLogPage() {
  const feedback = useFeedback();
  const [rows, setRows] = useState([]);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [entityType, setEntityType] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    adminApi
      .listAuditLogs({ page, page_size: 30, entity_type: entityType || undefined })
      .then((result) => {
        setRows(result.items);
        setPages(result.pages);
      })
      .catch((error) => feedback.error(error.message || "تعذّر تحميل السجل."))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, entityType]);

  return (
    <>
      <PageHeader title="سجل التغييرات" description="من غيّر ماذا ومتى. لا يحتوي السجل على كلمات مرور أو بيانات حساسة." />
      {feedback.node}
      <div style={{ ...card, ...sx`margin-bottom:14px` }}>
        <select value={entityType} onChange={(event) => { setPage(1); setEntityType(event.target.value); }} style={{ ...input, ...sx`width:auto` }}>
          <option value="">كل العناصر</option>
          {["product", "category", "order", "coupon", "delivery_area", "store_settings", "article", "static_page", "media_asset", "admin_user", "hero_slide", "banner", "home_section"].map((value) => (
            <option key={value} value={value}>{value}</option>
          ))}
        </select>
      </div>
      <div style={card}>
        {loading ? (
          <Spinner />
        ) : (
          <Table
            rows={rows}
            empty="لا توجد سجلات."
            columns={[
              { key: "created_at", title: "التاريخ", render: (row) => formatDateTime(row.created_at) },
              { key: "admin_email", title: "المستخدم", render: (row) => row.admin_email || "—" },
              { key: "action", title: "الإجراء" },
              { key: "entity_type", title: "العنصر" },
              { key: "entity_id", title: "المعرّف", render: (row) => row.entity_id ?? "—" },
              {
                key: "meta",
                title: "تفاصيل",
                render: (row) => (
                  <span style={sx`font-size:12px;color:#766669`}>
                    {Object.entries(row.meta || {})
                      .map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join(", ") : value}`)
                      .join(" · ") || "—"}
                  </span>
                ),
              },
            ]}
          />
        )}
      </div>
      <Pagination page={page} pages={pages} onChange={setPage} />
    </>
  );
}
