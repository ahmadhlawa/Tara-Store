// Presentation constants only.
//
// Every piece of commercial content (products, categories, prices, delivery areas,
// coupons, store identity) now comes from the API via
// src/services/*. What is left here is navigation structure and static copy that
// belongs to the storefront layout itself.

// Primary navigation. Every destination here is a route that always has
// something to show; the narrower tools live in the footer instead.
export const navLinks = [
  { label: "الرئيسية", href: "/" },
  { label: "كل المنتجات", href: "/shop" },
  { label: "العروض", href: "/offers" },
  { label: "البكجات", href: "/packages" },
  { label: "تواصل معنا", href: "/contact" },
];

export const footerLinks = {
  shop: {
    title: "التسوّق",
    items: [
      ["كل المنتجات", "/shop"],
      ["العروض", "/offers"],
      ["البكجات", "/packages"],
    ],
  },
  service: {
    title: "خدمة العملاء",
    items: [
      ["عربة التسوّق", "/cart"],
      ["تواصل معنا", "/contact"],
    ],
  },
  policies: {
    title: "معلومات",
    items: [
      ["من نحن", "/page/about"],
      ["سياسة الشحن", "/page/shipping-policy"],
      ["سياسة التبديل والإرجاع", "/page/return-policy"],
      ["سياسة الخصوصية", "/page/privacy-policy"],
      ["الشروط والأحكام", "/page/terms"],
    ],
  },
};

export const trustFeatures = [
  { title: "توصيل لكل المناطق", desc: "خلال ١–٤ أيام عمل", icon: "truck" },
  { title: "دفع عند الاستلام", desc: "نقداً للمندوب عند التسليم", icon: "wallet" },
  { title: "إرجاع خلال ١٤ يوماً", desc: "على المنتجات غير المستخدمة", icon: "refresh" },
  { title: "دعم فني حرفي", desc: "نساعدك في اختيار المواد", icon: "headset" },
];

export const trustGlyphs = { truck: "⛟", wallet: "₪", refresh: "↺", headset: "☏" };

export const paymentMethods = [
  {
    key: "cash_on_delivery",
    label: "الدفع عند الاستلام",
    desc: "ادفع نقداً للمندوب عند التسليم",
  },
];

export const paymentMethodLabels = {
  cash_on_delivery: "الدفع عند الاستلام",
  bank_transfer: "تحويل بنكي / يدوي",
};

export const invoiceStatusLabels = {
  issued: "صادرة",
  cancelled: "ملغاة",
};

export const orderStatusLabels = {
  new: "طلب جديد",
  confirmed: "طلب مؤكد",
  ready: "جاهز",
  delivered: "تم تسليمه",
  completed: "مكتمل",
  cancelled: "طلب ملغى",
  pending: "طلب مؤكد",
  reviewing: "طلب مؤكد",
  processing: "جاهز",
  preparing: "جاهز",
  shipped: "تم تسليمه",
  out_for_delivery: "تم تسليمه",
};
