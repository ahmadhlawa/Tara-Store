import { describe, expect, it } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  categoryFixture,
  renderApp,
  settingsFixture,
  storefrontRoutes,
  stubApi,
} from "./utils.jsx";

/** A root category with children, so the drawer's nesting has something to expand. */
const parentCategory = {
  ...categoryFixture,
  id: 7,
  name: "مطبوعات المناسبات",
  slug: "event-print",
  children: [
    { id: 8, name: "بنرات", slug: "banners", product_count: 4 },
    { id: 9, name: "ستاندات", slug: "stands", product_count: 2 },
  ],
};

const heroSlides = [
  {
    id: 1,
    title: "إعلان الأول",
    subtitle: "",
    description: "",
    button_label: "",
    button_url: "/shop",
    image_url: "/media/preview/one.png",
    sort_order: 0,
  },
  {
    id: 2,
    title: "إعلان الثاني",
    subtitle: "",
    description: "",
    button_label: "",
    button_url: "/shop",
    image_url: "/media/preview/two.png",
    sort_order: 1,
  },
];

/** A banner in every hero-side placement the old layout used to render. */
const banners = [
  { id: 1, placement: "home_main", title: "بانر رئيسي", subtitle: "", link_url: "/shop", image_url: null, sort_order: 0 },
  { id: 2, placement: "home_side", title: "بانر جانبي", subtitle: "", link_url: "/shop", image_url: null, sort_order: 1 },
];

const rail = () => document.querySelector(".vs-catbar");
const drawer = () => screen.queryByRole("dialog", { name: "تصنيفات المنتجات" });

describe("category rail", () => {
  it("renders one rail item per active category, straight from the API", async () => {
    stubApi({ ...storefrontRoutes, "/api/v1/categories": [categoryFixture, parentCategory] });
    renderApp("/");

    await waitFor(() => expect(rail().querySelectorAll(".vs-catbar__item")).toHaveLength(2));

    const items = within(rail()).getAllByRole("link");
    expect(items[0]).toHaveAttribute("href", `/category/${categoryFixture.slug}`);
    expect(items[1]).toHaveAttribute("href", "/category/event-print");
    // Every item is labelled and carries a tooltip; none shows permanent text.
    items.forEach((item) => {
      expect(item).toHaveAccessibleName();
      expect(item).toHaveAttribute("title");
    });
    expect(rail()).toHaveAccessibleName();
  });

  it("marks the category of the current route as active", async () => {
    stubApi({ ...storefrontRoutes, "/api/v1/categories": [categoryFixture, parentCategory] });
    renderApp("/category/event-print");

    await waitFor(() => expect(rail().querySelectorAll(".vs-catbar__item")).toHaveLength(2));
    const active = within(rail()).getByRole("link", { name: parentCategory.name });
    expect(active).toHaveAttribute("aria-current", "page");
    expect(
      within(rail()).getByRole("link", { name: categoryFixture.name }),
    ).not.toHaveAttribute("aria-current");
  });

  it("opens and closes the drawer from the rail trigger", async () => {
    stubApi({ ...storefrontRoutes, "/api/v1/categories": [parentCategory] });
    renderApp("/");

    await waitFor(() => expect(rail()).not.toBeNull());
    const trigger = within(rail()).getByRole("button", { name: "تصنيفات المنتجات" });
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    expect(drawer()).toBeNull();

    await userEvent.click(trigger);
    expect(drawer()).toBeInTheDocument();
    expect(trigger).toHaveAttribute("aria-expanded", "true");

    // The same trigger closes it again — one overlay, one state.
    await userEvent.click(trigger);
    await waitFor(() => expect(drawer()).toBeNull());
  });

  it("hands the categories over to the drawer instead of showing them twice", async () => {
    stubApi({ ...storefrontRoutes, "/api/v1/categories": [categoryFixture, parentCategory] });
    renderApp("/");

    // Collapsed: the rail is the only place the categories are drawn.
    await waitFor(() => expect(rail().querySelectorAll(".vs-catbar__item")).toHaveLength(2));
    expect(drawer()).toBeNull();

    await userEvent.click(within(rail()).getByRole("button", { name: "تصنيفات المنتجات" }));
    const panel = drawer();

    // Expanded: one row per category in the panel, and the icon column is gone
    // rather than left standing beside it as a second copy of the same list.
    expect(panel.querySelectorAll(".vs-catdrawer__item")).toHaveLength(2);
    expect(rail().querySelectorAll(".vs-catbar__item")).toHaveLength(0);
    expect(rail().querySelectorAll(".vs-catbar__thumb, .vs-catbar__ico")).toHaveLength(0);
    // The names the rail only whispered as tooltips are now real, visible rows.
    expect(within(panel).getByRole("link", { name: /مطبوعات المناسبات/ })).toBeInTheDocument();
    expect(within(panel).getAllByText("منتج واحد")).toHaveLength(2);
    // The trigger stays put — it is still what reports and toggles the state.
    expect(rail().querySelector(".vs-catbar__trigger")).toHaveAttribute("aria-expanded", "true");

    // Closing hands them back.
    await userEvent.click(within(rail()).getByRole("button", { name: "تصنيفات المنتجات" }));
    await waitFor(() => expect(drawer()).toBeNull());
    expect(rail().querySelectorAll(".vs-catbar__item")).toHaveLength(2);
  });

  it("expands a category's children inside the drawer", async () => {
    stubApi({ ...storefrontRoutes, "/api/v1/categories": [parentCategory] });
    renderApp("/");

    await waitFor(() => expect(rail()).not.toBeNull());
    await userEvent.click(within(rail()).getByRole("button", { name: "تصنيفات المنتجات" }));

    const panel = drawer();
    expect(within(panel).queryByRole("link", { name: "بنرات" })).not.toBeInTheDocument();

    const toggle = within(panel).getByRole("button", {
      name: `الأقسام الفرعية لـ ${parentCategory.name}`,
    });
    expect(toggle).toHaveAttribute("aria-expanded", "false");

    await userEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(within(panel).getByRole("link", { name: "بنرات" })).toHaveAttribute(
      "href",
      "/category/banners",
    );
    expect(within(panel).getByRole("link", { name: "ستاندات" })).toBeInTheDocument();
  });

  it("keeps the rail out of the admin workspace", async () => {
    stubApi(storefrontRoutes);
    renderApp("/admin");

    await waitFor(() => expect(document.querySelector(".vs-public")).toBeNull());
    expect(document.querySelector(".vs-catbar")).toBeNull();
    expect(screen.queryByRole("dialog", { name: "تصنيفات المنتجات" })).toBeNull();
  });
});

