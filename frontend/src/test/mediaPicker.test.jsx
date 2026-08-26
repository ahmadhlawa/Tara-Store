import { useState } from "react";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { MediaField } from "../admin/MediaPicker.jsx";
import { page, respond, stubApi } from "./utils.jsx";

const asset = (id, name) => ({
  id,
  original_filename: name,
  stored_key: `2026/07/${name}`,
  content_type: "image/png",
  size_bytes: 2048,
  url: `/uploads/${name}`,
  storage_provider: "local",
  uploaded_by_id: 1,
  created_at: "2026-07-01T00:00:00Z",
});

const LIBRARY = page([asset(1, "hero.png"), asset(2, "promo.png")]);

/** Mirrors how ResourceScreen/Settings own the value and hand it to the field. */
function Harness({ initial = "", onValue }) {
  const [value, setValue] = useState(initial);
  return (
    <>
      <MediaField
        title="صورة القسم"
        value={value}
        onChange={(next) => {
          onValue?.(next);
          setValue(next);
        }}
      />
      <span data-testid="value">{value}</span>
    </>
  );
}

const openPicker = async () => {
  await userEvent.click(screen.getByRole("button", { name: "اختيار من مكتبة الوسائط" }));
  return screen.findByRole("dialog", { name: "مكتبة الوسائط" });
};

describe("media picker", () => {
  it("searches media by filename", async () => {
    stubApi({
      "/api/v1/admin/media": ({ path }) =>
        path.includes("q=promo") ? page([asset(2, "promo.png")]) : LIBRARY,
    });
    render(<Harness />);

    const dialog = await openPicker();
    await userEvent.type(within(dialog).getByLabelText("بحث باسم الملف"), "promo");
    expect(await within(dialog).findByText("promo.png")).toBeInTheDocument();
    expect(within(dialog).queryByText("hero.png")).not.toBeInTheDocument();
  });

  it("opens from the image field and lists the existing library", async () => {
    stubApi({ "/api/v1/admin/media": LIBRARY });
    render(<Harness />);

    const dialog = await openPicker();
    expect(await within(dialog).findByText("hero.png")).toBeInTheDocument();
    expect(within(dialog).getByText("promo.png")).toBeInTheDocument();
  });

  it("returns the selected asset url to the field and previews it", async () => {
    const onValue = vi.fn();
    stubApi({ "/api/v1/admin/media": LIBRARY });
    render(<Harness onValue={onValue} />);

    const dialog = await openPicker();
    await userEvent.click(await within(dialog).findByText("promo.png"));
    await userEvent.click(within(dialog).getByRole("button", { name: "اختيار" }));

    expect(onValue).toHaveBeenCalledWith("/uploads/promo.png");
    expect(screen.getByTestId("value")).toHaveTextContent("/uploads/promo.png");
    expect(screen.queryByRole("dialog", { name: "مكتبة الوسائط" })).not.toBeInTheDocument();
  });

  it("leaves the existing value untouched when the dialog is cancelled", async () => {
    stubApi({ "/api/v1/admin/media": LIBRARY });
    render(<Harness initial="https://cdn.example.com/old.png" />);

    const dialog = await openPicker();
    await userEvent.click(await within(dialog).findByText("hero.png"));
    await userEvent.click(within(dialog).getByRole("button", { name: "إلغاء" }));

    expect(screen.getByTestId("value")).toHaveTextContent("https://cdn.example.com/old.png");
  });

  it("clears the field and keeps a manual url available as a fallback", async () => {
    stubApi({ "/api/v1/admin/media": LIBRARY });
    render(<Harness initial="https://cdn.example.com/old.png" />);

    await userEvent.click(screen.getByRole("button", { name: "إزالة" }));
    expect(screen.getByText("لا توجد صورة محددة.")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "إدخال رابط صورة يدويًا" }));
    await userEvent.type(screen.getByLabelText(/رابط يدوي/), "https://cdn.example.com/new.png");
    expect(screen.getByTestId("value")).toHaveTextContent("https://cdn.example.com/new.png");
  });

  it("adds a freshly uploaded image to the list and selects it", async () => {
    const uploaded = asset(9, "fresh.png");
    stubApi({ "/api/v1/admin/media": LIBRARY, "POST /api/v1/admin/media": uploaded });
    render(<Harness />);

    const dialog = await openPicker();
    await within(dialog).findByText("hero.png");
    await userEvent.upload(
      within(dialog).getByLabelText("رفع صورة جديدة"),
      new File(["x"], "fresh.png", { type: "image/png" }),
    );

    expect(await within(dialog).findByText("fresh.png")).toBeInTheDocument();
    await userEvent.click(within(dialog).getByRole("button", { name: "اختيار" }));
    expect(screen.getByTestId("value")).toHaveTextContent("/uploads/fresh.png");
  });

  it("shows a recoverable error when the library fails to load", async () => {
    let failed = false;
    stubApi({
      "/api/v1/admin/media": () => {
        if (failed) return LIBRARY;
        failed = true;
        return respond(500, { error: { code: "server_error", message: "تعذّر تحميل مكتبة الوسائط." } });
      },
    });
    render(<Harness />);

    const dialog = await openPicker();
    expect(await within(dialog).findByRole("alert")).toHaveTextContent("تعذّر تحميل مكتبة الوسائط.");

    await userEvent.click(within(dialog).getByRole("button", { name: "إعادة المحاولة" }));
    expect(await within(dialog).findByText("hero.png")).toBeInTheDocument();
  });

  it("reports a failed upload without closing the picker", async () => {
    stubApi({
      "/api/v1/admin/media": LIBRARY,
      "POST /api/v1/admin/media": respond(413, { error: { code: "too_large", message: "الملف كبير جداً." } }),
    });
    render(<Harness />);

    const dialog = await openPicker();
    await within(dialog).findByText("hero.png");
    await userEvent.upload(
      within(dialog).getByLabelText("رفع صورة جديدة"),
      new File(["x"], "huge.png", { type: "image/png" }),
    );

    expect(await within(dialog).findByRole("alert")).toHaveTextContent("الملف كبير جداً.");
    expect(within(dialog).getByText("hero.png")).toBeInTheDocument();
  });
});

