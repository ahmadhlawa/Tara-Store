import { describe, expect, it } from "vitest";
import { screen, within } from "@testing-library/react";
import { renderApp, storefrontRoutes, stubApi } from "./utils.jsx";

describe("contact route", () => {
  it("offers direct contact without a message-composer form", async () => {
    stubApi({ ...storefrontRoutes, "/api/v1/store/settings": { ...storefrontRoutes["/api/v1/store/settings"], instagram_url: "https://instagram.com/tara", instagram_visible: true }, "/api/v1/pages/contact": { lead: "تواصل مباشر" } });
    renderApp("/contact");

    const contact = await screen.findByRole("heading", { name: "تواصل معنا" });
    const page = contact.closest("section");
    const whatsapp = within(page).getByRole("link", { name: "تواصل عبر واتساب" });
    expect(whatsapp).toHaveAttribute("href", "https://wa.me/0590000000?text=");
    expect(within(page).getByRole("link", { name: "تواصل عبر إنستغرام" })).toHaveAttribute("href", "https://instagram.com/tara");
    const note = within(page).getByLabelText("رسالة ترحيبية");
    expect(note.querySelector("img")).toHaveAttribute("src", "/branding/contact-note.png");
    expect(within(page).queryByLabelText("الاسم")).not.toBeInTheDocument();
    expect(within(page).queryByLabelText("رقم الهاتف")).not.toBeInTheDocument();
    expect(within(page).queryByLabelText("رسالتك")).not.toBeInTheDocument();
  });

});
