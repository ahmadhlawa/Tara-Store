import { describe, expect, it } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { renderApp, storefrontRoutes, stubApi } from "./utils.jsx";
import { buildStorefrontThemeVariables, contrastRatio } from "../theme/storefrontTheme.js";

describe("free shipping bar", () => {
  it.each([300, 375])("does not render the removed bar for delivery threshold %s", async (threshold) => {
    stubApi({ ...storefrontRoutes, "/api/v1/delivery-areas": [
      { id: 1, name: "منطقة الاختبار", delivery_fee: 25, free_delivery_threshold: threshold },
      { id: 2, name: "منطقة بلا حد", delivery_fee: 35, free_delivery_threshold: null },
      { id: 3, name: "مجاني دائماً", delivery_fee: 0, free_delivery_threshold: 0 },
    ] });
    renderApp("/");
    expect(await screen.findByRole("banner")).toBeInTheDocument();
    expect(screen.queryByLabelText("توصيل مجاني")).not.toBeInTheDocument();
    expect(document.querySelector(".vs-free-shipping-bar")).toBeNull();
  });

  it("renders nothing when no zone has a threshold", async () => {
    stubApi({ ...storefrontRoutes, "/api/v1/delivery-areas": [
      { id: 1, name: "منطقة بلا حد", delivery_fee: 25, free_delivery_threshold: null },
    ] });
    renderApp("/");
    await waitFor(() => expect(document.querySelector(".vs-inline-alert")).toBeNull());
    expect(screen.queryByLabelText("توصيل مجاني")).not.toBeInTheDocument();
  });

  it.each(["#9070b5", "#FFFFFF", "#000000"])("chooses readable text for %s", (background) => {
    const variables = buildStorefrontThemeVariables({ theme_announcement_background: background });
    expect(variables["--announcement-background"]).toBe(background);
    expect(contrastRatio(background, variables["--announcement-text"])).toBeGreaterThanOrEqual(4.5);
    expect(buildStorefrontThemeVariables()["--announcement-text"]).toBe(buildStorefrontThemeVariables({ theme_announcement_background: "#9070b5" })["--announcement-text"]);
  });
});
