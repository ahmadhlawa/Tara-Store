import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { CategoryPicker } from "../admin/pages/ProductEditorPage.jsx";

const categories = [
  { id: 4, name: "Crochet", parent_id: null, sort_order: 1 },
  { id: 1, name: "Candles", parent_id: null, sort_order: 0 },
  { id: 2, name: "شموع الديكور", parent_id: 1, sort_order: 0 },
  { id: 3, name: "شموع المشروبات", parent_id: 2, sort_order: 0 },
];

describe("product category picker", () => {
  it("shows roots first and expands recursively without selecting from arrows", async () => {
    const onChange = vi.fn();
    render(<CategoryPicker categories={categories} value="" onChange={onChange} />);

    await userEvent.click(screen.getByRole("button", { name: "بدون قسم" }));
    const list = screen.getByRole("listbox", { name: "القسم" });
    expect(within(list).getByRole("option", { name: "Candles" })).toBeInTheDocument();
    expect(within(list).getByRole("option", { name: "Crochet" })).toBeInTheDocument();
    expect(within(list).getAllByRole("option").slice(1).map((option) => option.textContent)).toEqual(["Candles", "Crochet"]);
    expect(within(list).queryByRole("option", { name: "شموع الديكور" })).not.toBeInTheDocument();

    await userEvent.click(within(list).getByRole("button", { name: "توسيع Candles" }));
    expect(onChange).not.toHaveBeenCalled();
    expect(within(list).getByRole("option", { name: "شموع الديكور" })).toBeInTheDocument();
    await userEvent.click(within(list).getByRole("button", { name: "توسيع شموع الديكور" }));
    expect(within(list).getByRole("option", { name: "شموع المشروبات" })).toBeInTheDocument();

    await userEvent.click(within(list).getByRole("option", { name: "شموع المشروبات" }));
    expect(onChange).toHaveBeenCalledWith("3");
  });

  it("reveals and clearly marks the current nested category in edit mode", async () => {
    const { rerender } = render(<CategoryPicker categories={categories} value="3" onChange={vi.fn()} />);
    expect(screen.getByRole("button", { name: "شموع المشروبات" })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "شموع المشروبات" }));
    expect(await screen.findByRole("option", { name: "شموع المشروبات" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("button", { name: "طي Candles" })).toHaveAttribute("aria-expanded", "true");

    rerender(<CategoryPicker categories={categories} value="3" onChange={vi.fn()} />);
    expect(screen.getByRole("button", { name: "شموع المشروبات" })).toBeInTheDocument();
  });
});
