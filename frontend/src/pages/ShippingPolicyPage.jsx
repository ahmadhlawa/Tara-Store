import { useEffect, useState } from "react";
import { useLocale } from "../i18n/locale.jsx";
import { useMoney } from "../hooks/useStorefront.js";
import { storefrontService } from "../services/storefront.js";

export default function ShippingPolicyPage() {
  const { locale, t } = useLocale();
  const money = useMoney();
  const [areas, setAreas] = useState([]);
  const [status, setStatus] = useState("loading");
  useEffect(() => {
    let cancelled = false;
    setStatus("loading");
    storefrontService.deliveryAreas().then((rows) => {
      if (!cancelled) { setAreas(rows); setStatus("ready"); }
    }).catch(() => !cancelled && setStatus("error"));
    return () => { cancelled = true; };
  }, [locale]);
  return <article className="vs-container vs-container--narrow vs-section">
    <h1 className="vs-page__title">{t("سياسة الشحن")}</h1>
    <p className="vs-prose">{t("يتم التوصيل إلى المناطق المتاحة أدناه. يرجى إدخال عنوان صحيح ورقم هاتف متاح لتنسيق استلام الطلب.")}</p>
    {status === "loading" && <p role="status">{t("جارٍ التحميل…")}</p>}
    {status === "error" && <p role="alert">{t("تعذر تحميل رسوم التوصيل. يرجى المحاولة لاحقاً.")}</p>}
    {status === "ready" && <div className="vs-page__body">{areas.map((area) => <section key={area.id}>
      <h2>{area.name}</h2>
      <p>{t("رسوم التوصيل")}: <strong className="vs-price__now">{money(area.price)}</strong></p>
      {area.freeOver != null && <p>{t("توصيل مجاني للطلبات من")}: <strong className="vs-price__now">{money(area.freeOver)}</strong></p>}
      {area.eta && <p>{t("مدة التوصيل المتوقعة")}: {area.eta}</p>}
      {area.minOrder != null && <p>{t("الحد الأدنى للطلب")}: <strong className="vs-price__now">{money(area.minOrder)}</strong></p>}
    </section>)}</div>}
    <p className="vs-prose">{t("قد تتأخر مواعيد التوصيل بسبب الظروف الخارجة عن إرادتنا. في حال تعذر تسليم الطلب، سنتواصل معكم لتنسيق موعد آخر. يرجى التواصل معنا عند وجود مشكلة في التوصيل.")}</p>
  </article>;
}