describe("homepage hero", () => {
  const heroRoutes = {
    ...storefrontRoutes,
    "/api/v1/hero-slides": heroSlides,
    "/api/v1/banners": banners,
    "/api/v1/home-sections": [],
  };

  it("shows exactly one advertising image at a time", async () => {
    stubApi(heroRoutes);
    renderApp("/");

    await waitFor(() => expect(document.querySelectorAll(".vs-hero__slide")).toHaveLength(2));
    expect(document.querySelectorAll('.vs-hero__slide[data-active="true"]')).toHaveLength(1);
    expect(document.querySelector('.vs-hero__slide[data-active="true"] img')).toHaveAttribute(
      "src",
      "/media/preview/one.png",
    );
  });

  it("renders no promotional cards beside the hero", async () => {
    stubApi(heroRoutes);
    renderApp("/");

    await waitFor(() => expect(document.querySelector(".vs-hero")).not.toBeNull());
    // Both banners exist in the payload; neither may appear as a hero-side tile.
    expect(document.querySelector(".vs-promocol")).toBeNull();
    expect(document.querySelectorAll(".vs-promo")).toHaveLength(0);
    expect(screen.queryByText("بانر جانبي")).not.toBeInTheDocument();
  });

  it("moves between slides from its own controls", async () => {
    stubApi(heroRoutes);
    renderApp("/");

    await waitFor(() => expect(document.querySelector(".vs-hero")).not.toBeNull());
    const active = () =>
      [...document.querySelectorAll(".vs-hero__slide")].findIndex(
        (slide) => slide.dataset.active === "true",
      );
    expect(active()).toBe(0);

    await userEvent.click(screen.getByRole("button", { name: "الشريحة التالية" }));
    expect(active()).toBe(1);

    await userEvent.click(screen.getByRole("button", { name: "الشريحة السابقة" }));
    expect(active()).toBe(0);

    // Dots are real buttons and report which slide is showing.
    const dot = screen.getByRole("tab", { name: "الشريحة 2" });
    await userEvent.click(dot);
    expect(dot).toHaveAttribute("aria-current", "true");
    expect(active()).toBe(1);
  });

  it("does not autoplay when the visitor has asked for reduced motion", async () => {
    window.__mediaMatches = (query) => query.includes("prefers-reduced-motion");
    stubApi(heroRoutes);
    renderApp("/");

    await waitFor(() => expect(document.querySelector(".vs-hero")).not.toBeNull());
    const active = () =>
      [...document.querySelectorAll(".vs-hero__slide")].findIndex(
        (slide) => slide.dataset.active === "true",
      );
    expect(active()).toBe(0);
    await new Promise((resolve) => setTimeout(resolve, 120));
    expect(active()).toBe(0);
  });
});

