import { act, render, renderHook, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import AddToCartButton, { ADDED_LABEL, SUCCESS_MS } from "../components/AddToCartButton.jsx";
import { useCartCountPulse } from "../hooks/useCartCountPulse.js";
import { cartStorage } from "../storage/cartStorage.js";
import { productFixture, renderApp, storefrontRoutes, stubApi } from "./utils.jsx";

const PRODUCT_LABEL = "أضف إلى العربة";
const PACKAGE_LABEL = "أضف البكج إلى العربة";

describe("AddToCartButton", () => {
  // `shouldAdvanceTime` keeps user-event's internal delays running while the
  // component's success timeout stays under the test's control.
  beforeEach(() => vi.useFakeTimers({ shouldAdvanceTime: true }));
  afterEach(() => vi.useRealTimers());

  const setup = (props = {}) => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    const onAdd = vi.fn();
    render(<AddToCartButton onAdd={onAdd} label={PRODUCT_LABEL} icon="+" {...props} />);
    return { user, onAdd, button: () => screen.getByRole("button") };
  };

  it("calls the cart action exactly once per click", async () => {
    const { user, onAdd, button } = setup();

    await user.click(button());

    expect(onAdd).toHaveBeenCalledTimes(1);
  });

  it("shows the success label after a click and restores the original one", async () => {
    const { user, button } = setup();

    await user.click(button());
    expect(button()).toHaveTextContent(ADDED_LABEL);

    act(() => vi.advanceTimersByTime(SUCCESS_MS));
    expect(button()).toHaveTextContent(PRODUCT_LABEL);
    expect(button()).not.toHaveTextContent(ADDED_LABEL);
  });

  it("restores the package label on the package card", async () => {
    const { user, button } = setup({ label: PACKAGE_LABEL, icon: undefined });

    await user.click(button());
    expect(button()).toHaveTextContent(ADDED_LABEL);

    act(() => vi.advanceTimersByTime(SUCCESS_MS));
    expect(button()).toHaveTextContent(PACKAGE_LABEL);
  });

  it("ignores a second click while the success state is showing", async () => {
    const { user, onAdd, button } = setup();

    await user.click(button());
    await user.click(button());
    await user.click(button());
    expect(onAdd).toHaveBeenCalledTimes(1);

    // Once the window closes the button works again.
    act(() => vi.advanceTimersByTime(SUCCESS_MS));
    await user.click(button());
    expect(onAdd).toHaveBeenCalledTimes(2);
  });

  it("still adds through the keyboard", async () => {
    const { user, onAdd, button } = setup();

    await user.tab();
    expect(button()).toHaveFocus();
    await user.keyboard("{Enter}");

    expect(onAdd).toHaveBeenCalledTimes(1);
    expect(button()).toHaveTextContent(ADDED_LABEL);
  });

  it("never fires while sold out", async () => {
    const { user, onAdd, button } = setup({ disabled: true, label: "غير متوفر" });

    await user.click(button());

    expect(button()).toBeDisabled();
    expect(onAdd).not.toHaveBeenCalled();
  });
});

describe("useCartCountPulse", () => {
  it("pulses on a quantity increase only", () => {
    const { result, rerender } = renderHook(({ count }) => useCartCountPulse(count), {
      initialProps: { count: 2 },
    });

    expect(result.current).toBe(0); // a restored cart must not pulse on load

    rerender({ count: 2 });
    expect(result.current).toBe(0); // unrelated re-renders stay quiet

    rerender({ count: 3 });
    expect(result.current).toBe(1);

    rerender({ count: 1 });
    expect(result.current).toBe(1); // removing a line does not pulse
  });
});

describe("cart badge", () => {
  const badgeOf = () => {
    const button = screen.getByRole("button", { name: "عربة التسوّق" });
    return button.querySelector("span:last-of-type");
  };

  it("pulses when a card adds a product", async () => {
    stubApi(storefrontRoutes);
    renderApp("/shop");

    const card = (await screen.findAllByText(productFixture.name))[0].closest("div");
    expect(badgeOf()).toHaveStyle({ animation: "none" });

    await userEvent.click(
      within(card.parentElement).getByRole("button", { name: new RegExp(PRODUCT_LABEL) }),
    );

    await waitFor(() => expect(badgeOf()).toHaveTextContent("1"));
    expect(badgeOf().style.animation).toContain("pulse");
    expect(cartStorage.load()).toHaveLength(1);
  });
});
