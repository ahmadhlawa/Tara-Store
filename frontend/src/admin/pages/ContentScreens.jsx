import { useCallback } from "react";
import { adminApi } from "../../api/adminApi.js";
import ResourceScreen from "../ResourceScreen.jsx";
import { Badge } from "../ui.jsx";
import { formatDate } from "../../utils/format.js";

const activeColumn = {
  key: "is_active",
  title: "الحالة",
  render: (row) => <Badge tone={row.is_active ? "good" : "bad"}>{row.is_active ? "ظاهر" : "مخفي"}</Badge>,
};

export function HeroSlidesPage() {
  const fetchList = useCallback(() => adminApi.listHeroSlides(), []);
  return (
    <ResourceScreen
      title="شرائح الواجهة"
      description="الشرائح المتحركة أعلى الصفحة الرئيسية. إذا رفعت صورة إعلان جاهزة ولم تضف عنواناً فرعياً أو وصفاً أو زراً، تُعرض الصورة وحدها دون أي نص فوقها، ويبقى «العنوان» اسماً للشريحة ونصاً بديلاً للصورة."
      createLabel="إضافة شريحة"
      fetchList={fetchList}
      createItem={adminApi.createHeroSlide}
      updateItem={adminApi.updateHeroSlide}
      deleteItem={adminApi.deleteHeroSlide}
      describeRow={(row) => row.title}
      columns={[
        { key: "title", title: "العنوان" },
        { key: "subtitle", title: "العنوان الفرعي", render: (row) => row.subtitle || "—" },
        { key: "button_label", title: "زر", render: (row) => row.button_label || "—" },
        { key: "sort_order", title: "الترتيب" },
        activeColumn,
      ]}
      fields={[
        { name: "title", title: "العنوان", required: true },
        { name: "subtitle", title: "العنوان الفرعي" },
        { name: "description", title: "الوصف", type: "textarea", rows: 3 },
        { name: "image_url", title: "الصورة", type: "media", emptyAsNull: true },
        { name: "button_label", title: "نص الزر" },
        { name: "button_url", title: "رابط الزر", placeholder: "/shop" },
        { name: "starts_at", title: "يبدأ في", type: "date" },
        { name: "ends_at", title: "ينتهي في", type: "date" },
        { name: "sort_order", title: "الترتيب", type: "number", defaultValue: 0 },
        { name: "is_active", title: "ظاهر", type: "checkbox", defaultValue: true },
      ]}
    />
  );
}

export function BannersPage() {
  const fetchList = useCallback(() => adminApi.listBanners(), []);
  return (
    <ResourceScreen
      title="البانرات"
      description="بانرات ترويجية في الصفحة الرئيسية."
      createLabel="إضافة بانر"
      fetchList={fetchList}
      createItem={adminApi.createBanner}
      updateItem={adminApi.updateBanner}
      deleteItem={adminApi.deleteBanner}
      describeRow={(row) => row.title}
      columns={[
        { key: "title", title: "العنوان" },
        { key: "placement", title: "الموضع" },
        { key: "link_url", title: "الرابط", render: (row) => row.link_url || "—" },
        { key: "sort_order", title: "الترتيب" },
        activeColumn,
      ]}
      fields={[
        { name: "title", title: "العنوان", required: true },
        { name: "subtitle", title: "العنوان الفرعي" },
        {
          name: "placement",
          title: "الموضع",
          type: "select",
          required: true,
          defaultValue: "home_side",
          options: [
            { value: "home_main", label: "الصفحة الرئيسية — رئيسي" },
            { value: "home_side", label: "الصفحة الرئيسية — جانبي" },
            { value: "home_strip", label: "الصفحة الرئيسية — شريط" },
            { value: "category_top", label: "أعلى صفحة القسم" },
          ],
        },
        { name: "image_url", title: "الصورة", type: "media", emptyAsNull: true },
        { name: "link_url", title: "الرابط", placeholder: "/offers" },
        { name: "starts_at", title: "يبدأ في", type: "date" },
        { name: "ends_at", title: "ينتهي في", type: "date" },
        { name: "sort_order", title: "الترتيب", type: "number", defaultValue: 0 },
        { name: "is_active", title: "ظاهر", type: "checkbox", defaultValue: true },
      ]}
    />
  );
}

