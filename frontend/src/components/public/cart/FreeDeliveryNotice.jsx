import { useMemo } from "react";
import { useStore } from "../../../app/StoreProvider.jsx";
import { useMoney } from "../../../hooks/useStorefront.js";

/**
 * The free-delivery rule, shown where the customer is deciding: in the cart and
 * again in the checkout summary.
 *
 * Every number here comes from the delivery areas the API returned, and the same
 * thresholds are what the server charges against — this states the rule, it does
 * not implement a second one. An area with no threshold contributes nothing, so a
 * store that has never offered free delivery renders nothing at all.
 *
 * Before an area is chosen the notice covers all of them, grouped by threshold,
 * because that is genuinely the customer's position in the cart: they do not yet
 * know what they will pay. Once an area is selected the notice narrows to it.
 */
export default function FreeDeliveryNotice({ subtotal, areaId = null }) {
  const { deliveryAreas } = useStore();
  const money = useMoney();

  const groups = useMemo(() => {
    const eligible = deliveryAreas.filter((area) => area.freeOver != null && area.freeOver > 0);
    const selected = areaId ? eligible.filter((area) => area.id === areaId) : eligible;
    const byThreshold = new Map();
    selected.forEach((area) => {
      const names = byThreshold.get(area.freeOver) || [];
      names.push(area.name);
      byThreshold.set(area.freeOver, names);
    });
    return [...byThreshold.entries()]
      .sort(([a], [b]) => a - b)
      .map(([threshold, names]) => ({ threshold, names, reached: subtotal >= threshold }));
  }, [deliveryAreas, areaId, subtotal]);

  if (!groups.length) return null;

  return (
    <div className="vs-freeship" role="status">
      <span className="vs-freeship__title">التوصيل المجاني</span>
      {groups.map((group) => (
        <p
          key={group.threshold}
          className={`vs-freeship__row${group.reached ? " is-reached" : ""}`}
        >
          {group.reached ? (
            <>طلبك مؤهل للتوصيل المجاني إلى {group.names.join("، ")}.</>
          ) : (
            <>
              أضف {money(group.threshold - subtotal)} للحصول على توصيل مجاني إلى{" "}
              {group.names.join("، ")} (الطلبات من {money(group.threshold)}).
            </>
          )}
        </p>
      ))}
    </div>
  );
}
