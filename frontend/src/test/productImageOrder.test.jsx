import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import ProductImageGallery from "../admin/ProductImageGallery.jsx";
import ProductEditorPage from "../admin/pages/ProductEditorPage.jsx";
import { page, respond, stubApi } from "./utils.jsx";

const img = (id, name) => ({ id, url: `/media/${name}.png`, alt_text: name, sort_order: id });

const A = img(1, "a");
const B = img(2, "b");
const C = img(3, "c");

const cards = () => screen.getAllByLabelText(/^الصورة \d+ من \d+$/);
const badgeOwner = () => screen.getByText("الصورة الرئيسية").closest("[aria-label]");
const upOf = (name) => screen.getByLabelText(`تحريك للأعلى: ${name}`);
const downOf = (name) => screen.getByLabelText(`تحريك للأسفل: ${name}`);

describe("product image gallery", () => {
  it("marks only the first image as the cover", () => {
    render(<ProductImageGallery images={[A, B, C]} onReorder={vi.fn()} onDelete={vi.fn()} />);

    expect(screen.getAllByText("الصورة الرئيسية")).toHaveLength(1);
    expect(badgeOwner()).toBe(cards()[0]);
    expect(within(cards()[1]).queryByText("الصورة الرئيسية")).not.toBeInTheDocument();
  });

  it("moves an image down and hands the whole new order to the server", async () => {
    const onReorder = vi.fn().mockResolvedValue(undefined);
    render(<ProductImageGallery images={[A, B, C]} onReorder={onReorder} onDelete={vi.fn()} />);

    await userEvent.click(downOf("a"));

    expect(onReorder).toHaveBeenCalledWith([2, 1, 3]);
    // The badge follows the new first image with no separate primary call.
    await waitFor(() => expect(badgeOwner()).toBe(cards()[0]));
    expect(within(cards()[0]).getByLabelText(/تحريك للأسفل: b/)).toBeInTheDocument();
    expect(onReorder).toHaveBeenCalledTimes(1);
  });

  it("moves an image up", async () => {
    const onReorder = vi.fn().mockResolvedValue(undefined);
    render(<ProductImageGallery images={[A, B, C]} onReorder={onReorder} onDelete={vi.fn()} />);

    await userEvent.click(upOf("c"));

    expect(onReorder).toHaveBeenCalledWith([1, 3, 2]);
  });

  it("disables up on the first image and down on the last", () => {
    render(<ProductImageGallery images={[A, B, C]} onReorder={vi.fn()} onDelete={vi.fn()} />);

    expect(upOf("a")).toBeDisabled();
    expect(downOf("a")).toBeEnabled();
    expect(upOf("b")).toBeEnabled();
    expect(downOf("b")).toBeEnabled();
    expect(downOf("c")).toBeDisabled();
  });

  it("reorders by dragging one card onto another", async () => {
    const onReorder = vi.fn().mockResolvedValue(undefined);
    render(<ProductImageGallery images={[A, B, C]} onReorder={onReorder} onDelete={vi.fn()} />);

    const [first, , third] = cards();
    const dataTransfer = { effectAllowed: "", setData: vi.fn(), getData: vi.fn() };
    fireEvent.dragStart(third, { dataTransfer });
    fireEvent.dragOver(first, { dataTransfer });
    fireEvent.drop(first, { dataTransfer });

    expect(onReorder).toHaveBeenCalledWith([3, 1, 2]);
    await waitFor(() => expect(within(cards()[0]).getByLabelText(/تحريك للأسفل: c/)).toBeInTheDocument());
  });

  it("snaps back to the stored order when saving the new one fails", async () => {
    const onReorder = vi.fn().mockRejectedValue(new Error("nope"));
    render(<ProductImageGallery images={[A, B, C]} onReorder={onReorder} onDelete={vi.fn()} />);

    await userEvent.click(downOf("a"));

    await waitFor(() => expect(within(cards()[0]).getByLabelText(/تحريك للأسفل: a/)).toBeInTheDocument());
    expect(badgeOwner()).toBe(cards()[0]);
  });
});

const PRODUCT = {
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
  images: [A, B, C],
  specifications: [],
  options: [],
  variants: [],
  package_items: [],
};

const renderEditor = (routes) => {
  const calls = stubApi({
    "/api/v1/admin/products/7": PRODUCT,
    "/api/v1/admin/products": page([]),
    "/api/v1/admin/categories": page([]),
    ...routes,
  });
  render(
    <MemoryRouter initialEntries={["/admin/products/7"]}>
      <Routes>
        <Route path="/admin/products/:productId" element={<ProductEditorPage />} />
      </Routes>
    </MemoryRouter>,
  );
  return calls;
};

