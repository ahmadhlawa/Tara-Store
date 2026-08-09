import { Link } from "react-router-dom";
import { Drawer } from "../overlays/Overlay.jsx";
import Media from "../shell/Media.jsx";
import QuantityStepper from "./QuantityStepper.jsx";
import { useCartLines } from "./useCartLines.js";
import { CartIcon, TrashIcon } from "../shell/icons.jsx";

export default function CartDrawer({ open, onClose }) {
  const { lines, count, subtotalText, empty } = useCartLines();

  return (
    <Drawer
      open={open}
      onClose={onClose}
      side="left"
      label="عربة التسوّق"
      title={`عربة التسوّق (${count})`}
      footer={
        empty ? null : (
          <>
            <div className="vs-cartdrawer__totals">
              <span>المجموع الفرعي</span>
              <strong>{subtotalText}</strong>
            </div>
            <p className="vs-cartdrawer__hint">
              تُحتسب رسوم التوصيل حسب المنطقة في صفحة إتمام الطلب.
            </p>
            <Link
              to="/checkout"
              className="vs-btn vs-btn--primary vs-btn--lg vs-btn--block"
              onClick={onClose}
            >
              إتمام الطلب
            </Link>
            <Link to="/cart" className="vs-btn vs-btn--ghost vs-btn--block" onClick={onClose}>
              عرض العربة
            </Link>
          </>
        )
      }
    >
      {empty ? (
        <div className="vs-cartdrawer__empty">
          <span className="vs-state__icon">
            <CartIcon size={26} />
          </span>
          <strong className="vs-state__title">لا توجد منتجات بعد</strong>
          <p className="vs-state__body">أضف منتجات من الأقسام لتظهر هنا.</p>
          <Link to="/shop" className="vs-btn vs-btn--primary" onClick={onClose}>
            تصفّح المتجر
          </Link>
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
                <span className="vs-cartline__unit">سعر القطعة: {line.unitText}</span>
                <div className="vs-cartline__row">
                  <QuantityStepper
                    value={line.qty}
                    onDecrease={line.decrease}
                    onIncrease={line.increase}
                    size="sm"
                    label={`الكمية من ${line.name}`}
                  />
                  <strong className="vs-cartline__total">{line.lineText}</strong>
                  <button
                    type="button"
                    className="vs-iconbtn vs-iconbtn--bare vs-cartline__remove"
                    onClick={line.remove}
                    aria-label={`إزالة ${line.name} من العربة`}
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