describe("hero advertisement copy", () => {
  /** One finished advertisement, one slide the Admin gave supporting copy. */
  const mixedSlides = [
    {
      id: 11,
      title: "إعلان جاهز",
      subtitle: "",
      description: "",
      button_label: "",
      button_url: "",
      image_url: "/media/preview/complete-ad.png",
      sort_order: 0,
    },
    {
      id: 12,
      title: "عنوان الشريحة",
      subtitle: "عنوان فرعي",
      description: "نص كتبه المسؤول في لوحة التحكم.",
      button_label: "تسوّق",
      button_url: "/shop",
      image_url: "/media/preview/with-copy.png",
      sort_order: 1,
    },
  ];

  const routesFor = (slides) => ({
    ...storefrontRoutes,
    "/api/v1/hero-slides": slides,
    "/api/v1/home-sections": [],
  });

  it("shows an image-only advertisement with nothing printed over it", async () => {
    stubApi(routesFor(mixedSlides));
    renderApp("/");

    await waitFor(() => expect(document.querySelectorAll(".vs-hero__slide")).toHaveLength(2));
    const [advert, withCopy] = document.querySelectorAll(".vs-hero__slide");

    // The artwork carries its own typography: no heading, no paragraph, no
    // eyebrow, no button and no darkening veil laid over it.
    expect(advert.querySelector(".vs-hero__body")).toBeNull();
    expect(advert.querySelector(".vs-hero__veil")).toBeNull();
    expect(advert.querySelector(".vs-hero__cta")).toBeNull();
    expect(screen.queryByText("إعلان جاهز")).not.toBeInTheDocument();
    // The title is still the image's alt text, so the slide is not silent.
    expect(advert.querySelector("img")).toHaveAttribute("alt", "إعلان جاهز");

    // The slide the owner actually wrote copy for keeps all of it.
    expect(withCopy.querySelector(".vs-hero__body")).not.toBeNull();
    expect(withCopy.querySelector(".vs-hero__veil")).not.toBeNull();
    expect(within(withCopy).getByText("نص كتبه المسؤول في لوحة التحكم.")).toBeInTheDocument();
    // Queried by class: an inactive slide is aria-hidden, so its button is
    // deliberately out of the accessibility tree until the slide comes round.
    expect(withCopy.querySelector(".vs-hero__cta")).toHaveAttribute("href", "/shop");
    expect(document.querySelectorAll(".vs-hero__body")).toHaveLength(1);
  });

  it("keeps the copy of a slide that has no artwork to speak for it", async () => {
    stubApi(
      routesFor([
        {
          id: 13,
          title: "بدون صورة",
          subtitle: "",
          description: "",
          button_label: "",
          button_url: "",
          image_url: null,
          sort_order: 0,
        },
      ]),
    );
    renderApp("/");

    await waitFor(() => expect(document.querySelector(".vs-hero")).not.toBeNull());
    // Suppressing the title here would leave a blank gradient.
    expect(screen.getByText("بدون صورة")).toBeInTheDocument();
  });

  it("runs the hero band outside the page container", async () => {
    stubApi(routesFor(mixedSlides));
    renderApp("/");

    await waitFor(() => expect(document.querySelector(".vs-hero")).not.toBeNull());
    const row = document.querySelector(".vs-herorow");
    expect(row.classList.contains("vs-container")).toBe(false);
    expect(row.closest(".vs-container")).toBeNull();
  });
});

