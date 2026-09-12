import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useStore } from "../app/StoreProvider.jsx";
import { useCartLines } from "../components/public/cart/useCartLines.js";
import FreeDeliveryNotice from "../components/public/cart/FreeDeliveryNotice.jsx";
import Media from "../components/public/shell/Media.jsx";
import { buildOrderWhatsAppMessage, checkoutService } from "../services/checkout.js";
import { orderTokenStorage } from "../storage/authStorage.js";
import { paymentMethods } from "../store.js";
import { useMoney } from "../hooks/useStorefront.js";
import { whatsappHref } from "../utils/format.js";

const RETURN_POLICY_NOTICE = [
  "نظراً لطبيعة منتجات تارا وحساسية القطع، وكونها مصنوعة ومجهزة يدوياً بعناية، لا يمكن استبدال أو إرجاع المنتجات بعد تأكيد الطلب أو استلامه.",
  "ولا تعد الاختلافات البسيطة والطبيعية في اللون أو الشكل أو القياس أو التفاصيل الناتجة عن طبيعة التصنيع اليدوي عيباً أو تلفاً في المنتج.",
  "نرجو التأكد من تفاصيل المنتج والمواصفات المطلوبة قبل تأكيد الطلب.",
];

function newClientReference() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  return `checkout-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function validate(form) {
  const errors = {};
  if (!form.name || form.name.trim().length < 3) errors.name = "الرجاء إدخال الاسم الكامل";
  if (!/^\+?\d{7,15}$/.test(String(form.phone).replace(/[\s-()]/g, ""))) {
    errors.phone = "رقم هاتف غير صالح — مثال 0591234567";
  }
  if (!form.areaId) errors.area = "اختر منطقة التوصيل";
  if (!form.address || form.address.trim().length < 6) errors.address = "الرجاء إدخال عنوان واضح";
  if (!form.terms) errors.terms = "يجب الموافقة على الشروط قبل إتمام الطلب";
  return errors;
}

/** Cash on delivery only — the form never asks for card or transfer details. */
export default function CheckoutRoutePage() {
  const store = useStore();
  const money = useMoney();
  const navigate = useNavigate();
  const { lines } = useCartLines();
  const { checkoutForm: form, setCheckoutForm, cart, coupon, deliveryAreas } = store;

  const [errors, setErrors] = useState({});
  const [placing, setPlacing] = useState(false);
  const [submitError, setSubmitError] = useState(null);
  const [priced, setPriced] = useState(null);
  const clientReference = useRef(null);
  const submitting = useRef(false);
  const formRef = useRef(null);
  const focusValidationError = useRef(false);

  useEffect(() => {
    if (!focusValidationError.current || !Object.keys(errors).length) return;
    focusValidationError.current = false;
    formRef.current?.querySelector("[aria-invalid='true']")?.focus();
  }, [errors]);

  // Every displayed number is recomputed by the server, so a stale cart or a
  // tampered price can never become an order total.
  useEffect(() => {
    let cancelled = false;
    if (!cart.length) {
      setPriced(null);
      return undefined;
    }
    checkoutService
      .price(cart, { couponCode: coupon.applied || null, deliveryAreaId: form.areaId })
      .then((result) => {
        if (cancelled) return;
        setPriced(result);
        setSubmitError(null);
      })
      .catch((error) => {
        if (cancelled) return;
        setPriced(null);
        setSubmitError(error.message);
      });
    return () => {
      cancelled = true;
    };
  }, [cart, coupon.applied, form.areaId]);

  const update = (patch) => {
    const next = { ...form, ...patch };
    setCheckoutForm(next);
    // Once the form has been submitted and errors are showing, fixing a field
    // clears its message straight away rather than at the next submit.
    setErrors((current) => (Object.keys(current).length ? validate(next) : current));
  };

  const placeOrder = async (event) => {
    event.preventDefault();
    if (placing || submitting.current) return;
    const found = validate(form);
    setErrors(found);
    if (Object.keys(found).length) {
      focusValidationError.current = true;
      return;
    }

    submitting.current = true;
    setPlacing(true);
    setSubmitError(null);
    try {
      clientReference.current ||= newClientReference();
      const order = await checkoutService.placeOrder(cart, {
        name: form.name.trim(),
        phone: form.phone.trim(),
        address: form.address.trim(),
        deliveryAreaId: form.areaId,
        couponCode: coupon.applied || null,
        paymentMethod: "cash_on_delivery",
        notes: form.notes.trim() || null,
      }, clientReference.current);
      orderTokenStorage.save(order.order_number, order.public_token);
      if (store.settings.whatsapp) {
        window.open(
          whatsappHref(store.settings.whatsapp, buildOrderWhatsAppMessage(order)),
          "_blank",
          "noopener",
        );
      }
      store.clearCart();
      store.setCoupon({ input: "", applied: "", label: "", message: "", ok: false, discount: 0 });
      navigate(`/order-success/${order.order_number}`, { replace: true });
    } catch (error) {
      setSubmitError(error.message || "تعذّر إتمام الطلب. حاول مرة أخرى.");
    } finally {
      submitting.current = false;
      setPlacing(false);
    }
  };

  const totals = priced || { subtotal: 0, discount: 0, shipping: 0, total: 0, areaName: "" };

  if (!cart.length) {
    return (
      <section className="vs-container vs-container--narrow vs-section">
        <h1 className="vs-page__title">إتمام الطلب</h1>
        <div className="vs-state">
          <h2 className="vs-state__title">لا توجد منتجات لإتمام الطلب</h2>
          <p className="vs-state__body">أضف منتجات إلى العربة ثم عد إلى هنا.</p>
          <Link to="/shop" className="vs-btn vs-btn--primary vs-btn--lg">
            تصفّح المتجر
          </Link>
        </div>
      </section>
    );
  }

  const field = (key) => (errors[key] ? { "aria-invalid": true, "aria-describedby": `vs-err-${key}` } : {});

  return (
    <section className="vs-container vs-section">
      <h1 className="vs-page__title">إتمام الطلب</h1>

      <div className="vs-checkout">
        <form className="vs-form vs-checkout__form" onSubmit={placeOrder} noValidate ref={formRef}>
          <fieldset className="vs-panel vs-checkout__customer">
            <legend className="vs-panel__title">بيانات العميل</legend>

            <div className="vs-checkout__fields">
              <label className="vs-field">
                الاسم الكامل
                <input
                  className="vs-input"
                  type="text"
                  value={form.name}
                  onChange={(event) => update({ name: event.target.value })}
                  placeholder="مثال: محمد أحمد"
                  {...field("name")}
                />
                {errors.name && (
                  <span className="vs-field__error" id="vs-err-name">
                    {errors.name}
                  </span>
                )}
              </label>

              <label className="vs-field">
                رقم الهاتف
                <input
                  className="vs-input"
                  type="tel"
                  dir="ltr"
                  value={form.phone}
                  onChange={(event) => update({ phone: event.target.value })}
                  placeholder="05XXXXXXXX"
                  {...field("phone")}
                />
                {errors.phone && (
                  <span className="vs-field__error" id="vs-err-phone">
                    {errors.phone}
                  </span>
                )}
              </label>

              <label className="vs-field">
                منطقة التوصيل
                <select
                  className="vs-input"
                  value={form.areaId ?? ""}
                  onChange={(event) =>
                    update({ areaId: event.target.value ? Number(event.target.value) : null })
                  }
                  {...field("area")}
                >
                  <option value="">اختر المنطقة…</option>
                  {deliveryAreas.map((area) => (
                    <option key={area.id} value={area.id}>
                      {area.name} — {money(area.price)}
                      {area.eta ? ` · ${area.eta}` : ""}
                    </option>
                  ))}
                </select>
                {errors.area && (
                  <span className="vs-field__error" id="vs-err-area">
                    {errors.area}
                  </span>
                )}
              </label>

              <label className="vs-field">
                العنوان بالتفصيل
                <textarea
                  className="vs-input vs-textarea"
                  rows="2"
                  value={form.address}
                  onChange={(event) => update({ address: event.target.value })}
                  placeholder="الشارع، رقم البناية، أقرب معلم"
                  {...field("address")}
                />
                {errors.address && (
                  <span className="vs-field__error" id="vs-err-address">
                    {errors.address}
                  </span>
                )}
              </label>

              <label className="vs-field vs-checkout__notes">
                ملاحظات على الطلب (اختياري)
                <textarea
                  className="vs-input vs-textarea"
                  rows="1"
                  value={form.notes}
                  onChange={(event) => update({ notes: event.target.value })}
                  placeholder="أي تفاصيل تساعدنا في التوصيل"
                />
              </label>
            </div>
          </fieldset>

          <fieldset className="vs-panel vs-checkout__payment">
            <legend className="vs-panel__title">طريقة الدفع</legend>
            {paymentMethods.map((method) => (
              <label
                key={method.key}
                className="vs-payopt"
                data-selected={form.payment === method.key}
              >
                <input
                  type="radio"
                  name="pay"
                  checked={form.payment === method.key}
                  onChange={() => update({ payment: method.key })}
                />
                <span>
                  <strong>{method.label}</strong>
                  <span className="vs-payopt__desc">{method.desc}</span>
                </span>
              </label>
            ))}

            <p className="vs-form__note">
              لا يتم تحصيل أي مبلغ الآن؛ يُدفع نقداً للمندوب عند التسليم.
            </p>

            <div className="vs-return-policy" aria-labelledby="vs-return-policy-title">
              <h2 id="vs-return-policy-title">سياسة الإرجاع والاستبدال</h2>
              {RETURN_POLICY_NOTICE.map((paragraph) => <p key={paragraph}>{paragraph}</p>)}
            </div>

            <label className="vs-check vs-check--terms">
              <input
                type="checkbox"
                checked={form.terms}
                onChange={() => update({ terms: !form.terms })}
                {...field("terms")}
              />
              <span>
                قرأت <Link to="/page/return-policy">سياسة الإرجاع والاستبدال</Link> وأوافق عليها
              </span>
            </label>
            {errors.terms && (
              <span className="vs-field__error" id="vs-err-terms">
                {errors.terms}
              </span>
            )}
          </fieldset>

          {(submitError || Object.keys(errors).length > 0) && (
            <div className="vs-state vs-state--error vs-checkout__error" role="alert">
              {submitError || Object.values(errors)[0]}
            </div>
          )}

          <button
            type="submit"
            className="vs-btn vs-btn--primary vs-btn--lg vs-btn--block"
            disabled={placing || !form.terms}
          >
            {placing && <span className="vs-spinner" aria-hidden="true" />}
            {placing ? "جارٍ إرسال الطلب…" : `تأكيد وإرسال الطلب — ${money(totals.total)}`}
          </button>
        </form>

        <aside className="vs-summary" aria-label="ملخّص الطلب">
          <h2 className="vs-summary__title">ملخّص الطلب</h2>
          {lines.map((line) => (
            <div className="vs-summary__line" key={line.key}>
              <span className="vs-summary__thumb">
                <Media src={line.imageUrl} fallback={line.bg} alt="" ratio="1 / 1" />
              </span>
              <span className="vs-summary__linetext">
                <span className="vs-clamp-2">{line.name}</span>
                <span className="vs-summary__muted">×{line.qty}</span>
              </span>
              <strong>{line.lineText}</strong>
            </div>
          ))}

          <div className="vs-summary__row">
            <span>المجموع الفرعي</span>
            <strong>{money(totals.subtotal)}</strong>
          </div>
          {totals.discount > 0 && (
            <div className="vs-summary__row vs-summary__row--good">
              <span>الخصم</span>
              <strong>−{money(totals.discount)}</strong>
            </div>
          )}
          <div className="vs-summary__row">
            <span>التوصيل {totals.areaName ? `(${totals.areaName})` : ""}</span>
            <strong>{totals.shipping ? money(totals.shipping) : "—"}</strong>
          </div>

          {/* Priced by the server above; this only explains the rule behind that
              number, and narrows to the chosen area once there is one. */}
          <FreeDeliveryNotice subtotal={totals.subtotal} areaId={form.areaId} />
          <div className="vs-summary__total">
            <span>الإجمالي</span>
            <strong>{money(totals.total)}</strong>
          </div>
          <p className="vs-summary__note">جميع المبالغ محسوبة من الخادم عند إتمام الطلب.</p>
        </aside>
      </div>
    </section>
  );
}
