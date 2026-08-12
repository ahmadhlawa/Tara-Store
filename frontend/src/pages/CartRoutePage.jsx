import { Link } from "react-router-dom";
import { useStore } from "../app/StoreProvider.jsx";
import { checkoutService } from "../services/checkout.js";
import { useCartLines } from "../components/public/cart/useCartLines.js";
import FreeDeliveryNotice from "../components/public/cart/FreeDeliveryNotice.jsx";
import QuantityStepper from "../components/public/cart/QuantityStepper.jsx";
import Media from "../components/public/shell/Media.jsx";
import { CartIcon, TrashIcon } from "../components/public/shell/icons.jsx";

export default function CartRoutePage() {
  const store = useStore();
  const { lines, count, subtotalText, subtotal, empty, money } = useCartLines();
  const { coupon, setCoupon } = store;

  const applyCoupon = async () => {
    const code = coupon.input.trim();
    if (!code) return;
    try {
      const result = await checkoutService.validateCoupon(code, subtotal);
      setCoupon((current) => ({
        ...current,
        applied: result.code,
        label: result.label,
        discount: result.discount,
        message: `تم تطبيق ${result.label}`,
        ok: true,
      }));
    } catch (error) {
      setCoupon((current) => ({
        ...current,
        applied: "",
        label: "",
        discount: 0,
        message: error.message || "الكود غير صالح أو منتهي الصلاحية",
        ok: false,
      }));
    }
  };

  const discount = coupon.applied ? coupon.discount : 0;
  const total = Math.max(0, subtotal - discount);

  return (
    <section className="vs-container vs-section">
      <h1 className="vs-page__title">عربة التسوّق</h1>
      <p className="vs-page__lead">
        {count === 0 ? "لا توجد منتجات في العربة" : `${count} منتجاً في عربتك`}
      </p>

      {empty ? (
        <div className="vs-state">
          <span className="vs-state__icon">
            <CartIcon size={26} />
          </span>
          <h2 className="vs-state__title">عربتك فارغة</h2>
          <p className="vs-state__body">ابدأ بتصفّح الأقسام واختر ما يناسب مناسبتك.</p>
          <Link to="/shop" className="vs-btn vs-btn--primary vs-btn--lg">
            تصفّح المتجر
          </Link>
        </div>
      ) : (
        <div className="vs-cartpage">
          <div className="vs-cartpage__lines">
            {lines.map((line) => (
              <article key={line.key} className="vs-cartrow" data-leaving={line.leaving}>
                <Link to={line.href} className="vs-cartrow__thumb" tabIndex={-1} aria-hidden="true">
                  <Media src={line.imageUrl} fallback={line.bg} alt="" ratio="1 / 1" />
                </Link>
                <div className="vs-cartrow__body">
                  <Link to={line.href} className="vs-cartrow__name">
                    {line.name}
                  </Link>
                  {line.variationText && (
                    <span className="vs-cartrow__variant">الخيار: {line.variationText}</span>
                  )}
                  <span className="vs-cartrow__unit">سعر القطعة: {line.unitText}</span>
                </div>
                <QuantityStepper
                  value={line.qty}
                  onDecrease={line.decrease}
                  onIncrease={line.increase}
                  label={`الكمية من ${line.name}`}
                />
                <strong className="vs-cartrow__total">{line.lineText}</strong>
                <button
                  type="button"
                  className="vs-iconbtn vs-cartrow__remove"
                  onClick={line.remove}
                  aria-label="إزالة المنتج"
                >
                  <TrashIcon size={17} />
                </button>
              </article>
            ))}
            <Link to="/shop" className="vs-cartpage__back">
              → متابعة التسوّق
            </Link>
          </div>

          <aside className="vs-summary" aria-label="ملخّص الطلب">
            <h2 className="vs-summary__title">ملخّص الطلب</h2>
            <div className="vs-summary__row">
              <span>المجموع الفرعي</span>
              <strong>{subtotalText}</strong>
            </div>
            {discount > 0 && (
              <div className="vs-summary__row vs-summary__row--good">
                <span>الخصم ({coupon.label})</span>
                <strong>−{money(discount)}</strong>
              </div>
            )}
            <div className="vs-summary__row">
              <span>التوصيل</span>
              <span className="vs-summary__muted">يُحتسب عند إتمام الطلب</span>
            </div>

            <FreeDeliveryNotice subtotal={subtotal} />

            <div className="vs-coupon">
              <input
                className="vs-input"
                type="text"
                value={coupon.input}
                onChange={(event) =>
                  setCoupon((current) => ({ ...current, input: event.target.value }))
                }
                placeholder="كود الخصم"
                aria-label="كود الخصم"
              />
              <button type="button" className="vs-btn vs-btn--outline" onClick={applyCoupon}>
                تطبيق
              </button>
            </div>
            {coupon.message && (
              <span
                role="status"
                className={`vs-coupon__msg${coupon.ok ? " is-ok" : " is-bad"}`}
              >
                {coupon.message}
              </span>
            )}

            <div className="vs-summary__total">
              <span>الإجمالي</span>
              <strong>{money(total)}</strong>
            </div>
            <Link to="/checkout" className="vs-btn vs-btn--primary vs-btn--lg vs-btn--block">
              إتمام الطلب
            </Link>
            <p className="vs-summary__note">
              تُحتسب رسوم التوصيل حسب المنطقة في صفحة إتمام الطلب.
            </p>
          </aside>
        </div>
      )}
    </section>
  );
}
