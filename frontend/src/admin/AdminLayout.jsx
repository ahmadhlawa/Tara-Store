import { useEffect, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { LOGO_URL, STORE_NAME_AR } from "../brand.js";
import sx from "../sx.js";
import { useAdminAuth } from "./AdminAuth.jsx";
import { Button } from "./ui.jsx";

const NAV = [
  { to: "/admin", label: "لوحة التحكم", end: true },
  { to: "/admin/products", label: "المنتجات" },
  { to: "/admin/categories", label: "الأقسام" },
  { to: "/admin/orders", label: "الطلبات" },
  { to: "/admin/orders/manual", label: "طلب يدوي جديد", superOnly: true },
  { to: "/admin/invoices", label: "أرشيف الفواتير" },
  { to: "/admin/coupons", label: "أكواد الخصم" },
  { to: "/admin/delivery", label: "مناطق التوصيل" },
  { to: "/admin/hero", label: "شرائح الواجهة" },
  { to: "/admin/banners", label: "البانرات" },
  { to: "/admin/articles", label: "المقالات" },
  { to: "/admin/pages", label: "الصفحات" },
  { to: "/admin/media", label: "الوسائط" },
  { to: "/admin/settings", label: "روابط المتجر" },
  { to: "/admin/admins", label: "حسابات الإدارة", superOnly: true },
  { to: "/admin/audit", label: "سجل التغييرات", superOnly: true },
];

// Deliberately styled apart from the management routes above: this one leaves
// the admin area instead of navigating inside it.
const storeLinkStyle = sx`display:flex;align-items:center;gap:8px;padding:11px 14px;border-radius:10px;font-size:14px;font-weight:700;color:var(--admin-primary);background:var(--brand-soft);text-decoration:none`;

export default function AdminLayout() {
  const { admin, isSuperAdmin, signOut } = useAdminAuth();
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);

  const items = NAV.filter((item) => !item.superOnly || isSuperAdmin);

  // The admin area never loads StoreSettings, so without this the tab keeps
  // whatever title index.html shipped with.
  useEffect(() => {
    document.title = "لوحة إدارة المتجر";
  }, []);

  const linkStyle = ({ isActive }) =>
    sx`display:block;padding:11px 14px;border-radius:10px;font-size:14px;font-weight:${isActive ? 800 : 600};color:${isActive ? "var(--admin-sidebar-text)" : "var(--text-primary)"};background:${isActive ? "var(--admin-sidebar-background)" : "transparent"};text-decoration:none`;

  return (
    <div className="vs-public" style={sx`direction:rtl;min-height:100vh;background:var(--vs-surface-2);display:flex;flex-direction:column`}>
      {/* Admin gets the brand as two marks and nothing more: the logo beside the
          title, and a gold hairline under the header. The screens below stay
          plain white and warm grey, because they are read all day. */}
      <header style={sx`background:#fff;border-bottom:1px solid #E7DCF2;box-shadow:inset 0 -3px 0 -2px var(--brand-secondary);position:sticky;top:0;z-index:60`}>
        <div style={sx`max-width:1400px;margin:0 auto;padding:12px 20px;display:flex;align-items:center;gap:14px`}>
          <button type="button" onClick={() => setMenuOpen((open) => !open)} aria-label="القائمة" aria-expanded={menuOpen} style={sx`display:var(--mob);width:42px;height:42px;align-items:center;justify-content:center;border:1px solid #E7DCF2;border-radius:10px;background:#fff;cursor:pointer;font-size:18px`}>☰</button>
          <img src={LOGO_URL} alt={STORE_NAME_AR} style={sx`width:34px;height:34px;object-fit:contain;display:block;flex:0 0 auto`} />
          <strong style={sx`font-size:17px;color:var(--admin-primary)`}>لوحة إدارة المتجر</strong>
          <div style={sx`margin-inline-start:auto;display:flex;align-items:center;gap:12px`}>
            <span style={sx`display:var(--desk);font-size:13px;color:#766669`}>{admin?.full_name} · {isSuperAdmin ? "مدير أعلى" : "مدير"}</span>
            <Button variant="ghost" onClick={() => { signOut(); navigate("/admin/login", { replace: true }); }}>خروج</Button>
          </div>
        </div>
      </header>

      <div style={sx`max-width:1400px;width:100%;margin:0 auto;padding:20px;display:grid;grid-template-columns:var(--adminG);gap:20px;align-items:start;flex:1;box-sizing:border-box`}>
        <nav style={sx`background:#fff;border:1px solid #E7DCF2;border-radius:14px;padding:10px;display:${menuOpen ? "block" : "var(--adminNav)"};position:sticky;top:82px`}>
          {items.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.end} style={linkStyle} onClick={() => setMenuOpen(false)}>
              {item.label}
            </NavLink>
          ))}
          <div style={sx`margin:8px 4px;border-top:1px solid #E7DCF2`} />
          <a
            href="/"
            target="_blank"
            rel="noopener noreferrer"
            onClick={() => setMenuOpen(false)}
            style={storeLinkStyle}
          >
            <span aria-hidden="true">🛍</span>
            العودة إلى الموقع
          </a>
        </nav>
        <main style={sx`min-width:0`}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
