import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
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
  { to: "/admin/media", label: "الوسائط" },
  { to: "/admin/settings", label: "روابط المتجر" },
  { to: "/admin/store-colors", label: "ألوان المتجر" },
  { to: "/admin/admins", label: "حسابات الإدارة", superOnly: true },
  { to: "/admin/audit", label: "سجل التغييرات", superOnly: true },
];

// Deliberately styled apart from the management routes above: this one leaves
// the admin area instead of navigating inside it.
const storeLinkStyle = sx`display:flex;align-items:center;gap:8px;padding:11px 14px;border-radius:10px;font-size:14px;font-weight:700;color:var(--admin-primary);background:var(--admin-soft);text-decoration:none`;

export default function AdminLayout() {
  const { admin, isSuperAdmin, signOut } = useAdminAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);

  const items = NAV.filter((item) => !item.superOnly || isSuperAdmin);

  // The admin area never loads StoreSettings, so without this the tab keeps
  // whatever title index.html shipped with.
  useEffect(() => {
    document.title = "لوحة إدارة المتجر";
  }, []);

  useEffect(() => {
    setMenuOpen(false);
  }, [location.pathname, location.search]);

  useEffect(() => {
    if (!menuOpen) return undefined;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [menuOpen]);

  useEffect(() => {
    const mobile = window.matchMedia("(max-width: 900px)");
    const closeOnDesktop = () => {
      if (!mobile.matches) setMenuOpen(false);
    };
    mobile.addEventListener("change", closeOnDesktop);
    return () => mobile.removeEventListener("change", closeOnDesktop);
  }, []);

  const logout = () => {
    setMenuOpen(false);
    signOut();
    navigate("/admin/login", { replace: true });
  };

  const linkStyle = ({ isActive }) =>
    sx`display:block;padding:11px 14px;border-radius:10px;font-size:14px;font-weight:${isActive ? 800 : 600};color:${isActive ? "var(--admin-on-primary)" : "var(--admin-text)"};background:${isActive ? "var(--admin-primary)" : "transparent"};text-decoration:none`;

  return (
    <div style={sx`direction:rtl;min-height:100vh;background:var(--admin-page-background);display:flex;flex-direction:column`}>
      {/* Admin gets the brand as two marks and nothing more: the logo beside the
          title, and a gold hairline under the header. The screens below stay
          plain white and warm grey, because they are read all day. */}
      <header inert={menuOpen ? "" : undefined} style={sx`background:#fff;border-bottom:1px solid #E7DCF2;box-shadow:inset 0 -3px 0 -2px var(--admin-secondary);position:sticky;top:0;z-index:60`}>
        <div style={sx`max-width:1400px;margin:0 auto;padding:12px 20px;display:flex;align-items:center;gap:14px`}>
          <button type="button" onClick={() => setMenuOpen(true)} aria-label="فتح قائمة الإدارة" aria-expanded={menuOpen} aria-controls="admin-navigation" style={sx`display:var(--mob);width:44px;height:44px;min-width:44px;min-height:44px;flex:0 0 44px;align-items:center;justify-content:center;border:1px solid #E7DCF2;border-radius:10px;background:#fff;cursor:pointer;font-size:18px`}>☰</button>
          <img src={LOGO_URL} alt={STORE_NAME_AR} style={sx`width:34px;height:34px;object-fit:contain;display:block;flex:0 0 auto`} />
          <strong style={sx`font-size:17px;color:var(--admin-primary)`}>لوحة إدارة المتجر</strong>
          <div style={sx`margin-inline-start:auto;display:flex;align-items:center;gap:12px`}>
            <span style={sx`display:var(--desk);font-size:13px;color:#766669`}>{admin?.full_name} · {isSuperAdmin ? "مدير أعلى" : "مدير"}</span>
            <Button variant="ghost" onClick={logout}>خروج</Button>
          </div>
        </div>
      </header>

      {menuOpen && <button type="button" className="admin-nav-scrim" data-admin-nav-scrim aria-label="إغلاق القائمة بالنقر خارجها" onClick={() => setMenuOpen(false)} />}

      <div style={sx`max-width:1400px;width:100%;margin:0 auto;padding:20px;display:grid;grid-template-columns:var(--adminG);gap:20px;align-items:start;flex:1;box-sizing:border-box`}>
        <nav id="admin-navigation" className={`admin-nav${menuOpen ? " is-open" : ""}`} data-admin-nav-drawer data-mobile-open={menuOpen} aria-label="التنقل الإداري" style={sx`background:#fff;border:1px solid #E7DCF2;border-radius:14px;padding:10px`}>
          {menuOpen && (
            <div className="admin-nav__mobile-head">
              <strong>قائمة الإدارة</strong>
              <button type="button" aria-label="إغلاق قائمة الإدارة" onClick={() => setMenuOpen(false)}>×</button>
            </div>
          )}
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
          {menuOpen && <Button className="admin-nav__mobile-logout" variant="ghost" onClick={logout}>خروج</Button>}
        </nav>
        <main inert={menuOpen ? "" : undefined} style={sx`min-width:0`}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
