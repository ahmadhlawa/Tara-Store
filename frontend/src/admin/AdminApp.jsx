import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AdminAuthProvider, useAdminAuth } from "./AdminAuth.jsx";
import AdminLayout from "./AdminLayout.jsx";
import LoginPage from "./pages/LoginPage.jsx";
import DashboardPage from "./pages/DashboardPage.jsx";
import ProductsPage from "./pages/ProductsPage.jsx";
import ProductEditorPage from "./pages/ProductEditorPage.jsx";
import { CategoriesPage } from "./pages/CatalogScreens.jsx";
import { CouponsPage, DeliveryAreasPage } from "./pages/CommerceScreens.jsx";
import { HeroSlidesPage } from "./pages/ContentScreens.jsx";
import { OrderDetailPage, OrdersPage } from "./pages/OrdersPages.jsx";
import ManualOrderPage from "./pages/ManualOrderPage.jsx";
import { InvoiceDetailPage, InvoicesPage } from "./pages/InvoicesPages.jsx";
import MediaPage from "./pages/MediaPage.jsx";
import SettingsPage from "./pages/SettingsPage.jsx";
import StoreColorsPage from "./pages/StoreColorsPage.jsx";
import { AdminsPage, AuditLogPage } from "./pages/AccountScreens.jsx";
import { Spinner } from "./ui.jsx";
import sx from "../sx.js";

function RequireAdmin({ children }) {
  const { isAuthenticated, restoring } = useAdminAuth();
  const location = useLocation();

  if (restoring) {
    return (
      <div style={sx`direction:rtl;min-height:100vh;display:flex;align-items:center;justify-content:center;background:#FAF3EA`}>
        <Spinner label="جارٍ استعادة الجلسة…" />
      </div>
    );
  }
  if (!isAuthenticated) {
    return <Navigate to="/admin/login" replace state={{ from: location.pathname }} />;
  }
  return children;
}

function RequireSuperAdmin({ children }) {
  const { isSuperAdmin } = useAdminAuth();
  return isSuperAdmin ? children : <Navigate to="/admin" replace />;
}

export default function AdminApp() {
  return (
    <div className="admin-app">
      <AdminAuthProvider>
        <Routes>
        <Route path="login" element={<LoginPage />} />
        <Route
          element={
            <RequireAdmin>
              <AdminLayout />
            </RequireAdmin>
          }
        >
          <Route index element={<DashboardPage />} />
          <Route path="products" element={<ProductsPage />} />
          <Route path="products/:productId" element={<ProductEditorPage />} />
          <Route path="categories" element={<CategoriesPage />} />
          <Route path="orders" element={<OrdersPage />} />
          <Route path="orders/manual" element={<RequireSuperAdmin><ManualOrderPage /></RequireSuperAdmin>} />
          <Route path="orders/:orderId" element={<OrderDetailPage />} />
          <Route path="invoices" element={<InvoicesPage />} />
          <Route path="invoices/:invoiceNumber" element={<InvoiceDetailPage />} />
          <Route path="coupons" element={<CouponsPage />} />
          <Route path="delivery" element={<DeliveryAreasPage />} />
          <Route path="hero" element={<HeroSlidesPage />} />
          <Route path="media" element={<MediaPage />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="store-colors" element={<StoreColorsPage />} />
          <Route
            path="admins"
            element={
              <RequireSuperAdmin>
                <AdminsPage />
              </RequireSuperAdmin>
            }
          />
          <Route
            path="audit"
            element={
              <RequireSuperAdmin>
                <AuditLogPage />
              </RequireSuperAdmin>
            }
          />
          <Route path="*" element={<Navigate to="/admin" replace />} />
        </Route>
        </Routes>
      </AdminAuthProvider>
    </div>
  );
}
