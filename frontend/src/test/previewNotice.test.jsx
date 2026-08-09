import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import PreviewNotice, { previewNoticeText } from "../components/PreviewNotice.jsx";
import { renderApp, storefrontRoutes, stubApi } from "./utils.jsx";

const NOTICE = "نسخة تجريبية — البيانات والأسعار للمعاينة";

describe("preview notice", () => {
  it("renders the configured Arabic text", () => {
    render(<PreviewNotice text={NOTICE} />);
    expect(screen.getByTestId("preview-notice")).toHaveTextContent(NOTICE);
  });

  it("renders nothing when the variable is unset — the default", () => {
    const { container } = render(<PreviewNotice text={previewNoticeText({})} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing when the variable is blank", () => {
    const { container } = render(
      <PreviewNotice text={previewNoticeText({ VITE_PREVIEW_NOTICE: "   " })} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("reads the text from the environment", () => {
    expect(previewNoticeText({ VITE_PREVIEW_NOTICE: NOTICE })).toBe(NOTICE);
    expect(previewNoticeText({ VITE_PREVIEW_NOTICE: "" })).toBe("");
    expect(previewNoticeText(undefined)).toBe("");
  });

  it("is announced to assistive technology without interrupting", () => {
    render(<PreviewNotice text={NOTICE} />);
    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("is absent from the storefront when the build does not configure it", async () => {
    // The test build sets no VITE_PREVIEW_NOTICE, which is exactly the shipped default.
    stubApi(storefrontRoutes);
    renderApp("/");

    expect(await screen.findByRole("search")).toBeInTheDocument();
    expect(screen.queryByTestId("preview-notice")).toBeNull();
  });
});