describe("product editor image ordering", () => {
  it("creates a product with a device-uploaded cover and gallery in one save", async () => {
    const created = { ...PRODUCT, id: 8, images: [] };
    const attached = [];
    const calls = stubApi({
      "POST /api/v1/admin/media": ({ init }) => {
        const file = init.body.get("file");
        return { id: file.name === "main.png" ? 20 : 21, url: `/media/${file.name}` };
      },
      "/api/v1/admin/categories": page([]),
      "POST /api/v1/admin/products": ({ init }) => {
        if ((init.method || "GET") === "POST") {
          const payload = JSON.parse(init.body);
          expect(payload.images).toBeUndefined();
          expect(payload.seo_title).toBe("منتج جديد");
          expect(payload.seo_description).toBe("وصف المنتج الجديد");
          return created;
        }
        return page([]);
      },
      "POST /api/v1/admin/products/8/images": ({ init }) => {
        const image = JSON.parse(init.body);
        attached.push(image);
        return { id: attached.length, ...image, sort_order: attached.length - 1 };
      },
    });

    render(
      <MemoryRouter initialEntries={["/admin/products/new"]}>
        <Routes>
          <Route path="/admin/products/:productId" element={<ProductEditorPage />} />
        </Routes>
      </MemoryRouter>,
    );

    await userEvent.upload(screen.getByLabelText("الصورة الرئيسية — رفع من الجهاز"), new File(["main"], "main.png", { type: "image/png" }));
    await userEvent.upload(screen.getByLabelText("صور إضافية — رفع من الجهاز"), new File(["extra"], "extra.png", { type: "image/png" }));
    await userEvent.type(screen.getByLabelText("اسم المنتج"), "منتج جديد");
    await userEvent.type(screen.getByLabelText("وصف مختصر"), "وصف المنتج الجديد");
    expect(screen.getByText("صورة رئيسية جديدة")).toBeInTheDocument();
    expect(screen.getByText("extra.png")).toBeInTheDocument();
    expect(screen.queryByText(/احفظ المنتج أولاً/)).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "حفظ" }));

    await waitFor(() => expect(attached.map((image) => image.url)).toEqual(["/media/main.png", "/media/extra.png"]));
    expect(calls.filter((call) => call.method === "POST").map((call) => call.path)).toEqual([
      "/api/v1/admin/products",
      "/api/v1/admin/media",
      "/api/v1/admin/media",
      "/api/v1/admin/products/8/images",
      "/api/v1/admin/products/8/images",
    ]);
  });

  it("reports a staged upload failure after creating the product", async () => {
    const created = { ...PRODUCT, id: 8, images: [] };
    const calls = stubApi({
      "POST /api/v1/admin/media": respond(500, { error: { code: "server_error", message: "فشل رفع الصورة." } }),
      "/api/v1/admin/categories": page([]),
      "POST /api/v1/admin/products": created,
      "/api/v1/admin/products": page([]),
      "DELETE /api/v1/admin/products/8": { message: "تم حذف المنتج." },
    });
    render(
      <MemoryRouter initialEntries={["/admin/products/new"]}>
        <Routes><Route path="/admin/products/:productId" element={<ProductEditorPage />} /></Routes>
      </MemoryRouter>,
    );

    await userEvent.upload(screen.getByLabelText("الصورة الرئيسية — رفع من الجهاز"), new File(["main"], "main.png", { type: "image/png" }));
    await userEvent.click(screen.getByRole("button", { name: "حفظ" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("فشل رفع الصورة.");
    expect(calls.some((call) => call.method === "POST" && call.path === "/api/v1/admin/products")).toBe(true);
    expect(calls.some((call) => call.method === "DELETE" && call.path === "/api/v1/admin/products/8")).toBe(true);
  });

  it("creates a product with only its staged main image", async () => {
    const calls = stubApi({
      "POST /api/v1/admin/media": { id: 20, url: "/media/main.png" },
      "/api/v1/admin/categories": page([]),
      "POST /api/v1/admin/products": { ...PRODUCT, id: 9, images: [] },
      "POST /api/v1/admin/products/9/images": { id: 1, url: "/media/main.png", sort_order: 0 },
    });
    render(
      <MemoryRouter initialEntries={["/admin/products/new"]}>
        <Routes><Route path="/admin/products/:productId" element={<ProductEditorPage />} /></Routes>
      </MemoryRouter>,
    );

    await userEvent.upload(screen.getByLabelText("الصورة الرئيسية — رفع من الجهاز"), new File(["main"], "main.png", { type: "image/png" }));
    await userEvent.click(screen.getByRole("button", { name: "حفظ" }));

    await waitFor(() => expect(calls.some((call) => call.method === "POST" && call.path === "/api/v1/admin/products/9/images")).toBe(true));
    expect(calls.filter((call) => call.path === "/api/v1/admin/products/9/images")).toHaveLength(1);
  });

  it("stages a media-library image for a new product", async () => {
    stubApi({
      "/api/v1/admin/categories": page([]),
      "/api/v1/admin/products": page([]),
      "/api/v1/admin/media": page([{ id: 11, original_filename: "library.png", url: "/media/library.png" }]),
    });
    render(
      <MemoryRouter initialEntries={["/admin/products/new"]}>
        <Routes><Route path="/admin/products/:productId" element={<ProductEditorPage />} /></Routes>
      </MemoryRouter>,
    );

    await userEvent.click(screen.getAllByRole("button", { name: "اختيار من مكتبة الوسائط" })[0]);
    const dialog = await screen.findByRole("dialog", { name: "مكتبة الوسائط" });
    await userEvent.click(await within(dialog).findByText("library.png"));
    await userEvent.click(within(dialog).getByRole("button", { name: "اختيار" }));

    expect(screen.getByText("صورة رئيسية جديدة")).toBeInTheDocument();
    expect(screen.queryByText(/احفظ المنتج أولاً/)).not.toBeInTheDocument();
  });

  it("persists a reorder through the product images endpoint", async () => {
    const calls = renderEditor({
      "PUT /api/v1/admin/products/7/images/reorder": [B, A, C],
    });

    await screen.findByText("الصورة الرئيسية");
    await userEvent.click(downOf("a"));

    await waitFor(() => {
      const put = calls.find((call) => call.method === "PUT");
      expect(put.path).toBe("/api/v1/admin/products/7/images/reorder");
      expect(JSON.parse(put.body)).toEqual({ image_ids: [2, 1, 3] });
    });
  });

  it("reports a failed reorder instead of showing it as saved", async () => {
    renderEditor({
      "PUT /api/v1/admin/products/7/images/reorder": respond(400, {
        error: { code: "image_mismatch", message: "تعذّر حفظ ترتيب الصور." },
      }),
    });

    await screen.findByText("الصورة الرئيسية");
    await userEvent.click(downOf("a"));

    expect(await screen.findByRole("alert")).toHaveTextContent("تعذّر حفظ ترتيب الصور.");
    await waitFor(() => expect(within(cards()[0]).getByLabelText(/تحريك للأسفل: a/)).toBeInTheDocument());
  });

  it("promotes the next image when the cover is deleted", async () => {
    let deleted = false;
    renderEditor({
      "/api/v1/admin/products/7": () => (deleted ? { ...PRODUCT, images: [B, C] } : PRODUCT),
      "DELETE /api/v1/admin/products/7/images/1": () => {
        deleted = true;
        return { message: "تم حذف الصورة." };
      },
    });

    await screen.findByText("الصورة الرئيسية");
    await userEvent.click(within(cards()[0]).getByRole("button", { name: "حذف" }));

    await waitFor(() => expect(cards()).toHaveLength(2));
    expect(badgeOwner()).toBe(cards()[0]);
    expect(within(cards()[0]).getByLabelText(/تحريك للأسفل: b/)).toBeInTheDocument();
  });

  it("appends a picked image without making it the cover", async () => {
    const D = img(4, "d");
    let added = false;
    const calls = renderEditor({
      "/api/v1/admin/products/7": () => (added ? { ...PRODUCT, images: [A, B, C, D] } : PRODUCT),
      "PATCH /api/v1/admin/products/7": PRODUCT,
      "POST /api/v1/admin/products/7/images": () => {
        added = true;
        return D;
      },
      "/api/v1/admin/media": page([
        {
          id: 11,
          original_filename: "d.png",
          stored_key: "d.png",
          content_type: "image/png",
          size_bytes: 10,
          url: "/media/d.png",
          storage_provider: "local",
          created_at: "2026-07-01T00:00:00Z",
        },
      ]),
    });

    await screen.findByText("الصورة الرئيسية");
    await userEvent.click(screen.getAllByRole("button", { name: "اختيار من مكتبة الوسائط" })[1]);
    const dialog = await screen.findByRole("dialog", { name: "مكتبة الوسائط" });
    await userEvent.click(await within(dialog).findByText("d.png"));
    await userEvent.click(within(dialog).getByRole("button", { name: "اختيار" }));
    await userEvent.click(screen.getByRole("button", { name: "حفظ" }));

    await waitFor(() => expect(cards()).toHaveLength(4));
    expect(badgeOwner()).toBe(cards()[0]);
    expect(within(cards()[0]).getByLabelText(/تحريك للأسفل: a/)).toBeInTheDocument();
    expect(within(cards()[3]).getByLabelText(/تحريك للأعلى: d/)).toBeInTheDocument();
    expect(calls.some((call) => call.method === "PUT")).toBe(false);
  });
});
