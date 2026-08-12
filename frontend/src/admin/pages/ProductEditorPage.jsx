import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import sx from "../../sx.js";
import { adminApi } from "../../api/adminApi.js";
import { MediaPickerDialog } from "../MediaPicker.jsx";
import ProductImageGallery from "../ProductImageGallery.jsx";
import ProductVariantsEditor, {
  buildOptionsPayload,
  variantsRemovedByOptions,
} from "../ProductVariantsEditor.jsx";
import {
  Button,
  ConfirmDialog,
  Field,
  PageHeader,
  Spinner,
  card,
  input,
  textarea,
  useFeedback,
} from "../ui.jsx";

const EMPTY = {
  name: "",
  slug: "",
  category_id: "",
  product_type: "standard",
  sku: "",
  short_description: "",
  description: "",
  price: "",
  compare_at_price: "",
  cost_price: "",
  stock_quantity: 0,
  track_inventory: true,
  low_stock_threshold: 3,
  is_active: true,
  is_featured: false,
  is_new: false,
  is_bestseller: false,
  sort_order: 0,
  seo_title: "",
  seo_description: "",
};

function Section({ title, children, actions }) {
  return (
    <div style={{ ...card, ...sx`display:flex;flex-direction:column;gap:14px;margin-bottom:16px` }}>
      <div style={sx`display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap`}>
        <h2 style={sx`margin:0;font-size:16px;font-weight:800`}>{title}</h2>
        {actions}
      </div>
      {children}
    </div>
  );
}

const num = (value) => (value === "" || value === null ? null : Number(value));

