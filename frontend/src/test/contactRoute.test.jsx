import { describe, expect, it } from "vitest";
import { screen, within } from "@testing-library/react";
import { renderApp, storefrontRoutes, stubApi } from "./utils.jsx";

describe("contact route", () => {
  it("omits unconfigured methods", async () => {
    stubApi({ ...storefrontRoutes, "/api/v1/store/settings": { ...storefrontRoutes["/api/v1/store/settings"], whatsapp: "", instagram_url: "", instagram_visible: false } });
    renderApp("/contact");
    const heading = await screen.findByRole("heading", { name: "تواصل معنا", level: 1 });
    const page = within(heading.closest("section"));
    expect(page.queryByRole("link", { name: /تواصل عبر/ })).not.toBeInTheDocument();
    expect(page.getByText("ستظهر روابط التواصل هنا فور إضافتها من إعدادات المتجر.")).toBeInTheDocument();
  });

  it("offers direct contact without a message-composer form", async () => {
    stubApi({ ...storefrontRoutes, "/api/v1/store/settings": { ...storefrontRoutes["/api/v1/store/settings"], instagram_url: "https://instagram.com/tara", instagram_visible: true }, "/api/v1/pages/contact": { lead: "تواصل مباشر" } });
    renderApp("/contact");

    const contact = await screen.findByRole("heading", { name: "تواصل معنا", level: 1 });
    const page = contact.closest("section");
    expect(await within(page).findByText("تواصل مباشر")).toBeInTheDocument();
    expect(within(page).getByText("نسعى للرد على جميع الاستفسارات في أقرب وقت ممكن.")).toBeInTheDocument();
    expect(page).not.toHaveTextContent("كيف يمكننا مساعدتك؟");
    expect(page).not.toHaveTextContent("نحن بالقرب منك");
    expect(page).not.toHaveTextContent("←");
    const whatsapp = within(page).getByRole("link", { name: "تواصل عبر واتساب" });
    expect(whatsapp).toHaveAttribute("href", "https://wa.me/0590000000?text=");
    expect(whatsapp).toHaveAttribute("target", "_blank");
    expect(whatsapp).toHaveAttribute("rel", "noopener noreferrer");
    expect(whatsapp).toHaveTextContent("0590000000");
    expect(within(page).getByText("@tara")).toBeInTheDocument();
    expect(within(page).getByRole("link", { name: "تواصل عبر إنستغرام" })).toHaveAttribute("href", "https://instagram.com/tara");
    expect(page.querySelector("img[src='/branding/contact-note.png']")).toBeNull();
    expect(within(page).queryByLabelText("الاسم")).not.toBeInTheDocument();
    expect(within(page).queryByLabelText("رقم الهاتف")).not.toBeInTheDocument();
    expect(within(page).queryByLabelText("رسالتك")).not.toBeInTheDocument();
  });

});
