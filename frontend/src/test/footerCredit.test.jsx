import { describe, expect, it } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { renderApp, storefrontRoutes, stubApi } from "./utils.jsx";

describe("TFN footer credit", () => {
  it("shows the TFN credit in the storefront footer", async () => {
    stubApi(storefrontRoutes);
    renderApp("/");

    const credit = await screen.findByText("Developed by TFN Technologies Team");
    expect(credit.closest(".vs-footer__credit")).not.toBeNull();
    expect(credit.previousElementSibling).toHaveAttribute("src", "/branding/tfn.png");
    expect(credit.previousElementSibling).toHaveAttribute("alt", "TFN Technologies Team");

  });

  it("does not show the TFN credit in the admin workspace", async () => {
    stubApi(storefrontRoutes);
    renderApp("/admin");
    await waitFor(() => expect(document.querySelector(".vs-public")).toBeNull());
    expect(screen.queryByText("Developed by TFN Technologies Team")).not.toBeInTheDocument();
  });
});
