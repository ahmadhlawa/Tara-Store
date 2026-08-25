import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import StoreColorsPage from "../admin/pages/StoreColorsPage.jsx";

const { getSettings, updateSettings } = vi.hoisted(() => ({ getSettings: vi.fn(), updateSettings: vi.fn() }));

vi.mock("../api/adminApi.js", () => ({
  adminApi: { getSettings, updateSettings },
}));

vi.mock("../theme/storefrontTheme.js", () => ({
  THEME_KEYS: ["theme_primary_color", "theme_secondary_color", "theme_soft_color", "theme_nav_strip_background", "theme_nav_strip_text", "theme_footer_background", "theme_footer_text", "theme_footer_muted_text", "theme_button_primary_background", "theme_button_primary_text"],
  staticThemeDefaults: () => ({ theme_primary_color: "#AE98CB", theme_secondary_color: "#D7CAE8", theme_soft_color: "#FAF9FC", theme_nav_strip_background: "#FFFFFF", theme_nav_strip_text: "#181818", theme_footer_background: "#F6F6F8", theme_footer_text: "#181818", theme_footer_muted_text: "#666666", theme_button_primary_background: "#AE98CB", theme_button_primary_text: "#FFFFFF" }),
  buildStorefrontThemeVariables: () => ({}),
  contrastRatio: (first, second) => first === second ? 1 : 7,
}));

describe("ألوان المتجر", () => {
  beforeEach(() => { getSettings.mockResolvedValue({}); updateSettings.mockResolvedValue({}); });

  it("warns for low contrast without disabling Save, while invalid HEX still blocks it", async () => {
    const user = userEvent.setup();
    render(<StoreColorsPage />);
    const save = await screen.findByRole("button", { name: "حفظ التغييرات" });

    const navText = screen.getAllByLabelText("نص شريط التنقل").find((input) => input.type === "text");
    fireEvent.change(navText, { target: { value: "#FFFFFF" } });
    expect(screen.getByRole("status")).toHaveTextContent("4.5:1");
    expect(save).toBeEnabled();

    fireEvent.change(navText, { target: { value: "#FFF" } });
    expect(save).toBeDisabled();
  });

  it("saves valid colors", async () => {
    const user = userEvent.setup();
    render(<StoreColorsPage />);
    await user.click(await screen.findByRole("button", { name: "حفظ التغييرات" }));
    await waitFor(() => expect(updateSettings).toHaveBeenCalled());
  });
});
