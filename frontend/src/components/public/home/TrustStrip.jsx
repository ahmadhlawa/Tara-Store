import { Link } from "react-router-dom";
import { useStore } from "../../../app/StoreProvider.jsx";
import { ShieldIcon, TruckIcon, WalletIcon } from "../shell/icons.jsx";

/**
 * Only claims the store can actually keep: the payment methods the checkout
 * really offers, the delivery areas the API really returns, and a policy page
 * that really exists. Nothing here is invented copy.
 */
export default function TrustStrip() {
  const { deliveryAreas } = useStore();

  const areasText = !deliveryAreas.length
    ? null
    : deliveryAreas.length === 1
      ? `توصيل إلى ${deliveryAreas[0].name}`
      : `توصيل إلى ${deliveryAreas.length} مناطق`;

  return (
    <div className="vs-trust">
      <div className="vs-trust__item">
        <span className="vs-trust__icon">
          <WalletIcon size={20} />
        </span>
        <span>
          <span className="vs-trust__title">الدفع عند الاستلام</span>
          <br />
          <span className="vs-trust__desc">أو تحويل بنكي يدوي — بدون بطاقات</span>
        </span>
      </div>

      {areasText && (
        <div className="vs-trust__item">
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

      <Link to="/page/return-policy" className="vs-trust__item">
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
