import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import Gallery from "../components/public/product/Gallery.jsx";
import Media from "../components/public/shell/Media.jsx";

const images = [
  { id: 1, url: "/portrait.jpg" },
  { id: 2, url: "/landscape.jpg" },
  { id: 3, url: "/square.jpg" },
];

describe("product gallery", () => {
  it("keeps one semantic contained image over a decorative backdrop", async () => {
    const { container } = render(<Gallery images={images} alt="Tara candle" />);
    const frame = container.querySelector(".vs-gallery__main");

    expect(screen.getByRole("img", { name: "Tara candle" })).toHaveAttribute("src", "/portrait.jpg");
    expect(frame.querySelector(".vs-media--foreground")).toBeInTheDocument();
    expect(frame.querySelector(".vs-media--backdrop")).toHaveAttribute("aria-hidden", "true");

    await userEvent.click(screen.getByRole("button", { name: /2/ }));

    expect(screen.getByRole("img", { name: "Tara candle" })).toHaveAttribute("src", "/landscape.jpg");
    expect(frame.querySelector(".vs-media--backdrop")).toHaveAttribute("src", "/landscape.jpg");
    expect(screen.getByRole("button", { name: /2/ })).toHaveAttribute("aria-pressed", "true");
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
