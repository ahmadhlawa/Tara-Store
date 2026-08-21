import { useCallback, useEffect, useState } from "react";
import sx from "../sx.js";
import { MediaField } from "./MediaPicker.jsx";
import {
  Button,
  ConfirmDialog,
  Field,
  Modal,
  PageHeader,
  Pagination,
  Spinner,
  Table,
  card,
  input,
  textarea,
  useFeedback,
} from "./ui.jsx";

function initialValues(fields, row) {
  const values = {};
  fields.forEach((field) => {
    const current = row ? row[field.name] : undefined;
    if (current !== undefined && current !== null) {
      values[field.name] = field.type === "date" ? String(current).slice(0, 16) : current;
    } else {
      values[field.name] = field.defaultValue ?? (field.type === "checkbox" ? false : "");
    }
  });
  return values;
}

function serialize(fields, values) {
  const payload = {};
  fields.forEach((field) => {
    const value = values[field.name];
    if (field.type === "number") {
      payload[field.name] = value === "" || value === null ? null : Number(value);
    } else if (field.type === "checkbox") {
      payload[field.name] = !!value;
    } else if (field.type === "date") {
      payload[field.name] = value ? new Date(value).toISOString().slice(0, 19) : null;
    } else if (typeof value === "string") {
      payload[field.name] = value.trim() === "" ? (field.emptyAsNull ? null : "") : value.trim();
    } else {
      payload[field.name] = value;
    }
    if (field.omitWhenEmpty && (payload[field.name] === "" || payload[field.name] === null)) {
      delete payload[field.name];
    }
  });
  return payload;
}

function FieldControl({ field, value, onChange }) {
  if (field.type === "checkbox") {
    return (
      <label style={sx`display:flex;align-items:center;gap:10px;font-size:14px;font-weight:600;color:#3B3243;cursor:pointer`}>
        <input
          type="checkbox"
          checked={!!value}
          onChange={(event) => onChange(event.target.checked)}
          style={sx`width:18px;height:18px;accent-color:var(--admin-primary);cursor:pointer`}
        />
        {field.title}
      </label>
    );
  }
  if (field.type === "media") {
    return <MediaField title={field.title} hint={field.hint} value={value} onChange={onChange} />;
  }
  if (field.type === "textarea") {
    return (
      <Field title={field.title} hint={field.hint}>
        <textarea
          rows={field.rows || 4}
          value={value ?? ""}
          onChange={(event) => onChange(event.target.value)}
          style={textarea}
        />
      </Field>
    );
  }
  if (field.type === "select") {
    return (
      <Field title={field.title} hint={field.hint}>
        <select value={value ?? ""} onChange={(event) => onChange(event.target.value)} style={input}>
          {!field.required && <option value="">—</option>}
          {field.options.map((option) => (
            <option key={option.value} value={option.value}>{option.label}</option>
          ))}
        </select>
      </Field>
    );
  }
  const type = { number: "number", date: "datetime-local", color: "color" }[field.type] || "text";
  return (
    <Field title={field.title} hint={field.hint}>
      <input
        type={type}
        step={field.step}
        min={field.min}
        value={value ?? ""}
        onChange={(event) => onChange(event.target.value)}
        placeholder={field.placeholder}
        style={input}
      />
    </Field>
  );
}

/**
 * A CRUD screen for one resource. Every screen still declares its own columns,
 * form fields and API calls — this only removes the repeated wiring.
 */
export default function ResourceScreen({
  title,
  description,
  columns,
  fields,
  fetchList,
  createItem,
  updateItem,
  preparePayload,
  deleteItem,
  paginated = false,
  createLabel = "إضافة",
  describeRow = (row) => row.name || row.title || row.code || `#${row.id}`,
  extraActions,
}) {
  const [rows, setRows] = useState([]);
  const [pages, setPages] = useState(1);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(null);
  const [values, setValues] = useState({});
  const [saving, setSaving] = useState(false);
  const [confirming, setConfirming] = useState(null);
  const feedback = useFeedback();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const result = await fetchList(paginated ? { page, page_size: 20 } : undefined);
      if (Array.isArray(result)) {
        setRows(result);
        setPages(1);
      } else {
        setRows(result.items || []);
        setPages(result.pages || 1);
      }
    } catch (error) {
      feedback.error(error.message || "تعذّر تحميل البيانات.");
      setRows([]);
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fetchList, page, paginated]);

  useEffect(() => {
    load();
  }, [load]);

  const openCreate = () => {
    setEditing({ mode: "create" });
    setValues(initialValues(fields, null));
  };
  const openEdit = (row) => {
    setEditing({ mode: "edit", row });
    setValues(initialValues(fields, row));
  };

  const save = async () => {
    setSaving(true);
    try {
      const payload = preparePayload
        ? preparePayload(serialize(fields, values), editing.mode === "edit" ? editing.row : undefined)
        : serialize(fields, values);
      if (editing.mode === "create") {
        await createItem(payload);
        feedback.success("تمت الإضافة بنجاح.");
      } else {
        await updateItem(editing.row.id, payload);
        feedback.success("تم حفظ التعديلات.");
      }
      setEditing(null);
      await load();
    } catch (error) {
      feedback.error(error.message || "تعذّر الحفظ.");
    } finally {
      setSaving(false);
    }
  };

  const remove = async () => {
    const row = confirming;
    setConfirming(null);
    try {
      await deleteItem(row.id);
      feedback.success("تم الحذف.");
      await load();
    } catch (error) {
      feedback.error(error.message || "تعذّر الحذف.");
    }
  };

  const allColumns = [
    ...columns,
    {
      key: "__actions",
      title: "إجراءات",
      render: (row) => (
        <div style={sx`display:flex;gap:8px;flex-wrap:wrap`}>
          {extraActions?.(row)}
          <Button variant="ghost" onClick={() => openEdit(row)} style={sx`min-height:36px;padding:0 12px;font-size:13px`}>تعديل</Button>
          {deleteItem && (
            <Button variant="danger" onClick={() => setConfirming(row)} style={sx`min-height:36px;padding:0 12px;font-size:13px`}>حذف</Button>
          )}
        </div>
      ),
    },
  ];

  return (
    <>
      <PageHeader
        title={title}
        description={description}
        actions={createItem && <Button onClick={openCreate}>{createLabel}</Button>}
      />
      {feedback.node}
      <div style={card}>
        {loading ? <Spinner /> : <Table columns={allColumns} rows={rows} />}
      </div>
      {paginated && <Pagination page={page} pages={pages} onChange={setPage} />}

      {editing && (
        <Modal
          title={editing.mode === "create" ? `${createLabel}` : `تعديل: ${describeRow(editing.row)}`}
          onClose={() => setEditing(null)}
          footer={
            <>
              <Button variant="ghost" onClick={() => setEditing(null)}>إلغاء</Button>
              <Button onClick={save} disabled={saving}>{saving ? "جارٍ الحفظ…" : "حفظ"}</Button>
            </>
          }
        >
          {fields.map((field) => (
            <FieldControl
              key={field.name}
              field={field}
              value={values[field.name]}
              onChange={(value) => setValues((current) => ({ ...current, [field.name]: value }))}
            />
          ))}
        </Modal>
      )}

      {confirming && (
        <ConfirmDialog
          title="تأكيد الحذف"
          message={`سيتم حذف «${describeRow(confirming)}» نهائياً. لا يمكن التراجع عن هذه العملية.`}
          onConfirm={remove}
          onCancel={() => setConfirming(null)}
        />
      )}
    </>
  );
}
