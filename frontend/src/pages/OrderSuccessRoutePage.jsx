import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMoney } from "../hooks/useStorefront.js";
import { checkoutService } from "../services/checkout.js";
import { orderTokenStorage } from "../storage/authStorage.js";
import { orderStatusLabels, paymentMethodLabels } from "../store.js";
import { CheckIcon } from "../components/public/shell/icons.jsx";

export default function OrderSuccessRoutePage() {
  const { orderNumber } = useParams();
  const money = useMoney();
  const [order, setOrder] = useState(null);
  const [status, setStatus] = useState("loading");

  useEffect(() => {
    let cancelled = false;
    const token = orderTokenStorage.load(orderNumber);
    if (!token) {
      setStatus("missing");
      return undefined;
    }
    checkoutService
      .order(orderNumber, token)
      .then((value) => {
        if (cancelled) return;
        setOrder(value);
        setStatus("ready");
      })
      .catch(() => !cancelled && setStatus("missing"));
    return () => {
      cancelled = true;
    };
  }, [orderNumber]);

  if (status === "loading") {
    return (
      <div className="vs-container vs-container--narrow vs-section">
        <div className="vs-skel" style={{ height: 220, borderRadius: 16 }} />
      </div>
    );
  }

  if (status === "missing" || !order) {
    return (
      <section className="vs-container vs-container--narrow vs-section">
        <div className="vs-state">
          <h1 className="vs-state__title">تعذّر عرض تفاصيل هذا الطلب</h1>
          <p className="vs-state__body">
            رابط تأكيد الطلب صالح على المتصفح الذي أُنشئ منه الطلب فقط. تواصل معنا وسنساعدك.
          </p>
          <Link to="/contact" className="vs-btn vs-btn--primary vs-btn--lg">
            تواصل معنا
          </Link>
        </div>
      </section>
    );
  }

  return (
    <section className="vs-container vs-container--narrow vs-section">
      <div className="vs-done">
        <span className="vs-done__mark">
          <CheckIcon size={30} />
        </span>
        <h1 className="vs-done__title">تم استلام طلبك بنجاح</h1>
        <p className="vs-done__sub">
          رقم الطلب <strong>{order.order_number}</strong> — الحالة:{" "}
          {orderStatusLabels[order.status] || order.status}
        </p>

        <div className="vs-done__summary">
          {order.items.map((item) => (
            <div className="vs-summary__row" key={item.id}>
              <span>
                {item.product_name} ×{item.quantity}
              </span>
              <strong>{money(item.line_total)}</strong>
            </div>
          ))}
          <div className="vs-summary__row">
            <span>المجموع الفرعي</span>
            <strong>{money(order.subtotal)}</strong>
          </div>
          {order.discount > 0 && (
            <div className="vs-summary__row vs-summary__row--good">
              <span>الخصم</span>
              <strong>−{money(order.discount)}</strong>
            </div>
          )}
          <div className="vs-summary__row">
            <span>التوصيل {order.delivery_area_name ? `(${order.delivery_area_name})` : ""}</span>
            <strong>{money(order.delivery_fee)}</strong>
          </div>
          <div className="vs-summary__row">
            <span>طريقة الدفع</span>
            <strong>{paymentMethodLabels[order.payment_method] || order.payment_method}</strong>
          </div>
          <div className="vs-summary__total">
            <span>الإجمالي</span>
            <strong>{money(order.total)}</strong>
          </div>
        </div>

        <div className="vs-done__next">
          <h2 className="vs-done__nexttitle">ما الخطوة التالية؟</h2>
          <ol className="vs-bullets">
            <li>سنراجع الطلب ونتواصل معك لتأكيد التفاصيل.</li>
            <li>يُجهَّز الطلب ثم يُسلَّم لمندوب التوصيل في منطقتك.</li>
            <li>الدفع يتم عند الاستلام أو بتحويل يدوي حسب ما اخترته.</li>
          </ol>
        </div>

        <div className="vs-done__actions">
          <Link to="/shop" className="vs-btn vs-btn--ghost vs-btn--lg">
            متابعة التسوّق
          </Link>
        </div>
      </div>
    </section>
  );
}
