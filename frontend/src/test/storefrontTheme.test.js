import { describe, expect, it } from "vitest";
import { buildStorefrontThemeVariables } from "../theme/storefrontTheme.js";

describe("buildStorefrontThemeVariables", () => {
  it("maps non-null persisted overrides and derives announcement text contrast", () => {
    expect(buildStorefrontThemeVariables({
      theme_primary_color: "#FF0000",
      theme_nav_strip_background: "#00FF00",
      theme_footer_background: "#0000FF",
      theme_button_primary_background: null,
    })).toEqual({
      "--brand-primary": "#FF0000",
      "--brand-primary-hover": "color-mix(in srgb, #FF0000 82%, #000)",
      "--nav-strip-background": "#00FF00",
      "--footer-background": "#0000FF",
      "--announcement-text": "#000000",
    });
  });
});
