import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import ProductDetailPage from "../admin/pages/ProductDetailPage.jsx";
import ProductEditorPage from "../admin/pages/ProductEditorPage.jsx";
import { page, productFixture, stubApi } from "./utils.jsx";

function Location() {
  return <output data-testid="location">{useLocation().pathname}</output>;
}

function ProductRoutes({ initialEntry }) {
  return <MemoryRouter initialEntries={[initialEntry]}><Routes>
    <Route path="/admin/products" element={<><span>product-list</span><Location /></>} />
    <Route path="/admin/products/new" element={<><ProductEditorPage mode="create" /><Location /></>} />
    <Route path="/admin/products/:productId" element={<><ProductDetailPage /><Location /></>} />
    <Route path="/admin/products/:productId/edit" element={<><ProductEditorPage mode="edit" /><Location /></>} />
  </Routes></MemoryRouter>;
}

const apiRoutes = {
  "/api/v1/admin/categories": page([]),
  "/api/v1/admin/products/7": { ...productFixture, id: 7 },
  "/api/v1/admin/products": page([]),
};

describe("admin product routes", () => {
  it("matches the static create route, initializes it without a detail request, and goes back to the list", async () => {
    const calls = stubApi(apiRoutes);
    render(<ProductRoutes initialEntry="/admin/products/new" />);

    expect(await screen.findByRole("heading", { name: "منتج جديد" })).toBeInTheDocument();
    expect(calls.some(({ path }) => /\/products\/(?:undefined|null|new)(?:$|\?)/.test(path))).toBe(false);
    await userEvent.click(screen.getByRole("button", { name: "رجوع" }));
    expect(screen.getByText("product-list")).toBeInTheDocument();
  });

  it("passes the real id to summary and generates the edit URL", async () => {
    const calls = stubApi(apiRoutes);
    render(<ProductRoutes initialEntry="/admin/products/7" />);

    await screen.findByRole("heading", { name: productFixture.name, level: 1 });
    expect(calls.filter(({ path }) => path === "/api/v1/admin/products/7")).toHaveLength(1);
    await userEvent.click(screen.getByRole("button", { name: "تعديل المنتج" }));
    expect(screen.getByTestId("location")).toHaveTextContent("/admin/products/7/edit");
  });

  it("loads edit with the real id once and uses deterministic Back", async () => {
    const calls = stubApi(apiRoutes);
    render(<ProductRoutes initialEntry="/admin/products/7/edit" />);

    expect(await screen.findByText("المعرّف: 7")).toBeInTheDocument();
    expect(calls.filter(({ path }) => path === "/api/v1/admin/products/7")).toHaveLength(1);
    await userEvent.click(screen.getByRole("button", { name: "رجوع" }));
    expect(screen.getByTestId("location")).toHaveTextContent("/admin/products/7");
  });

  it("rejects an invalid id without making a product-detail request or staying loading", async () => {
    const calls = stubApi({});
    render(<ProductRoutes initialEntry="/admin/products/not-a-real-id" />);

    expect(screen.getByRole("heading", { name: "المنتج غير موجود" })).toBeInTheDocument();
    expect(screen.queryByText(/جار.*التحميل/)).not.toBeInTheDocument();
    await waitFor(() => expect(calls).toHaveLength(0));
  });

  it.each(["/admin/products", "/admin/products/new", "/admin/products/7", "/admin/products/7/edit"])("initializes %s directly", async (route) => {
    stubApi(apiRoutes);
    render(<ProductRoutes initialEntry={route} />);
    await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent(route));
  });
});
