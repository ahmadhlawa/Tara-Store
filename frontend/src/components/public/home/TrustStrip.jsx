import { Link } from "react-router-dom";
import { ShieldIcon, TruckIcon, WalletIcon } from "../shell/icons.jsx";
import { useViewportReveal } from "../../../hooks/useViewportReveal.js";

export default function TrustStrip() {
  const paymentReveal = useViewportReveal(0);
  const deliveryReveal = useViewportReveal(70);
  const returnReveal = useViewportReveal(140);

  const paymentText = "ادفع نقداً للمندوب عند التسليم";

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

      <div className="vs-trust__item" {...deliveryReveal}>
        <span className="vs-trust__icon">
          <TruckIcon size={20} />
        </span>
        <span>
          <span className="vs-trust__title">التوصيل إلى جميع المناطق</span>
          <br />
          <span className="vs-trust__desc">تُحتسب رسوم التوصيل عند إتمام الطلب</span>
        </span>
      </div>

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
