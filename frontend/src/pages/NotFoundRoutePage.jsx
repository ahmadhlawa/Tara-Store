import { Link } from "react-router-dom";
import useSeo from "../hooks/useSeo.js";

export default function NotFoundRoutePage() {
  useSeo({ title: "الصفحة غير موجودة", noindex: true });
  return (
    <section className="vs-container vs-section">
      <div className="vs-state vs-notfound">
        <span className="vs-notfound__code">404</span>
        <h1 className="vs-state__title">الصفحة غير موجودة</h1>
        <p className="vs-state__body">
          الرابط الذي فتحته لم يعد متاحاً، أو ربما تغيّر عنوانه. جرّب البحث أو ابدأ من الأقسام.
        </p>
        <div className="vs-notfound__actions">
          <Link to="/" className="vs-btn vs-btn--primary">
            الصفحة الرئيسية
          </Link>
          <Link to="/shop" className="vs-btn vs-btn--ghost">
            تصفّح المنتجات
          </Link>
        </div>
      </div>
    </section>
  );
}
