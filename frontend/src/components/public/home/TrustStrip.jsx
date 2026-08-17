import { Link } from "react-router-dom";
import { useStore } from "../../../app/StoreProvider.jsx";
import { ShieldIcon, TruckIcon, WalletIcon } from "../shell/icons.jsx";
import { useViewportReveal } from "../../../hooks/useViewportReveal.js";

/**
 * Only claims the store can actually keep: the payment methods the checkout
 * really offers, the delivery areas the API really returns, and a policy page
 * that really exists. Nothing here is invented copy.
 */
export default function TrustStrip() {
  const { deliveryAreas, settings } = useStore();
  const paymentReveal = useViewportReveal(0);
  const deliveryReveal = useViewportReveal(70);
  const returnReveal = useViewportReveal(140);

  // Checkout offers manual transfer only once the owner has published account
  // details for it, so this line has to follow the same rule or it advertises a
  // method the customer will not find.
  const paymentText = settings.manualPaymentInstructions
    ? "أو تحويل بنكي يدوي — بدون بطاقات"
    : "ادفع نقداً للمندوب عند التسليم — بدون بطاقات";

  const areasText = !deliveryAreas.length
    ? null
    : deliveryAreas.length === 1
      ? `توصيل إلى ${deliveryAreas[0].name}`
      : `توصيل إلى ${deliveryAreas.length} مناطق`;

  return (
    <div className="vs-trust">
      <div className="vs-trust__item" {...paymentReveal}>
        <span className="vs-trust__icon">
          <WalletIcon size={20} />
        </span>
        <span>
          <span className="vs-trust__title">الدفع عند الاستلام</span>
          <br />
          <span className="vs-trust__desc">{paymentText}</span>
        </span>
      </div>

      {areasText && (
        <div className="vs-trust__item" {...deliveryReveal}>
          <span className="vs-trust__icon">
            <TruckIcon size={20} />
          </span>
          <span>
            <span className="vs-trust__title">{areasText}</span>
            <br />
            <span className="vs-trust__desc">تُحتسب رسوم التوصيل عند إتمام الطلب</span>
          </span>
        </div>
      )}

      <Link to="/page/return-policy" className="vs-trust__item" {...returnReveal}>
        <span className="vs-trust__icon">
          <ShieldIcon size={20} />
        </span>
        <span>
          <span className="vs-trust__title">سياسة التبديل والإرجاع</span>
          <br />
          <span className="vs-trust__desc">اقرأ الشروط قبل الطلب</span>
        </span>
      </Link>
    </div>
  );
}
