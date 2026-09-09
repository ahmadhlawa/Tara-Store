import CategoryCard from "../components/public/catalog/CategoryCard.jsx";
import { Link } from "react-router-dom";
import { useStore } from "../app/StoreProvider.jsx";
import { useCategoryNav } from "../hooks/useStorefront.js";
import useSeo from "../hooks/useSeo.js";

export default function CategoriesPage() {
  const { settings } = useStore();
  const categories = useCategoryNav();
  useSeo({
    title: `الأقسام | ${settings.storeName}`,
    description: "تصفّح أقسام متجر تارا.",
    baseUrl: settings.publicBaseUrl,
    path: "/categories",
  });

  return (
    <>
      <header className="vs-cathead vs-cathead--plain">
        <div className="vs-container vs-cathead__inner">
          <nav className="vs-crumbs" aria-label="مسار التصفح"><Link to="/">الرئيسية</Link><span aria-hidden="true">›</span><span>الأقسام</span></nav>
          <h1 className="vs-cathead__title">كل الأقسام</h1>
          <p className="vs-cathead__desc">اختر القسم المناسب لتصفّح منتجاته.</p>
        </div>
      </header>
      <main className="vs-container vs-section">
        <div className="vs-grid vs-grid--cats">
          {categories.map((category, index) => (
            <CategoryCard key={category.slug} category={category} eager={index < 4} />
          ))}
        </div>
      </main>
    </>
  );
}
