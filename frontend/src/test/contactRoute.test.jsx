import { describe, expect, it } from "vitest";
import { screen, within } from "@testing-library/react";
import { renderApp, storefrontRoutes, stubApi } from "./utils.jsx";

describe("contact route", () => {
  it("offers direct contact without a message-composer form", async () => {
    stubApi({ ...storefrontRoutes, "/api/v1/pages/contact": { lead: "تواصل مباشر" } });
    renderApp("/contact");

    const contact = await screen.findByRole("heading", { name: "تواصل معنا" });
    const page = contact.closest("section");
    const whatsapp = within(page).getByRole("link", { name: "تواصل عبر واتساب" });
    expect(whatsapp).toHaveAttribute("href", "https://wa.me/0590000000?text=");
    expect(within(page).queryByLabelText("الاسم")).not.toBeInTheDocument();
    expect(within(page).queryByLabelText("رقم الهاتف")).not.toBeInTheDocument();
    expect(within(page).queryByLabelText("رسالتك")).not.toBeInTheDocument();
  });

  it("renders an embedded map only while a usable location is configured", async () => {
    const mapUrl = "https://www.openstreetmap.org/export/embed.html?bbox=35.20%2C31.76%2C35.22%2C31.78&layer=mapnik";
    stubApi({ ...storefrontRoutes, "/api/v1/store/settings": { ...storefrontRoutes["/api/v1/store/settings"], location_url: mapUrl } });
    renderApp("/contact");
    expect(await screen.findByTitle("خريطة الموقع المهيأ")).toHaveAttribute("src", mapUrl);
  });

  it("hides the map after a location is cleared and restores it after a valid update", async () => {
    stubApi({ ...storefrontRoutes, "/api/v1/store/settings": { ...storefrontRoutes["/api/v1/store/settings"], location_url: "" } });
    renderApp("/contact");
    await screen.findByRole("heading", { name: "تواصل معنا" });
    expect(screen.queryByTitle("خريطة الموقع المهيأ")).not.toBeInTheDocument();
  });
});
