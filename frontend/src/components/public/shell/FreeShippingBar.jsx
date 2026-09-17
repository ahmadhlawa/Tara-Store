import { useLocale } from "../../../i18n/locale.jsx";
import { useStore } from "../../../app/StoreProvider.jsx";
import { useMoney } from "../../../hooks/useStorefront.js";

export default function FreeShippingBar() {
  const { locale, t } = useLocale();
  const { deliveryAreas } = useStore();
  const money = useMoney();
  const areas = deliveryAreas.filter((area) => area.freeOver != null);
  if (!areas.length) return null;

  return <div className="vs-free-shipping-bar" dir={locale === "en" ? "ltr" : "rtl"} aria-label={t("توصيل مجاني")}>{t("توصيل مجاني:")}{" "}{areas.map((area, index) => <span key={area.id}>
      {index > 0 && " • "}{area.name}{" "}{t("فوق")}{" "}<bdi>{money(area.freeOver)}</bdi>
    </span>)}
  </div>;
}
