import { useLocale } from "../../../i18n/locale.jsx";
import { Link } from "../../../i18n/routing.jsx";
import { Drawer } from "../overlays/Overlay.jsx";
import Media from "../shell/Media.jsx";
import FreeDeliveryNotice from "./FreeDeliveryNotice.jsx";
import QuantityStepper from "./QuantityStepper.jsx";
import { useCartLines } from "./useCartLines.js";
import { CartIcon, TrashIcon } from "../shell/icons.jsx";

export default function CartDrawer({ open, onClose }) {
  const { t } = useLocale();
  const { lines, count, subtotal, subtotalText, empty } = useCartLines();

  return (
    <Drawer
      open={open}
      onClose={onClose}
      side="left"
      label={t("عربة التسوّق")}
      title={t("عربة التسوّق ({0})", [count])}
      footer={
        empty ? null : (
          <>
            <div className="vs-cartdrawer__totals">
              <span>{t("المجموع الفرعي")}</span>
              <strong>{subtotalText}</strong>
            </div>
            <p className="vs-cartdrawer__hint">{t("تُحتسب رسوم التوصيل حسب المنطقة في صفحة إتمام الطلب.")}{" "}</p>
            <FreeDeliveryNotice subtotal={subtotal} />
            <Link
              to="/checkout"
              className="vs-btn vs-btn--primary vs-btn--lg vs-btn--block"
              onClick={onClose}
            >{t("إتمام الطلب")}{" "}</Link>
          </>
        )
      }
    >
      {empty ? (
        <div className="vs-cartdrawer__empty">
          <span className="vs-state__icon">
            <CartIcon size={26} />
          </span>
          <strong className="vs-state__title">{t("لا توجد منتجات بعد")}</strong>
          <p className="vs-state__body">{t("أضف منتجات من الأقسام لتظهر هنا.")}</p>
          <Link to="/shop" className="vs-btn vs-btn--primary" onClick={onClose}>{t("تصفّح المتجر")}{" "}</Link>
        </div>
      ) : (
        <ul className="vs-cartdrawer__list">
          {lines.map((line) => (
            <li key={line.key} className="vs-cartline" data-leaving={line.leaving}>
              <Link to={line.href} onClick={onClose} className="vs-cartline__thumb" tabIndex={-1}>
                <Media src={line.imageUrl} fallback={line.bg} alt="" ratio="1 / 1" />
              </Link>
              <div className="vs-cartline__body">
                <Link to={line.href} onClick={onClose} className="vs-cartline__name vs-clamp-2">
                  {line.name}
                </Link>
                {line.variationText && (
                  <span className="vs-cartline__variant">{line.variationText}</span>
                )}
                <span className="vs-cartline__unit">{t("سعر القطعة:")}{" "}{line.unitText}</span>
                <div className="vs-cartline__row">
                  <QuantityStepper
                    value={line.qty}
                    onDecrease={line.decrease}
                    onIncrease={line.increase}
                    size="sm"
                    label={t("الكمية من {0}", [line.name])}
                  />
                  <strong className="vs-cartline__total">{line.lineText}</strong>
                  <button
                    type="button"
                    className="vs-iconbtn vs-iconbtn--bare vs-cartline__remove"
                    onClick={line.remove}
                    aria-label={t("إزالة {0} من العربة", [line.name])}
                  >
                    <TrashIcon size={17} />
                  </button>
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Drawer>
  );
}
