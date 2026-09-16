import { useStore } from "../../../app/StoreProvider.jsx";
import { useMoney } from "../../../hooks/useStorefront.js";

export default function FreeShippingBar() {
  const { deliveryAreas } = useStore();
  const money = useMoney();
  const areas = deliveryAreas.filter((area) => area.freeOver != null);
  if (!areas.length) return null;

  return <div className="vs-free-shipping-bar" dir="rtl" aria-label="توصيل مجاني">
    توصيل مجاني: {areas.map((area, index) => <span key={area.id}>
      {index > 0 && " • "}{area.name} فوق <bdi>{money(area.freeOver)}</bdi>
    </span>)}
  </div>;
}
