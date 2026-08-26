import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { renderApp, respond, settingsFixture, storefrontRoutes, stubApi } from "./utils.jsx";

const maintenanceRoutes = {
  ...storefrontRoutes,
  "/api/v1/store/settings": { ...settingsFixture, maintenance_mode: true },
  // With maintenance mode on the backend closes the shopping surface too. The screen
  // must render from store identity alone, without any of these.
  "/api/v1/categories": respond(503, {
    error: { code: "maintenance_mode", message: "المتجر في وضع الصيانة حالياً." },
  }),
  "/api/v1/products": respond(503, {
    error: { code: "maintenance_mode", message: "المتجر في وضع الصيانة حالياً." },
  }),
};

describe("maintenance mode", () => {
  it("leaves the storefront untouched while it is off", async () => {
    stubApi(storefrontRoutes);
    renderApp("/");

    expect(await screen.findByRole("search")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "المتجر في وضع الصيانة" })).toBeNull();
  });

  it("replaces the storefront with an Arabic RTL maintenance screen when it is on", async () => {
    stubApi(maintenanceRoutes);
    const { container } = renderApp("/");

    const heading = await screen.findByRole("heading", { name: "المتجر في وضع الصيانة" });
    expect(heading).toBeInTheDocument();
    expect(container.querySelector('[dir="rtl"]')).not.toBeNull();

    // The storefront chrome and its pages are gone, not merely hidden.
    expect(screen.queryByRole("search")).toBeNull();
    expect(screen.queryByRole("contentinfo")).toBeNull();
  });

  it("shows store identity and safe contact information", async () => {
    stubApi(maintenanceRoutes);
    renderApp("/");

    expect(await screen.findByText(settingsFixture.store_name)).toBeInTheDocument();
    expect(screen.getByText(settingsFixture.store_tagline)).toBeInTheDocument();
    expect(screen.getAllByText(settingsFixture.whatsapp).length).toBeGreaterThan(0);
  });

  it("covers every public route without redirecting away from it", async () => {
    for (const path of ["/", "/shop", "/cart", "/checkout", "/no-such-page"]) {
      stubApi(maintenanceRoutes);
      const view = renderApp(path);
      expect(await screen.findByRole("heading", { name: "المتجر في وضع الصيانة" })).toBeInTheDocument();
      view.unmount();
    }
  });

  it("keeps admin login reachable", async () => {
    stubApi(maintenanceRoutes);
    renderApp("/admin/login");

    expect(await screen.findByRole("heading", { name: "تسجيل دخول الإدارة" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "المتجر في وضع الصيانة" })).toBeNull();
  });
});
