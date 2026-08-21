import { useEffect, useRef, useState } from "react";
import sx from "../sx.js";
import { Badge, Button } from "./ui.jsx";

// One source of truth: the order of this list. The first image is the cover, so
// there is no primary flag to set — moving an image to the front promotes it.

const move = (items, from, to) => {
  const next = [...items];
  const [item] = next.splice(from, 1);
  next.splice(to, 0, item);
  return next;
};

const ids = (items) => items.map((item) => item.id);

/**
 * The product's images in their canonical order, with drag-and-drop and the
 * arrow controls that keep reordering reachable on a phone or by keyboard.
 */
export default function ProductImageGallery({ images, onReorder, onDelete }) {
  const [order, setOrder] = useState(images);
  const [dragging, setDragging] = useState(null);
  const [saving, setSaving] = useState(false);
  const serverOrder = useRef(images);

  // Follow the server whenever it hands us a different set or sequence — an
  // added or deleted image lands here the same way a rejected reorder does.
  useEffect(() => {
    serverOrder.current = images;
    setOrder((current) =>
      ids(current).join() === ids(images).join() ? current : images,
    );
  }, [images]);

  const apply = async (next) => {
    if (ids(next).join() === ids(order).join()) return;
    setOrder(next);
    setSaving(true);
    try {
      await onReorder(ids(next));
    } catch {
      // The save failed, so the shown order is not the stored one. Snap back to
      // what the server last told us rather than leaving a convincing lie.
      setOrder(serverOrder.current);
    } finally {
      setSaving(false);
    }
  };

  if (!order.length) {
    return <span style={sx`font-size:13px;color:#8A7F95`}>لا توجد صور بعد — سيظهر المنتج بخلفية متدرجة.</span>;
  }

  return (
    <div style={sx`display:flex;gap:12px;flex-wrap:wrap`}>
      {order.map((image, index) => (
        <div
          key={image.id}
          draggable
          aria-label={`الصورة ${index + 1} من ${order.length}`}
          onDragStart={(event) => {
            setDragging(index);
            event.dataTransfer.effectAllowed = "move";
          }}
          onDragOver={(event) => event.preventDefault()}
          onDrop={(event) => {
            event.preventDefault();
            if (dragging === null || dragging === index) return;
            apply(move(order, dragging, index));
            setDragging(null);
          }}
          onDragEnd={() => setDragging(null)}
          style={sx`width:140px;display:flex;flex-direction:column;gap:6px;padding:8px;border:1px solid ${index === 0 ? "var(--selection-border)" : "#E7DCF2"};border-radius:12px;background:#fff;opacity:${dragging === index ? 0.5 : 1}`}
        >
          <span
            title="اسحب لإعادة الترتيب"
            style={sx`cursor:grab;font-size:13px;color:#8A7F95;letter-spacing:2px;text-align:center;user-select:none`}
          >
            ⠿
          </span>
          <span style={sx`width:124px;height:124px;border-radius:10px;background:#F5EDE3 url("${image.url}") center/cover no-repeat`}></span>
          {index === 0 ? (
            <Badge tone="good">الصورة الرئيسية</Badge>
          ) : (
            <span style={sx`font-size:11.5px;color:#8A7F95;text-align:center`}>الترتيب {index + 1}</span>
          )}
          <div style={sx`display:flex;gap:6px`}>
            <Button
              variant="ghost"
              aria-label={`تحريك للأعلى: ${image.alt_text || image.url}`}
              title="تحريك للأعلى"
              disabled={index === 0 || saving}
              onClick={() => apply(move(order, index, index - 1))}
              style={sx`flex:1;min-height:34px;padding:0;font-size:14px`}
            >
              ↑
            </Button>
            <Button
              variant="ghost"
              aria-label={`تحريك للأسفل: ${image.alt_text || image.url}`}
              title="تحريك للأسفل"
              disabled={index === order.length - 1 || saving}
              onClick={() => apply(move(order, index, index + 1))}
              style={sx`flex:1;min-height:34px;padding:0;font-size:14px`}
            >
              ↓
            </Button>
          </div>
          <Button
            variant="danger"
            style={sx`min-height:34px;font-size:12.5px`}
            onClick={() => onDelete(image.id)}
          >
            حذف
          </Button>
        </div>
      ))}
    </div>
  );
}