describe("resource screens", () => {
  it("renders category image as a media field, not a bare url input", async () => {
    const { CategoriesPage } = await import("../admin/pages/CatalogScreens.jsx");
    stubApi({
      "/api/v1/admin/categories": page([
        { id: 1, name: "ريزن", slug: "resin", image_url: null, parent_id: null, is_active: true, is_featured: false, sort_order: 0, product_count: 0 },
      ]),
      "/api/v1/admin/media": LIBRARY,
    });
    render(<CategoriesPage />);

    await userEvent.click(await screen.findByRole("button", { name: "إضافة قسم" }));
    expect(await screen.findByRole("button", { name: "اختيار من مكتبة الوسائط" })).toBeInTheDocument();

    const dialog = await openPicker();
    await userEvent.click(await within(dialog).findByText("hero.png"));
    await userEvent.click(within(dialog).getByRole("button", { name: "اختيار" }));

    await waitFor(() => expect(screen.getByTitle("/uploads/hero.png")).toBeInTheDocument());
  });
});

describe("product images", () => {
  it("adds a library image to the product gallery", async () => {
    const product = {
      id: 7,
      name: "ريزن شفاف",
      slug: "clear-resin",
      sku: "RES-1",
      product_type: "standard",
      category_id: null,
      price: 100,
      stock_quantity: 1,
      track_inventory: true,
      is_active: true,
      images: [],
      specifications: [],
      options: [],
      variants: [],
      package_items: [],
    };
    const calls = stubApi({
      "/api/v1/admin/products/7/images": asset(3, "shot.png"),
      "/api/v1/admin/products/7": product,
      "/api/v1/admin/products": page([]),
      "/api/v1/admin/categories": page([]),
      "/api/v1/admin/media": LIBRARY,
    });

    const { MemoryRouter, Route, Routes } = await import("react-router-dom");
    const { default: ProductEditorPage } = await import("../admin/pages/ProductEditorPage.jsx");
    render(
      <MemoryRouter initialEntries={["/admin/products/7"]}>
        <Routes>
          <Route path="/admin/products/:productId" element={<ProductEditorPage />} />
        </Routes>
      </MemoryRouter>,
    );

    await userEvent.click((await screen.findAllByRole("button", { name: "اختيار من مكتبة الوسائط" }))[0]);
    const dialog = await screen.findByRole("dialog", { name: "مكتبة الوسائط" });
    await userEvent.click(await within(dialog).findByText("hero.png"));
    await userEvent.click(within(dialog).getByRole("button", { name: "اختيار" }));

    expect(await screen.findByText("صورة رئيسية جديدة")).toBeVisible();
    expect(calls.find((call) => call.method === "POST" && call.path === "/api/v1/admin/products/7/images")).toBeUndefined();
  });
});
