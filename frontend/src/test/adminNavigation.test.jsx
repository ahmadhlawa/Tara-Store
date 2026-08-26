import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AdminLayout from "../admin/AdminLayout.jsx";

const { signOut } = vi.hoisted(() => ({ signOut: vi.fn() }));

vi.mock("../admin/AdminAuth.jsx", () => ({
  useAdminAuth: () => ({
    admin: { id: 1, email: "owner@example.com", full_name: "Store Owner", role: "super_admin", is_active: true },
    isSuperAdmin: true,
    signOut,
  }),
}));

function renderLayout() {
  return render(
    <MemoryRouter initialEntries={["/admin"]}>
      <Routes>
        <Route path="/admin" element={<AdminLayout />}>
          <Route index element={<button type="button">محتوى لوحة التحكم</button>} />
          <Route path="products" element={<p>صفحة المنتجات</p>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

describe("Admin mobile navigation drawer", () => {
  beforeEach(() => {
    document.body.style.overflow = "scroll";
  });

  it("does not expose deleted content management routes", () => {
    renderLayout();

    for (const href of ["/admin/banners", "/admin/articles", "/admin/pages"]) {
      expect(document.querySelector(`a[href="${href}"]`)).toBeNull();
    }
  });

  it("opens above inert Admin content, locks body scroll, and keeps logout reachable", async () => {
    const user = userEvent.setup();
    renderLayout();

    await user.click(screen.getByRole("button", { name: "فتح قائمة الإدارة" }));

    const drawer = screen.getByRole("navigation", { name: "التنقل الإداري" });
    expect(drawer).toHaveAttribute("data-mobile-open", "true");
    expect(screen.getByRole("button", { name: "إغلاق القائمة بالنقر خارجها" })).toBeInTheDocument();
    expect(within(drawer).getByRole("button", { name: "خروج" })).toBeInTheDocument();
    expect(document.body.style.overflow).toBe("hidden");
    expect(screen.getByRole("main", { hidden: true })).toHaveAttribute("inert");
    expect(document.querySelector("header")).toHaveAttribute("inert");
  });

  it("closes from its internal control and restores the previous body overflow", async () => {
    const user = userEvent.setup();
    renderLayout();

    await user.click(screen.getByRole("button", { name: "فتح قائمة الإدارة" }));
    await user.click(screen.getByRole("button", { name: "إغلاق قائمة الإدارة" }));

    expect(screen.queryByRole("button", { name: "إغلاق القائمة بالنقر خارجها" })).not.toBeInTheDocument();
    expect(document.body.style.overflow).toBe("scroll");
    expect(screen.getByRole("main")).not.toHaveAttribute("inert");
  });

  it("closes when the scrim is clicked", async () => {
    const user = userEvent.setup();
    renderLayout();

    await user.click(screen.getByRole("button", { name: "فتح قائمة الإدارة" }));
    await user.click(screen.getByRole("button", { name: "إغلاق القائمة بالنقر خارجها" }));

    expect(document.body.style.overflow).toBe("scroll");
    expect(screen.getByRole("navigation", { name: "التنقل الإداري" })).toHaveAttribute("data-mobile-open", "false");
  });

  it("closes after route navigation", async () => {
    const user = userEvent.setup();
    renderLayout();

    await user.click(screen.getByRole("button", { name: "فتح قائمة الإدارة" }));
    await user.click(screen.getByRole("link", { name: "المنتجات" }));

    expect(await screen.findByText("صفحة المنتجات")).toBeInTheDocument();
    expect(document.body.style.overflow).toBe("scroll");
    expect(screen.getByRole("navigation", { name: "التنقل الإداري" })).toHaveAttribute("data-mobile-open", "false");
  });

  it("restores body overflow when the layout unmounts while open", async () => {
    const user = userEvent.setup();
    const view = renderLayout();

    await user.click(screen.getByRole("button", { name: "فتح قائمة الإدارة" }));
    view.unmount();

    expect(document.body.style.overflow).toBe("scroll");
  });
});
