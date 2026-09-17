import { useLocale } from "../../../i18n/locale.jsx";
import { Link } from "../../../i18n/routing.jsx";
import { ShieldIcon, TruckIcon, WalletIcon } from "../shell/icons.jsx";
import { useViewportReveal } from "../../../hooks/useViewportReveal.js";

export default function TrustStrip() {
  const { t } = useLocale();
  const paymentReveal = useViewportReveal(0);
  const deliveryReveal = useViewportReveal(70);
  const returnReveal = useViewportReveal(140);

  const paymentText = t("ادفع نقداً للمندوب عند التسليم");

  return (
    <div className="vs-trust">
      <div className="vs-trust__item" {...paymentReveal}>
        <span className="vs-trust__icon">
          <WalletIcon size={20} />
        </span>
        <span>
          <span className="vs-trust__title">{t("الدفع عند الاستلام")}</span>
          <br />
          <span className="vs-trust__desc">{paymentText}</span>
        </span>
      </div>

      <div className="vs-trust__item" {...deliveryReveal}>
        <span className="vs-trust__icon">
          <TruckIcon size={20} />
        </span>
        <span>
          <span className="vs-trust__title">{t("التوصيل إلى جميع المناطق")}</span>
          <br />
          <span className="vs-trust__desc">{t("تُحتسب رسوم التوصيل عند إتمام الطلب")}</span>
        </span>
      </div>

      <Link to="/page/return-policy" className="vs-trust__item" {...returnReveal}>
        <span className="vs-trust__icon">
          <ShieldIcon size={20} />
        </span>
        <span>
          <span className="vs-trust__title">{t("سياسة التبديل والإرجاع")}</span>
          <br />
          <span className="vs-trust__desc">{t("اقرأ الشروط قبل الطلب")}</span>
        </span>
      </Link>
    </div>
  );
}
