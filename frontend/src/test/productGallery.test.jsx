import { act, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import Gallery from "../components/public/product/Gallery.jsx";
import Media from "../components/public/shell/Media.jsx";

const images = [
  { id: 1, url: "/portrait.jpg" },
  { id: 2, url: "/landscape.jpg" },
  { id: 3, url: "/square.jpg" },
];

describe("product gallery", () => {
  afterEach(() => vi.useRealTimers());

  it("renders one semantic image and switches it without a decorative backdrop", async () => {
    const { container } = render(<Gallery images={images} alt="Tara candle" />);
    const frame = container.querySelector(".vs-gallery__main");

    expect(screen.getByRole("img", { name: "Tara candle" })).toHaveAttribute("src", "/portrait.jpg");
    expect(frame.querySelectorAll("img")).toHaveLength(1);
    expect(frame.querySelector(".vs-media--backdrop")).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /2/ }));

    expect(screen.getByRole("img", { name: "Tara candle" })).toHaveAttribute("src", "/landscape.jpg");
    expect(screen.getByRole("button", { name: /2/ })).toHaveAttribute("aria-pressed", "true");
  });

  it("autoplays, loops, and restarts the timer after manual selection", () => {
    vi.useFakeTimers();
    render(<Gallery images={images} alt="Tara candle" />);

    act(() => vi.advanceTimersByTime(3000));
    expect(screen.getByRole("img", { name: "Tara candle" })).toHaveAttribute("src", "/landscape.jpg");

    fireEvent.click(screen.getByRole("button", { name: /3/ }));
    act(() => vi.advanceTimersByTime(2999));
    expect(screen.getByRole("img", { name: "Tara candle" })).toHaveAttribute("src", "/square.jpg");
    act(() => vi.advanceTimersByTime(1));
    expect(screen.getByRole("img", { name: "Tara candle" })).toHaveAttribute("src", "/portrait.jpg");
  });

  it("wraps arrow navigation and omits it for a single image", () => {
    const { rerender } = render(<Gallery images={images} alt="Tara candle" />);
    fireEvent.click(screen.getByRole("button", { name: "الصورة السابقة" }));
    expect(screen.getByRole("img", { name: "Tara candle" })).toHaveAttribute("src", "/square.jpg");
    fireEvent.click(screen.getByRole("button", { name: "الصورة التالية" }));
    expect(screen.getByRole("img", { name: "Tara candle" })).toHaveAttribute("src", "/portrait.jpg");
    rerender(<Gallery images={images.slice(0, 1)} alt="Tara candle" />);
    expect(screen.queryByRole("button", { name: "الصورة السابقة" })).not.toBeInTheDocument();
  });

  it("uses the identical source for Quick View foreground and backdrop", () => {
    const { container } = render(
      <Media className="vs-quick__media" src="/quick-view.jpg" alt="Pink Sugar" eager backdrop />,
    );

    const layers = container.querySelectorAll(".vs-quick__media img");
    expect(layers).toHaveLength(2);
    expect(layers[0]).toHaveAttribute("src", "/quick-view.jpg");
    expect(layers[1]).toHaveAttribute("src", "/quick-view.jpg");
    expect(layers[0]).toHaveAttribute("aria-hidden", "true");
    expect(layers[1]).toHaveAccessibleName("Pink Sugar");
  });
});