export default function ProductEditorPage() {
  const { productId } = useParams();
  const isNew = productId === "new";
  const navigate = useNavigate();
  const feedback = useFeedback();

  const [form, setForm] = useState(EMPTY);
  const [product, setProduct] = useState(null);
  const [categories, setCategories] = useState([]);
  const [allProducts, setAllProducts] = useState([]);
  const [loading, setLoading] = useState(!isNew);
  const [saving, setSaving] = useState(false);
  const [confirming, setConfirming] = useState(null);
  const [optionsConfirm, setOptionsConfirm] = useState(null);

  const [imageUrl, setImageUrl] = useState("");
  const [pickingImage, setPickingImage] = useState(false);
  const [specs, setSpecs] = useState([]);
  const [options, setOptions] = useState([]);
  const [packageChoice, setPackageChoice] = useState({ included_product_id: "", quantity: 1, display_note: "" });

  const update = (patch) => setForm((current) => ({ ...current, ...patch }));

  const loadProduct = useCallback(async () => {
    if (isNew) return;
    setLoading(true);
    try {
      const row = await adminApi.getProduct(productId);
      setProduct(row);
      setForm({
        ...EMPTY,
        ...Object.fromEntries(
          Object.keys(EMPTY).map((key) => [key, row[key] ?? EMPTY[key]]),
        ),
        category_id: row.category_id ?? "",
      });
      setSpecs(row.specifications.map((spec) => ({ name: spec.name, value: spec.value })));
      setOptions(
        row.options.map((option) => ({
          id: option.id,
          name: option.name,
          values: option.values.map((value) => value.value).join("، "),
          rows: option.values.map((value) => ({ id: value.id, value: value.value })),
        })),
      );
    } catch (error) {
      feedback.error(error.message || "تعذّر تحميل المنتج.");
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isNew, productId]);

  useEffect(() => {
    loadProduct();
  }, [loadProduct]);

  useEffect(() => {
    adminApi.listCategories({ page_size: 100 }).then((r) => setCategories(r.items || [])).catch(() => {});
    adminApi.listProducts({ page_size: 100 }).then((r) => setAllProducts(r.items || [])).catch(() => {});
  }, []);

  const save = async () => {
    setSaving(true);
    try {
      const payload = {
        name: form.name.trim(),
        category_id: form.category_id === "" ? null : Number(form.category_id),
        product_type: form.product_type,
        sku: form.sku.trim() || null,
        short_description: form.short_description,
        description: form.description,
        price: num(form.price) ?? 0,
        compare_at_price: num(form.compare_at_price),
        cost_price: num(form.cost_price),
        stock_quantity: Number(form.stock_quantity) || 0,
        track_inventory: !!form.track_inventory,
        low_stock_threshold: Number(form.low_stock_threshold) || 0,
        is_active: !!form.is_active,
        is_featured: !!form.is_featured,
        is_new: !!form.is_new,
        is_bestseller: !!form.is_bestseller,
        sort_order: Number(form.sort_order) || 0,
        seo_title: form.seo_title || null,
        seo_description: form.seo_description || null,
      };
      if (form.slug.trim()) payload.slug = form.slug.trim();

      if (isNew) {
        const created = await adminApi.createProduct(payload);
        feedback.success("تم إنشاء المنتج.");
        navigate(`/admin/products/${created.id}`, { replace: true });
      } else {
        await adminApi.updateProduct(productId, payload);
        feedback.success("تم حفظ المنتج.");
        await loadProduct();
      }
    } catch (error) {
      feedback.error(error.message || "تعذّر الحفظ.");
    } finally {
      setSaving(false);
    }
  };

  // Rethrows so a caller that owns unsaved form state can keep it on screen
  // instead of falling back to a row that was never saved.
  const runOrThrow = async (action, successMessage) => {
    try {
      await action();
      feedback.success(successMessage);
      await loadProduct();
    } catch (error) {
      feedback.error(error.message || "تعذّرت العملية.");
      throw error;
    }
  };

  const run = (action, successMessage) => runOrThrow(action, successMessage).catch(() => {});

  const commitOptions = (payload) =>
    run(() => adminApi.replaceOptions(productId, payload), "تم حفظ الخيارات.");

  // Only ask when the change actually destroys variants; a compatible edit saves
  // straight through.
  const saveOptions = () => {
    const payload = buildOptionsPayload(options);
    const removed = variantsRemovedByOptions(product?.variants || [], payload);
    if (!removed.length) return commitOptions(payload);
    return setOptionsConfirm({ payload, count: removed.length });
  };

  if (loading) return <Spinner />;

  const isPackage = form.product_type === "package";

  return (
    <>
      <PageHeader
        title={isNew ? "منتج جديد" : form.name || "تعديل المنتج"}
        description={isNew ? "أدخل البيانات الأساسية ثم احفظ لإضافة الصور والخيارات." : `المعرّف: ${productId}`}
        actions={
          <>
            <Button variant="ghost" onClick={() => navigate("/admin/products")}>رجوع</Button>
            <Button onClick={save} disabled={saving}>{saving ? "جارٍ الحفظ…" : "حفظ"}</Button>
          </>
        }
      />
      {feedback.node}

      <Section title="البيانات الأساسية">
        <div style={sx`display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px`}>
          <Field title="اسم المنتج"><input value={form.name} onChange={(e) => update({ name: e.target.value })} style={input} /></Field>
          <Field title="الرابط (اختياري)" hint="يُولَّد من الاسم إذا تُرك فارغاً"><input value={form.slug} onChange={(e) => update({ slug: e.target.value })} style={input} /></Field>
          <Field title="رقم SKU"><input value={form.sku} onChange={(e) => update({ sku: e.target.value })} style={input} /></Field>
          <Field title="القسم">
            <select value={form.category_id} onChange={(e) => update({ category_id: e.target.value })} style={input}>
              <option value="">بدون قسم</option>
              {categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}
            </select>
          </Field>
          <Field title="نوع المنتج">
            <select value={form.product_type} onChange={(e) => update({ product_type: e.target.value })} style={input}>
              <option value="standard">منتج عادي</option>
              <option value="package">بكج</option>
              <option value="silicone_mold">قالب سيليكون</option>
            </select>
          </Field>
          <Field title="ترتيب العرض"><input type="number" value={form.sort_order} onChange={(e) => update({ sort_order: e.target.value })} style={input} /></Field>
        </div>
        <Field title="وصف مختصر"><textarea rows="2" value={form.short_description} onChange={(e) => update({ short_description: e.target.value })} style={textarea} /></Field>
        <Field title="الوصف الكامل" hint="افصل الفقرات بسطر فارغ."><textarea rows="6" value={form.description} onChange={(e) => update({ description: e.target.value })} style={textarea} /></Field>
      </Section>

      <Section title="الأسعار والمخزون">
        <div style={sx`display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:14px`}>
          <Field title="سعر البيع"><input type="number" step="0.01" value={form.price} onChange={(e) => update({ price: e.target.value })} style={input} /></Field>
          <Field title="سعر قبل الخصم" hint="يجب أن يكون أعلى من سعر البيع"><input type="number" step="0.01" value={form.compare_at_price ?? ""} onChange={(e) => update({ compare_at_price: e.target.value })} style={input} /></Field>
          <Field title="سعر التكلفة" hint="داخلي — لا يظهر في المتجر"><input type="number" step="0.01" value={form.cost_price ?? ""} onChange={(e) => update({ cost_price: e.target.value })} style={input} /></Field>
          <Field title="الكمية في المخزون"><input type="number" value={form.stock_quantity} onChange={(e) => update({ stock_quantity: e.target.value })} style={input} /></Field>
          <Field title="حد التنبيه"><input type="number" value={form.low_stock_threshold} onChange={(e) => update({ low_stock_threshold: e.target.value })} style={input} /></Field>
        </div>
        <div style={sx`display:flex;gap:18px;flex-wrap:wrap`}>
          {[
            ["track_inventory", "تتبّع المخزون"],
            ["is_active", "فعّال في المتجر"],
            ["is_featured", "مميّز"],
            ["is_new", "جديد"],
            ["is_bestseller", "الأكثر مبيعاً"],
          ].map(([key, title]) => (
            <label key={key} style={sx`display:flex;align-items:center;gap:8px;font-size:14px;font-weight:600;cursor:pointer`}>
              <input type="checkbox" checked={!!form[key]} onChange={(e) => update({ [key]: e.target.checked })} style={sx`width:18px;height:18px;accent-color:#7F568F`} />
              {title}
            </label>
          ))}
        </div>
      </Section>

      <Section title="تحسين محركات البحث">
        <Field title="عنوان SEO"><input value={form.seo_title ?? ""} onChange={(e) => update({ seo_title: e.target.value })} style={input} /></Field>
        <Field title="وصف SEO"><textarea rows="2" value={form.seo_description ?? ""} onChange={(e) => update({ seo_description: e.target.value })} style={textarea} /></Field>
      </Section>

      {isNew ? (
        <div style={{ ...card, ...sx`font-size:13.5px;color:#766669` }}>
          احفظ المنتج أولاً لتتمكن من إضافة الصور والمواصفات والخيارات ومحتويات البكج.
        </div>
      ) : (
        <>
          <Section title="الصور">
            <div style={sx`display:flex;gap:10px;flex-wrap:wrap`}>
              <Button variant="secondary" onClick={() => setPickingImage(true)}>إضافة صورة من مكتبة الوسائط</Button>
              <input value={imageUrl} onChange={(e) => setImageUrl(e.target.value)} placeholder="أو الصق رابط صورة" style={{ ...input, ...sx`flex:1;min-width:220px` }} />
              <Button
                disabled={!imageUrl.trim()}
                onClick={() => run(async () => {
                  await adminApi.addProductImage(productId, { url: imageUrl.trim(), alt_text: form.name });
                  setImageUrl("");
                }, "تمت إضافة الصورة.")}
              >
                إضافة صورة
              </Button>
            </div>
            {pickingImage && (
              <MediaPickerDialog
                onClose={() => setPickingImage(false)}
                onSelect={(url) => {
                  setPickingImage(false);
                  run(() => adminApi.addProductImage(productId, { url, alt_text: form.name }), "تمت إضافة الصورة.");
                }}
              />
            )}
            <ProductImageGallery
              images={product?.images || []}
              onReorder={async (imageIds) => {
                try {
                  await adminApi.reorderProductImages(productId, imageIds);
                } catch (error) {
                  feedback.error(error.message || "تعذّر حفظ ترتيب الصور.");
                  await loadProduct();
                  throw error;
                }
                await loadProduct();
              }}
              onDelete={(imageId) => run(() => adminApi.deleteProductImage(productId, imageId), "تم حذف الصورة.")}
            />
          </Section>

          <Section
            title="المواصفات"
            actions={<Button variant="secondary" onClick={() => setSpecs((rows) => [...rows, { name: "", value: "" }])}>إضافة سطر</Button>}
          >
            {specs.map((spec, index) => (
              <div key={index} style={sx`display:flex;gap:10px;flex-wrap:wrap`}>
                <input value={spec.name} onChange={(e) => setSpecs((rows) => rows.map((row, i) => (i === index ? { ...row, name: e.target.value } : row)))} placeholder="الاسم" style={{ ...input, ...sx`flex:1;min-width:150px` }} />
                <input value={spec.value} onChange={(e) => setSpecs((rows) => rows.map((row, i) => (i === index ? { ...row, value: e.target.value } : row)))} placeholder="القيمة" style={{ ...input, ...sx`flex:1;min-width:150px` }} />
                <Button variant="danger" onClick={() => setSpecs((rows) => rows.filter((_, i) => i !== index))}>حذف</Button>
              </div>
            ))}
            <Button
              onClick={() => run(
                () => adminApi.replaceSpecifications(
                  productId,
                  specs.filter((spec) => spec.name.trim() && spec.value.trim()),
                ),
                "تم حفظ المواصفات.",
              )}
            >
              حفظ المواصفات
            </Button>
          </Section>

          <Section
            title="الخيارات"
            actions={<Button variant="secondary" onClick={() => setOptions((rows) => [...rows, { name: "", values: "" }])}>إضافة خيار</Button>}
          >
            <p style={sx`margin:0;font-size:12.5px;color:#8A7F95`}>حفظ الخيارات يبقي النسخ (variants) المتوافقة كما هي، ويحذف فقط غير المتوافقة بعد تأكيدك.</p>
            {options.map((option, index) => (
              <div key={index} style={sx`display:flex;gap:10px;flex-wrap:wrap`}>
                <input value={option.name} onChange={(e) => setOptions((rows) => rows.map((row, i) => (i === index ? { ...row, name: e.target.value } : row)))} placeholder="اسم الخيار — مثال: الحجم" style={{ ...input, ...sx`flex:1;min-width:150px` }} />
                <input value={option.values} onChange={(e) => setOptions((rows) => rows.map((row, i) => (i === index ? { ...row, values: e.target.value } : row)))} placeholder="القيم مفصولة بفاصلة" style={{ ...input, ...sx`flex:2;min-width:200px` }} />
                <Button variant="danger" onClick={() => setOptions((rows) => rows.filter((_, i) => i !== index))}>حذف</Button>
              </div>
            ))}
            <Button onClick={saveOptions}>حفظ الخيارات</Button>
          </Section>

          <Section title="النسخ (المقاسات والألوان)">
            <ProductVariantsEditor
              options={product?.options || []}
              variants={product?.variants || []}
              onCreate={(rows) => runOrThrow(async () => {
                for (const payload of rows) await adminApi.createVariant(productId, payload);
              }, rows.length === 1 ? "تمت إضافة النسخة." : `تمت إضافة ${rows.length} نسخة.`)}
              onUpdate={(variantId, payload) => runOrThrow(
                () => adminApi.updateVariant(productId, variantId, payload),
                "تم حفظ النسخة.",
              )}
              onDelete={(variantId) => runOrThrow(
                () => adminApi.deleteVariant(productId, variantId),
                "تم حذف النسخة.",
              )}
              onReport={(message) => feedback.success(message)}
            />
          </Section>

          {isPackage && (
            <Section title="محتويات البكج">
              <div style={sx`display:flex;gap:10px;flex-wrap:wrap;align-items:flex-end`}>
                <Field title="المنتج">
                  <select value={packageChoice.included_product_id} onChange={(e) => setPackageChoice({ ...packageChoice, included_product_id: e.target.value })} style={input}>
                    <option value="">اختر منتجاً…</option>
                    {allProducts
                      .filter((row) => row.product_type !== "package" && row.id !== Number(productId))
                      .map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
                  </select>
                </Field>
                <Field title="الكمية"><input type="number" min="1" value={packageChoice.quantity} onChange={(e) => setPackageChoice({ ...packageChoice, quantity: e.target.value })} style={input} /></Field>
                <Field title="ملاحظة العرض"><input value={packageChoice.display_note} onChange={(e) => setPackageChoice({ ...packageChoice, display_note: e.target.value })} style={input} /></Field>
                <Button
                  disabled={!packageChoice.included_product_id}
                  onClick={() => run(async () => {
                    await adminApi.addPackageItem(productId, {
                      included_product_id: Number(packageChoice.included_product_id),
                      quantity: Number(packageChoice.quantity) || 1,
                      display_note: packageChoice.display_note || null,
                    });
                    setPackageChoice({ included_product_id: "", quantity: 1, display_note: "" });
                  }, "تمت إضافة المنتج إلى البكج.")}
                >
                  إضافة
                </Button>
              </div>
              <div style={sx`display:flex;flex-direction:column;gap:8px`}>
                {(product?.package_items || []).map((item) => (
                  <div key={item.id} style={sx`display:flex;align-items:center;gap:12px;flex-wrap:wrap;border:1px solid #F3EBE0;border-radius:10px;padding:10px 12px`}>
                    <strong style={sx`font-size:14px`}>{item.included_product_name}</strong>
                    <span style={sx`font-size:13px;color:#766669`}>×{item.quantity}</span>
                    {item.display_note && <span style={sx`font-size:13px;color:#8A7F95`}>{item.display_note}</span>}
                    <Button variant="danger" style={sx`margin-inline-start:auto;min-height:34px;font-size:12.5px`} onClick={() => run(() => adminApi.deletePackageItem(productId, item.id), "تم الحذف.")}>حذف</Button>
                  </div>
                ))}
                {!product?.package_items?.length && <span style={sx`font-size:13px;color:#8A7F95`}>لم تُضف منتجات إلى هذا البكج بعد.</span>}
              </div>
            </Section>
          )}

          <div style={sx`display:flex;gap:10px;margin-bottom:30px`}>
            <Button onClick={save} disabled={saving}>{saving ? "جارٍ الحفظ…" : "حفظ المنتج"}</Button>
            <Button variant="danger" onClick={() => setConfirming(true)}>حذف المنتج</Button>
          </div>
        </>
      )}

      {optionsConfirm && (
        <ConfirmDialog
          title="تأكيد حفظ الخيارات"
          confirmLabel="حفظ وحذف النسخ"
          message={`سيؤدي هذا التعديل إلى حذف ${optionsConfirm.count} نسخة غير متوافقة. ستبقى بقية النسخ كما هي.`}
          onConfirm={() => {
            const { payload } = optionsConfirm;
            setOptionsConfirm(null);
            commitOptions(payload);
          }}
          onCancel={() => setOptionsConfirm(null)}
        />
      )}

      {confirming && (
        <ConfirmDialog
          title="تأكيد الحذف"
          message={`سيتم حذف «${form.name}» نهائياً.`}
          onConfirm={async () => {
            setConfirming(null);
            try {
              await adminApi.deleteProduct(productId);
              navigate("/admin/products", { replace: true });
            } catch (error) {
              feedback.error(error.message || "تعذّر الحذف.");
            }
          }}
          onCancel={() => setConfirming(null)}
        />
      )}
    </>
  );
}