describe("category rail imagery", () => {
  const withImage = {
    ...categoryFixture,
    id: 21,
    name: "هدايا مخصصة",
    slug: "custom-gifts",
    image_url: "/media/preview/tile-gifts.png",
  };
  const withoutImage = { ...categoryFixture, id: 22, name: "سكارف", slug: "scarves", image_url: null };

  it("uses the category's own picture, and a neutral icon when there is none", async () => {
    stubApi({ ...storefrontRoutes, "/api/v1/categories": [withImage, withoutImage] });
    renderApp("/");

    await waitFor(() => expect(rail().querySelectorAll(".vs-catbar__item")).toHaveLength(2));
    const [first, second] = rail().querySelectorAll(".vs-catbar__item");

    expect(first.querySelector("img")).toHaveAttribute("src", "/media/preview/tile-gifts.png");
    expect(second.querySelector("img")).toBeNull();
    expect(second.querySelector(".vs-catbar__ico")).not.toBeNull();

    // No tinted square ever stands in for a picture the store does not have.
    expect(rail().querySelectorAll(".vs-media--fallback")).toHaveLength(0);
    // Labels and tooltips survive the change.
    expect(second).toHaveAccessibleName("سكارف");
    expect(second).toHaveAttribute("title", "سكارف");
  });

  it("applies the same rule inside the drawer", async () => {
    stubApi({ ...storefrontRoutes, "/api/v1/categories": [withImage, withoutImage] });
    renderApp("/");

    await waitFor(() => expect(rail()).not.toBeNull());
    await userEvent.click(within(rail()).getByRole("button", { name: "تصنيفات المنتجات" }));

    const panel = drawer();
    expect(panel.querySelectorAll(".vs-catdrawer__thumb img")).toHaveLength(1);
    expect(panel.querySelectorAll(".vs-catdrawer__thumb svg")).toHaveLength(1);
    expect(panel.querySelectorAll(".vs-media--fallback")).toHaveLength(0);
  });
});

describe("store logo", () => {
  const branded = {
    ...storefrontRoutes,
    "/api/v1/store/settings": { ...settingsFixture, logo_url: "/brand/store-logo.png" },
  };

  it("clips the logo to a fixed viewport and leaves the file untouched", async () => {
    stubApi(branded);
    renderApp("/");

    // The header's, not the footer's — both render the same file.
    await waitFor(() => expect(document.querySelector(".vs-header .vs-logo__img")).not.toBeNull());
    const logo = document.querySelector(".vs-header .vs-logo__img");
    expect(logo.closest(".vs-logo__box")).not.toBeNull();
    expect(logo).toHaveAttribute("alt", "متجر الاختبار");
    expect(logo).toHaveAttribute("src", "/brand/store-logo.png");
    // Nothing measurable here — no canvas in jsdom — so the fit must not have
    // written any geometry of its own: the stylesheet's `contain` still rules.
    expect(logo.getAttribute("style")).toBeNull();
  });

  it("still shows the store name when no logo is configured", async () => {
    stubApi(storefrontRoutes);
    renderApp("/");

    await waitFor(() => expect(document.querySelector(".vs-logo")).not.toBeNull());
    expect(document.querySelector(".vs-logo__box")).toBeNull();
    expect(document.querySelector(".vs-logo__name")).toHaveTextContent("متجر الاختبار");
  });
});

describe("homepage category grid", () => {
  it("puts each category's title over its own artwork and links the whole card", async () => {
    stubApi({
      ...storefrontRoutes,
      "/api/v1/categories": [categoryFixture, parentCategory],
      "/api/v1/home-sections": [
        {
          id: 1,
          section_key: "categories",
          section_type: "categories",
          title: "تسوّق حسب القسم",
          description: "",
          sort_order: 0,
          config: {},
        },
      ],
    });
    renderApp("/");

    expect(await screen.findByRole("heading", { name: "تسوّق حسب القسم" })).toBeInTheDocument();
    const cards = document.querySelectorAll(".vs-cat");
    expect(cards).toHaveLength(2);

    // The title is over the image, and readable without any interaction.
    const first = cards[0];
    expect(first.tagName).toBe("A");
    expect(first).toHaveAttribute("href", `/category/${categoryFixture.slug}`);
    expect(within(first).getByText(categoryFixture.name)).toBeInTheDocument();
    expect(first.querySelector(".vs-cat__center")).toContainElement(
      within(first).getByText(categoryFixture.name),
    );
    // No white text panel under the artwork any more.
    expect(first.querySelector(".vs-cat__text")).toBeNull();
  });
});
