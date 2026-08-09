import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import { categoryFixture, renderApp, storefrontRoutes, stubApi } from "./utils.jsx";

/**
 * Desktop hover intent on the category rail. Everything here is timing, so the
 * clock is fake and every assertion sits on one side of a known delay.
 */

const OPEN_DELAY = 120;
const CLOSE_DELAY = 260;

const parentCategory = {
  ...categoryFixture,
  id: 7,
  name: "مطبوعات المناسبات",
  slug: "event-print",
  children: [{ id: 8, name: "بنرات", slug: "banners", product_count: 4 }],
};

const rail = () => document.querySelector(".vs-catbar");
const drawer = () => screen.queryByRole("dialog", { name: "تصنيفات المنتجات" });

// React synthesises enter/leave from the delegated over/out events, so the test
// has to speak the same language the browser does — including where the pointer
// came from, which is the whole point of the rail-to-drawer case.
const enter = (node, from = document.body) =>
  fireEvent.pointerOver(node, { pointerType: "mouse", relatedTarget: from });
const leave = (node, to = document.body) =>
  fireEvent.pointerOut(node, { pointerType: "mouse", relatedTarget: to });

/** Timers move state, so the clock runs inside act. */
const tick = (ms) =>
  act(() => {
    vi.advanceTimersByTime(ms);
  });

async function mountStorefront({ hover = true } = {}) {
  window.__mediaMatches = (query) => hover && query.includes("hover: hover");
  stubApi({ ...storefrontRoutes, "/api/v1/categories": [categoryFixture, parentCategory] });
  renderApp("/");
  await waitFor(() => expect(rail()).not.toBeNull());
  await waitFor(() => expect(rail().querySelectorAll(".vs-catbar__item")).toHaveLength(2));
}

describe("category rail hover intent", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("opens the drawer only once the pointer has stayed on the rail", async () => {
    await mountStorefront();

    enter(rail());
    tick(OPEN_DELAY - 20);
    expect(drawer()).toBeNull();

    tick(40);
    await waitFor(() => expect(drawer()).not.toBeNull());
    expect(rail().querySelector(".vs-catbar__trigger")).toHaveAttribute("aria-expanded", "true");
  });

  it("does not take focus when the pointer opened it", async () => {
    await mountStorefront();

    enter(rail());
    tick(OPEN_DELAY);
    await waitFor(() => expect(drawer()).not.toBeNull());

    expect(drawer().contains(document.activeElement)).toBe(false);
  });

  it("stays open when the pointer moves from the rail into the drawer", async () => {
    await mountStorefront();

    enter(rail());
    tick(OPEN_DELAY);
    await waitFor(() => expect(drawer()).not.toBeNull());

    const panel = drawer();
    leave(rail(), panel);
    enter(panel, rail());
    tick(CLOSE_DELAY + 100);

    expect(drawer()).not.toBeNull();
  });

  it("closes after the delay once the pointer has left both, and re-entering cancels it", async () => {
    await mountStorefront();

    enter(rail());
    tick(OPEN_DELAY);
    await waitFor(() => expect(drawer()).not.toBeNull());

    // Left both surfaces, but not for long enough yet.
    leave(drawer());
    tick(CLOSE_DELAY - 60);
    expect(drawer()).not.toBeNull();

    // Coming back cancels the pending close outright.
    enter(rail());
    tick(CLOSE_DELAY + 100);
    expect(drawer()).not.toBeNull();

    leave(rail());
    tick(CLOSE_DELAY - 60);
    expect(drawer()).not.toBeNull();
    tick(120);
    await waitFor(() => expect(drawer()).toBeNull());
  });

  it("moving between rail items neither reopens nor resets anything", async () => {
    await mountStorefront();

    // Travelling down the icons while the open is still pending: React fires
    // neither enter nor leave on the rail itself, so the timer it started is
    // neither cancelled nor restarted and the drawer opens on the original
    // schedule. (Once open there are no rail items left to move between — the
    // panel has taken the list over.)
    enter(rail());
    tick(OPEN_DELAY - 60);

    const [first, second] = rail().querySelectorAll(".vs-catbar__item");
    leave(first, second);
    enter(second, first);
    expect(drawer()).toBeNull();

    tick(60);
    await waitFor(() => expect(drawer()).not.toBeNull());
  });

  it("keeps the click toggle and Escape working", async () => {
    await mountStorefront();

    const trigger = rail().querySelector(".vs-catbar__trigger");
    fireEvent.click(trigger);
    await waitFor(() => expect(drawer()).not.toBeNull());
    // An explicit open does move focus into the panel.
    expect(drawer().contains(document.activeElement)).toBe(true);

    fireEvent.click(trigger);
    await waitFor(() => expect(drawer()).toBeNull());

    fireEvent.click(trigger);
    await waitFor(() => expect(drawer()).not.toBeNull());
    fireEvent.keyDown(drawer(), { key: "Escape" });
    await waitFor(() => expect(drawer()).toBeNull());
  });

  it("never opens on hover where the pointer is coarse", async () => {
    await mountStorefront({ hover: false });

    enter(rail());
    tick(OPEN_DELAY + 500);
    expect(drawer()).toBeNull();

    // The tap path is untouched.
    fireEvent.click(rail().querySelector(".vs-catbar__trigger"));
    await waitFor(() => expect(drawer()).not.toBeNull());
  });

  it("renders no rail and reserves no gutter in the admin workspace", async () => {
    window.__mediaMatches = (query) => query.includes("hover: hover");
    stubApi(storefrontRoutes);
    renderApp("/admin");
    await waitFor(() => expect(document.querySelector(".vs-public")).toBeNull());
    expect(rail()).toBeNull();
  });
});
