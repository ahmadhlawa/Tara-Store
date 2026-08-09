import { Route, Routes } from "react-router-dom";
import { StoreProvider } from "./app/StoreProvider.jsx";
import PublicShell from "./components/public/shell/PublicShell.jsx";
import HomePage from "./pages/HomePage.jsx";
import CatalogPage from "./pages/CatalogPage.jsx";
import ProductDetailPage from "./pages/ProductDetailPage.jsx";
import CartRoutePage from "./pages/CartRoutePage.jsx";
import CheckoutRoutePage from "./pages/CheckoutRoutePage.jsx";
import OrderSuccessRoutePage from "./pages/OrderSuccessRoutePage.jsx";
import { ArticleDetailPage, BlogListPage } from "./pages/BlogRoutePages.jsx";
import StaticContentPage from "./pages/StaticContentPage.jsx";
import ContactRoutePage from "./pages/ContactRoutePage.jsx";
import CalculatorRoutePage from "./pages/CalculatorRoutePage.jsx";
import NotFoundRoutePage from "./pages/NotFoundRoutePage.jsx";
import AdminApp from "./admin/AdminApp.jsx";

/**
 * Two independent areas share one SPA: the public storefront (with its own data
 * provider and chrome) and the admin workspace under /admin.
 */
export default function App() {
  return (
    <Routes>
      <Route path="/admin/*" element={<AdminApp />} />

      <Route
        element={
          <StoreProvider>
            <PublicShell />
          </StoreProvider>
        }
      >
        <Route index element={<HomePage />} />
        <Route path="shop" element={<CatalogPage mode="shop" />} />
        <Route path="category/:slug" element={<CatalogPage mode="category" />} />
        <Route path="offers" element={<CatalogPage mode="offers" />} />
        <Route path="packages" element={<CatalogPage mode="packages" />} />
        <Route path="molds" element={<CatalogPage mode="molds" />} />
        <Route path="search" element={<CatalogPage mode="search" />} />
        <Route path="product/:slug" element={<ProductDetailPage />} />
        <Route path="cart" element={<CartRoutePage />} />
        <Route path="checkout" element={<CheckoutRoutePage />} />
        <Route path="order-success/:orderNumber" element={<OrderSuccessRoutePage />} />
        <Route path="blog" element={<BlogListPage />} />
        <Route path="blog/:slug" element={<ArticleDetailPage />} />
        <Route path="page/:slug" element={<StaticContentPage />} />
        {/* Paths the original storefront used, kept working as direct links. */}
        <Route path="about" element={<StaticContentPage slug="about" />} />
        <Route path="privacy-policy" element={<StaticContentPage slug="privacy-policy" />} />
        <Route path="return-policy" element={<StaticContentPage slug="return-policy" />} />
        <Route path="terms" element={<StaticContentPage slug="terms" />} />
        <Route path="contact" element={<ContactRoutePage />} />
        <Route path="tools/calculator" element={<CalculatorRoutePage />} />
        <Route path="*" element={<NotFoundRoutePage />} />
      </Route>
    </Routes>
  );
}