export function HomeSectionsPage() {
  const fetchList = useCallback(() => adminApi.listHomeSections(), []);
  return (
    <ResourceScreen
      title="أقسام الصفحة الرئيسية"
      description="تحكّم في ترتيب أقسام الصفحة الرئيسية وظهورها وعناوينها."
      createLabel="إضافة قسم"
      fetchList={fetchList}
      createItem={adminApi.createHomeSection}
      updateItem={adminApi.updateHomeSection}
      deleteItem={adminApi.deleteHomeSection}
      describeRow={(row) => row.title || row.section_key}
      columns={[
        { key: "title", title: "العنوان", render: (row) => row.title || "—" },
        { key: "section_key", title: "المفتاح" },
        { key: "section_type", title: "النوع" },
        { key: "sort_order", title: "الترتيب" },
        {
          key: "is_visible",
          title: "الظهور",
          render: (row) => (
            <Badge tone={row.is_visible ? "good" : "bad"}>{row.is_visible ? "ظاهر" : "مخفي"}</Badge>
          ),
        },
      ]}
      fields={[
        {
          name: "section_key",
          title: "المفتاح الثابت",
          hint: "أحرف إنجليزية صغيرة وأرقام وشرطات فقط. لا يُستخدم إلا عند الإنشاء.",
          required: true,
        },
        {
          name: "section_type",
          title: "نوع القسم",
          type: "select",
          required: true,
          defaultValue: "featured_products",
          options: [
            { value: "featured_products", label: "منتجات مختارة" },
            { value: "new_products", label: "منتجات جديدة" },
            { value: "bestsellers", label: "الأكثر مبيعاً" },
            { value: "packages", label: "البكجات" },
            { value: "silicone_molds", label: "قوالب سيليكون" },
            { value: "categories", label: "الأقسام" },
            { value: "promo_banner", label: "بانر ترويجي" },
            { value: "custom_text", label: "نص مخصّص" },
          ],
        },
        { name: "title", title: "العنوان الظاهر" },
        { name: "description", title: "الوصف", type: "textarea", rows: 3 },
        { name: "sort_order", title: "الترتيب", type: "number", defaultValue: 0 },
        { name: "is_visible", title: "ظاهر في الواجهة", type: "checkbox", defaultValue: true },
      ]}
    />
  );
}

export function ArticlesPage() {
  const fetchList = useCallback((params) => adminApi.listArticles(params), []);
  return (
    <ResourceScreen
      title="المقالات"
      description="مقالات المدونة. غير المنشورة لا تظهر في الواجهة."
      paginated
      createLabel="مقال جديد"
      fetchList={fetchList}
      createItem={adminApi.createArticle}
      updateItem={adminApi.updateArticle}
      deleteItem={adminApi.deleteArticle}
      describeRow={(row) => row.title}
      columns={[
        { key: "title", title: "العنوان" },
        { key: "category_label", title: "التصنيف", render: (row) => row.category_label || "—" },
        { key: "published_at", title: "تاريخ النشر", render: (row) => formatDate(row.published_at) || "—" },
        {
          key: "is_published",
          title: "الحالة",
          render: (row) => (
            <Badge tone={row.is_published ? "good" : "warn"}>{row.is_published ? "منشور" : "مسودة"}</Badge>
          ),
        },
      ]}
      fields={[
        { name: "title", title: "العنوان", required: true },
        { name: "slug", title: "الرابط (اختياري)", omitWhenEmpty: true },
        { name: "category_label", title: "التصنيف" },
        { name: "author_name", title: "الكاتب" },
        { name: "excerpt", title: "المقدمة", type: "textarea", rows: 3 },
        { name: "content", title: "المحتوى", type: "textarea", rows: 10, hint: "افصل الفقرات بسطر فارغ." },
        { name: "featured_image_url", title: "صورة المقال", type: "media", emptyAsNull: true },
        { name: "seo_title", title: "عنوان SEO" },
        { name: "seo_description", title: "وصف SEO", type: "textarea", rows: 2 },
        { name: "is_published", title: "منشور", type: "checkbox" },
      ]}
    />
  );
}

export function StaticPagesPage() {
  const fetchList = useCallback(() => adminApi.listPages(), []);
  return (
    <ResourceScreen
      title="الصفحات"
      description="من نحن، الخصوصية، الشروط، الإرجاع، الشحن، وتواصل معنا."
      createLabel="صفحة جديدة"
      fetchList={fetchList}
      createItem={adminApi.createPage}
      updateItem={adminApi.updatePage}
      deleteItem={adminApi.deletePage}
      describeRow={(row) => row.title}
      columns={[
        { key: "title", title: "العنوان" },
        { key: "slug", title: "الرابط" },
        {
          key: "is_published",
          title: "الحالة",
          render: (row) => (
            <Badge tone={row.is_published ? "good" : "warn"}>{row.is_published ? "منشورة" : "مخفية"}</Badge>
          ),
        },
      ]}
      fields={[
        { name: "title", title: "العنوان", required: true },
        { name: "slug", title: "الرابط (اختياري)", omitWhenEmpty: true, hint: "مثال: about" },
        { name: "lead", title: "المقدمة", type: "textarea", rows: 2 },
        { name: "content", title: "المحتوى", type: "textarea", rows: 10, hint: "افصل الفقرات بسطر فارغ." },
        { name: "seo_title", title: "عنوان SEO" },
        { name: "seo_description", title: "وصف SEO", type: "textarea", rows: 2 },
        { name: "is_published", title: "منشورة", type: "checkbox", defaultValue: true },
      ]}
    />
  );
}
