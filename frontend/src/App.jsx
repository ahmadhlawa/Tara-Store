import { lazy, Suspense } from "react";
import { Route, Routes } from "react-router-dom";
import { StoreProvider } from "./app/StoreProvider.jsx";
import PublicShell from "./components/public/shell/PublicShell.jsx";
import HomePage from "./pages/HomePage.jsx";

const AdminApp = lazy(() => import("./admin/AdminApp.jsx"));
const CatalogPage = lazy(() => import("./pages/CatalogPage.jsx"));
const ProductDetailPage = lazy(() => import("./pages/ProductDetailPage.jsx"));
const CartRoutePage = lazy(() => import("./pages/CartRoutePage.jsx"));
const CheckoutRoutePage = lazy(() => import("./pages/CheckoutRoutePage.jsx"));
const OrderSuccessRoutePage = lazy(() => import("./pages/OrderSuccessRoutePage.jsx"));
const StaticContentPage = lazy(() => import("./pages/StaticContentPage.jsx"));
const ContactRoutePage = lazy(() => import("./pages/ContactRoutePage.jsx"));
const NotFoundRoutePage = lazy(() => import("./pages/NotFoundRoutePage.jsx"));

const routeFallback = <div role="status" aria-label="Loading" />;
const lazyRoute = (Component, props) => (
  <Suspense fallback={routeFallback}>
    <Component {...props} />
  </Suspense>
);

/**
 * Two independent areas share one SPA: the public storefront (with its own data
 * provider and chrome) and the admin workspace under /admin.
 */
export default function App() {
  return (
    <Routes>
        <Route path="/admin/*" element={lazyRoute(AdminApp)} />

        <Route
          element={
            <StoreProvider>
              <PublicShell />
            </StoreProvider>
          }
        >
          <Route index element={<HomePage />} />
          <Route path="shop" element={lazyRoute(CatalogPage, { mode: "shop" })} />
          <Route path="category/:slug" element={lazyRoute(CatalogPage, { mode: "category" })} />
          <Route path="offers" element={lazyRoute(CatalogPage, { mode: "offers" })} />
          <Route path="packages" element={lazyRoute(CatalogPage, { mode: "packages" })} />
          <Route path="molds" element={lazyRoute(CatalogPage, { mode: "molds" })} />
          <Route path="search" element={lazyRoute(CatalogPage, { mode: "search" })} />
          <Route path="product/:slug" element={lazyRoute(ProductDetailPage)} />
          <Route path="cart" element={lazyRoute(CartRoutePage)} />
          <Route path="checkout" element={lazyRoute(CheckoutRoutePage)} />
          <Route path="order-success/:orderNumber" element={lazyRoute(OrderSuccessRoutePage)} />
          <Route path="page/:slug" element={lazyRoute(StaticContentPage)} />
          {/* Paths the original storefront used, kept working as direct links. */}
          <Route path="about" element={lazyRoute(StaticContentPage, { slug: "about" })} />
          <Route path="privacy-policy" element={lazyRoute(StaticContentPage, { slug: "privacy-policy" })} />
          <Route path="return-policy" element={lazyRoute(StaticContentPage, { slug: "return-policy" })} />
          <Route path="terms" element={lazyRoute(StaticContentPage, { slug: "terms" })} />
          <Route path="contact" element={lazyRoute(ContactRoutePage)} />
          <Route path="*" element={lazyRoute(NotFoundRoutePage)} />
        </Route>
    </Routes>
  );
}
