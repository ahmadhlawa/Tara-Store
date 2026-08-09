import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import ProductVariantsEditor, {
  buildOptionsPayload,
  variantsRemovedByOptions,
} from "../admin/ProductVariantsEditor.jsx";
import ProductEditorPage from "../admin/pages/ProductEditorPage.jsx";
import { cartStorage } from "../storage/cartStorage.js";
import { page, productFixture, renderApp, storefrontRoutes, stubApi } from "./utils.jsx";
import { authStorage } from "../storage/authStorage.js";

const OPTIONS = [
  {
    id: 1,
    name: "اللون",
    sort_order: 0,
    values: [
      { id: 11, value: "أحمر", sort_order: 0 },
      { id: 12, value: "أزرق", sort_order: 1 },
    ],
  },
  {
    id: 2,
    name: "الحجم",
    sort_order: 1,
    values: [
      { id: 21, value: "صغير", sort_order: 0 },
      { id: 22, value: "كبير", sort_order: 1 },
    ],
  },
];

const variantRow = (id, title, ids, extra = {}) => ({
  id,
  title,
  sku: null,
  price_override: null,
  stock_quantity: 0,
  is_active: true,
  option_value_ids: ids,
  ...extra,
});

const RED_SMALL = variantRow(101, "أحمر / صغير", [11, 21], {
  sku: "RS-1",
  price_override: 70,
  stock_quantity: 4,
});

const setup = (props = {}) => {
  const onCreate = vi.fn().mockResolvedValue(undefined);
  const onUpdate = vi.fn().mockResolvedValue(undefined);
  const onDelete = vi.fn().mockResolvedValue(undefined);
  const onReport = vi.fn();
  render(
    <ProductVariantsEditor
      options={OPTIONS}
      variants={[RED_SMALL]}
      onCreate={onCreate}
      onUpdate={onUpdate}
      onDelete={onDelete}
      onReport={onReport}
      {...props}
    />,
  );
  return { onCreate, onUpdate, onDelete, onReport };
};

const editRedSmall = () => screen.getByRole("button", { name: "تعديل أحمر / صغير" });
const save = () => screen.getByRole("button", { name: "حفظ النسخة" });

describe("admin variant editing", () => {
  it("opens an inline editor for an existing variant with its current values", async () => {
    setup();

    await userEvent.click(editRedSmall());

    expect(screen.getByLabelText("اسم النسخة")).toHaveValue("أحمر / صغير");
    expect(screen.getByLabelText("SKU النسخة")).toHaveValue("RS-1");
    expect(screen.getByLabelText("سعر النسخة الخاص")).toHaveValue(70);
    expect(screen.getByLabelText("مخزون النسخة")).toHaveValue(4);
    expect(screen.getByLabelText("فعّالة")).toBeChecked();
  });

  it("saves an edited SKU through the update endpoint", async () => {
    const { onUpdate } = setup();

    await userEvent.click(editRedSmall());
    await userEvent.clear(screen.getByLabelText("SKU النسخة"));
    await userEvent.type(screen.getByLabelText("SKU النسخة"), "RS-9");
    await userEvent.click(save());

    expect(onUpdate).toHaveBeenCalledWith(101, expect.objectContaining({ sku: "RS-9" }));
  });

  it("saves an edited special price", async () => {
    const { onUpdate } = setup();

    await userEvent.click(editRedSmall());
    await userEvent.clear(screen.getByLabelText("سعر النسخة الخاص"));
    await userEvent.type(screen.getByLabelText("سعر النسخة الخاص"), "88.5");
    await userEvent.click(save());

    expect(onUpdate).toHaveBeenCalledWith(101, expect.objectContaining({ price_override: 88.5 }));
  });

  it("clears the special price back to the product price when emptied", async () => {
    const { onUpdate } = setup();

    await userEvent.click(editRedSmall());
    await userEvent.clear(screen.getByLabelText("سعر النسخة الخاص"));
    await userEvent.click(save());

    expect(onUpdate).toHaveBeenCalledWith(101, expect.objectContaining({ price_override: null }));
  });

  it("saves an edited stock quantity", async () => {
    const { onUpdate } = setup();

    await userEvent.click(editRedSmall());
    await userEvent.clear(screen.getByLabelText("مخزون النسخة"));
    await userEvent.type(screen.getByLabelText("مخزون النسخة"), "12");
    await userEvent.click(save());

    expect(onUpdate).toHaveBeenCalledWith(101, expect.objectContaining({ stock_quantity: 12 }));
  });

  it("saves the active flag and keeps the option combination untouched", async () => {
    const { onUpdate } = setup();

    await userEvent.click(editRedSmall());
    await userEvent.click(screen.getByLabelText("فعّالة"));
    await userEvent.click(save());

    expect(onUpdate).toHaveBeenCalledWith(101, {
      title: "أحمر / صغير",
      sku: "RS-1",
      price_override: 70,
      stock_quantity: 4,
      is_active: false,
      option_value_ids: [11, 21],
    });
  });

  it("leaves the original values in place when the edit is cancelled", async () => {
    const { onUpdate } = setup();

    await userEvent.click(editRedSmall());
    await userEvent.clear(screen.getByLabelText("SKU النسخة"));
    await userEvent.type(screen.getByLabelText("SKU النسخة"), "THROWAWAY");
    await userEvent.click(screen.getByRole("button", { name: "إلغاء" }));

    expect(onUpdate).not.toHaveBeenCalled();
    expect(screen.getByText("أحمر / صغير")).toBeInTheDocument();
    expect(screen.getByText(/RS-1/)).toBeInTheDocument();
    expect(screen.queryByText(/THROWAWAY/)).not.toBeInTheDocument();
  });

  it("keeps the editor open and shows no saved state when the update fails", async () => {
    const onUpdate = vi.fn().mockRejectedValue(new Error("فشل الحفظ"));
    setup({ onUpdate });

    await userEvent.click(editRedSmall());
    await userEvent.clear(screen.getByLabelText("مخزون النسخة"));
    await userEvent.type(screen.getByLabelText("مخزون النسخة"), "99");
    await userEvent.click(save());

    await waitFor(() => expect(onUpdate).toHaveBeenCalled());
    // Still editing, and the read-only row never claimed the new stock.
    expect(screen.getByLabelText("مخزون النسخة")).toHaveValue(99);
    expect(screen.queryByText(/المخزون: 99/)).not.toBeInTheDocument();
  });
});

describe("admin multi-axis variant creation", () => {
  it("renders one selector per option axis", () => {
    setup();

    expect(screen.getByLabelText("اللون")).toBeInTheDocument();
    expect(screen.getByLabelText("الحجم")).toBeInTheDocument();
    expect(screen.getAllByRole("combobox")).toHaveLength(OPTIONS.length);
  });

  it("sends one option value from each axis as an array", async () => {
    const { onCreate } = setup();

    await userEvent.selectOptions(screen.getByLabelText("اللون"), "12");
    await userEvent.selectOptions(screen.getByLabelText("الحجم"), "22");
    await userEvent.click(screen.getByRole("button", { name: "إضافة نسخة" }));

    expect(onCreate).toHaveBeenCalledWith([
      expect.objectContaining({ title: "أزرق / كبير", option_value_ids: [12, 22] }),
    ]);
  });
});

describe("admin variant generator", () => {
  const generate = () => screen.getByRole("button", { name: "توليد المتغيرات من الخيارات" });

  it("creates every missing combination of the two axes", async () => {
    const { onCreate } = setup({ variants: [] });

    await userEvent.click(generate());

    const [rows] = onCreate.mock.calls[0];
    expect(rows).toHaveLength(4);
    expect(rows.map((row) => row.title)).toEqual([
      "أحمر / صغير",
      "أحمر / كبير",
      "أزرق / صغير",
      "أزرق / كبير",
    ]);
    expect(rows.map((row) => row.option_value_ids)).toEqual([
      [11, 21],
      [11, 22],
      [12, 21],
      [12, 22],
    ]);
    // Nothing invented: base price stays effective and stock starts at the safe zero.
    expect(rows.every((row) => row.price_override === null && row.sku === null)).toBe(true);
    expect(rows.every((row) => row.stock_quantity === 0 && row.is_active === true)).toBe(true);
  });

  it("skips combinations that already exist and reports the counts", async () => {
    const { onCreate, onReport } = setup();

    await userEvent.click(generate());

    const [rows] = onCreate.mock.calls[0];
    expect(rows).toHaveLength(3);
    expect(rows.map((row) => row.option_value_ids)).not.toContainEqual([11, 21]);
    await waitFor(() => expect(onReport).toHaveBeenCalledWith("تم إنشاء 3 نسخة — موجودة مسبقاً 1"));
  });

  it("reports nothing when a generation attempt fails", async () => {
    const onCreate = vi.fn().mockRejectedValue(new Error("تعذّرت العملية."));
    const { onReport } = setup({ onCreate });

    await userEvent.click(generate());

    await waitFor(() => expect(onCreate).toHaveBeenCalled());
    expect(onReport).not.toHaveBeenCalled();
  });

  it("never rewrites the state of a variant that already exists", async () => {
    const { onCreate, onUpdate, onDelete } = setup();

    await userEvent.click(generate());

    await waitFor(() => expect(onCreate).toHaveBeenCalled());
    expect(onUpdate).not.toHaveBeenCalled();
    expect(onDelete).not.toHaveBeenCalled();
    expect(screen.getByText("أحمر / صغير")).toBeInTheDocument();
    expect(screen.getByText(/المخزون: 4/)).toBeInTheDocument();
  });

  it("stays disabled while an axis has no values", () => {
    setup({ options: [OPTIONS[0], { id: 3, name: "الرائحة", sort_order: 2, values: [] }] });

    expect(generate()).toBeDisabled();
  });
});

const ADMIN = {
  id: 1,
  email: "owner@example.com",
  full_name: "مالك المتجر",
  role: "super_admin",
  is_active: true,
  created_at: "2026-07-01T00:00:00Z",
  last_login_at: null,
};

const adminProduct = {
  id: 7,
  name: "سكارف",
  slug: "scarf",
  category_id: null,
  product_type: "standard",
  sku: "SC-1",
  short_description: "",
  description: "",
  price: 60,
  compare_at_price: null,
  cost_price: null,
  stock_quantity: 5,
  track_inventory: true,
  low_stock_threshold: 3,
  is_active: true,
  is_featured: false,
  is_new: false,
  is_bestseller: false,
  sort_order: 0,
  seo_title: null,
  seo_description: null,
  images: [],
  specifications: [],
  options: OPTIONS,
  variants: [RED_SMALL],
  package_items: [],
};

describe("product editor variant wiring", () => {
  it("patches the existing variant and keeps its option combination", async () => {
    authStorage.save("valid-token", ADMIN);
    const calls = stubApi({
      "/api/v1/auth/me": ADMIN,
      "/api/v1/admin/products/7": adminProduct,
      "PATCH /api/v1/admin/products/7/variants/101": { ...RED_SMALL, stock_quantity: 30 },
      "/api/v1/admin/categories": page([]),
      "/api/v1/admin/products": page([]),
    });

    render(
      <MemoryRouter initialEntries={["/admin/products/7"]}>
        <Routes>
          <Route path="/admin/products/:productId" element={<ProductEditorPage />} />
        </Routes>
      </MemoryRouter>,
    );

    await userEvent.click(await screen.findByRole("button", { name: "تعديل أحمر / صغير" }));
    await userEvent.clear(screen.getByLabelText("مخزون النسخة"));
    await userEvent.type(screen.getByLabelText("مخزون النسخة"), "30");
    await userEvent.click(screen.getByRole("button", { name: "حفظ النسخة" }));

    const patch = await waitFor(() => {
      const call = calls.find((row) => row.method === "PATCH");
      expect(call).toBeTruthy();
      return call;
    });
    expect(JSON.parse(patch.body)).toEqual({
      title: "أحمر / صغير",
      sku: "RS-1",
      price_override: 70,
      stock_quantity: 30,
      is_active: true,
      option_value_ids: [11, 21],
    });
  });
});

const twoAxisProduct = {
  ...productFixture,
  id: 9,
  name: "سكارف مزدوج",
  slug: "two-axis",
  price: 60,
  compare_at_price: null,
  has_options: true,
  options: OPTIONS,
  variants: [
    variantRow(101, "أحمر / صغير", [11, 21], { stock_quantity: 4 }),
    variantRow(102, "أحمر / كبير", [11, 22], { stock_quantity: 4 }),
    variantRow(103, "أزرق / صغير", [12, 21], { stock_quantity: 4 }),
    variantRow(104, "أزرق / كبير", [12, 22], { stock_quantity: 4, price_override: 90 }),
  ],
};

const storefrontFor = (product) => ({
  ...storefrontRoutes,
  [`/api/v1/products/${product.slug}`]: product,
  "/api/v1/products/related": page([]),
  "/api/v1/products": page([product]),
});

describe("storefront multi-axis selection", () => {
  it("resolves the variant that matches one value from each axis", async () => {
    stubApi(storefrontFor(twoAxisProduct));
    renderApp("/product/two-axis");

    const color = await screen.findByRole("group", { name: "اللون" });
    const size = screen.getByRole("group", { name: "الحجم" });

    await userEvent.click(within(color).getByRole("button", { name: "أزرق" }));
    await userEvent.click(within(size).getByRole("button", { name: "كبير" }));

    // The blue/large row carries its own price.
    expect(await screen.findByText("90 ₪")).toBeInTheDocument();
  });

  it("puts the resolved variant id into the cart line", async () => {
    stubApi(storefrontFor(twoAxisProduct));
    renderApp("/product/two-axis");

    const color = await screen.findByRole("group", { name: "اللون" });
    await userEvent.click(within(color).getByRole("button", { name: "أزرق" }));
    await userEvent.click(within(screen.getByRole("group", { name: "الحجم" })).getByRole("button", { name: "كبير" }));
    await userEvent.click(screen.getByRole("button", { name: /أضف إلى العربة/ }));

    await waitFor(() => expect(cartStorage.load()).toHaveLength(1));
    expect(cartStorage.load()[0].variantId).toBe(104);
  });

  it("re-resolves when one axis is switched", async () => {
    stubApi(storefrontFor(twoAxisProduct));
    renderApp("/product/two-axis");

    const color = await screen.findByRole("group", { name: "اللون" });
    await userEvent.click(within(color).getByRole("button", { name: "أزرق" }));
    await userEvent.click(within(screen.getByRole("group", { name: "الحجم" })).getByRole("button", { name: "كبير" }));
    await userEvent.click(within(color).getByRole("button", { name: "أحمر" }));
    await userEvent.click(screen.getByRole("button", { name: /أضف إلى العربة/ }));

    await waitFor(() => expect(cartStorage.load()).toHaveLength(1));
    expect(cartStorage.load()[0].variantId).toBe(102);
  });

  it("refuses a combination whose variant is inactive", async () => {
    const product = {
      ...twoAxisProduct,
      variants: twoAxisProduct.variants.map((row) =>
        row.id === 104 ? { ...row, is_active: false } : row,
      ),
    };
    stubApi(storefrontFor(product));
    renderApp("/product/two-axis");

    const color = await screen.findByRole("group", { name: "اللون" });
    await userEvent.click(within(color).getByRole("button", { name: "أزرق" }));
    // Blue only pairs with small now, so large is not offered at all.
    expect(within(screen.getByRole("group", { name: "الحجم" })).getByRole("button", { name: "كبير" })).toBeDisabled();

    await userEvent.click(screen.getByRole("button", { name: /أضف إلى العربة/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent("اختر أحد الخيارات");
    expect(cartStorage.load()).toHaveLength(0);
  });
});

describe("option payload identity", () => {
  const edited = [
    {
      id: 1,
      name: "اللون",
      values: "قرمزي، أزرق",
      rows: [
        { id: 11, value: "أحمر" },
        { id: 12, value: "أزرق" },
      ],
    },
  ];

  it("carries the row ids so a rename is an update, not a delete", () => {
    expect(buildOptionsPayload(edited)).toEqual([
      {
        id: 1,
        name: "اللون",
        sort_order: 0,
        values: [
          { id: 11, value: "قرمزي", sort_order: 0 },
          { id: 12, value: "أزرق", sort_order: 1 },
        ],
      },
    ]);
  });

  it("marks an added value as new and keeps every existing variant", () => {
    const payload = buildOptionsPayload([
      { ...edited[0], values: "أحمر، أزرق، أخضر" },
      { id: 2, name: "الحجم", values: "صغير، كبير", rows: [{ id: 21, value: "صغير" }, { id: 22, value: "كبير" }] },
    ]);
    expect(payload[0].values[2]).toEqual({ value: "أخضر", sort_order: 2 });
    expect(variantsRemovedByOptions([RED_SMALL], payload)).toEqual([]);
  });

  it("removes only the variants that used a deleted value", () => {
    const blueSmall = variantRow(104, "أزرق / صغير", [12, 21]);
    const payload = buildOptionsPayload([
      { id: 1, name: "اللون", values: "أحمر", rows: [{ id: 11, value: "أحمر" }, { id: 12, value: "أزرق" }] },
      { id: 2, name: "الحجم", values: "صغير، كبير", rows: [{ id: 21, value: "صغير" }, { id: 22, value: "كبير" }] },
    ]);
    expect(variantsRemovedByOptions([RED_SMALL, blueSmall], payload)).toEqual([blueSmall]);
  });

  it("treats a dropped axis as destructive rather than merging combinations", () => {
    const payload = buildOptionsPayload([
      { id: 1, name: "اللون", values: "أحمر، أزرق", rows: [{ id: 11, value: "أحمر" }, { id: 12, value: "أزرق" }] },
    ]);
    expect(variantsRemovedByOptions([RED_SMALL], payload)).toEqual([RED_SMALL]);
  });
});

describe("saving options from the product editor", () => {
  const renderEditor = () => {
    authStorage.save("valid-token", ADMIN);
    const calls = stubApi({
      "/api/v1/auth/me": ADMIN,
      "/api/v1/admin/products/7": adminProduct,
      "PUT /api/v1/admin/products/7/options": OPTIONS,
      "/api/v1/admin/categories": page([]),
      "/api/v1/admin/products": page([]),
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

  const retypeColours = async (text) => {
    const fields = await screen.findAllByPlaceholderText("القيم مفصولة بفاصلة");
    await userEvent.clear(fields[0]);
    await userEvent.type(fields[0], text);
  };

  it("saves straight away when no variant is lost", async () => {
    const calls = renderEditor();
    await retypeColours("قرمزي، أزرق");
    await userEvent.click(screen.getByRole("button", { name: "حفظ الخيارات" }));

    const put = await waitFor(() => {
      const call = calls.find((row) => row.method === "PUT");
      expect(call).toBeTruthy();
      return call;
    });
    expect(JSON.parse(put.body)[0].values[0]).toEqual({ id: 11, value: "قرمزي", sort_order: 0 });
    expect(screen.queryByText(/غير متوافقة/)).toBeNull();
  });

  it("asks for confirmation, with the count, before a save that drops variants", async () => {
    const calls = renderEditor();
    await retypeColours("أزرق");
    await userEvent.click(screen.getByRole("button", { name: "حفظ الخيارات" }));

    expect(await screen.findByText(/حذف 1 نسخة غير متوافقة/)).toBeTruthy();
    expect(calls.find((row) => row.method === "PUT")).toBeFalsy();

    await userEvent.click(screen.getByRole("button", { name: "حفظ وحذف النسخ" }));
    await waitFor(() => expect(calls.find((row) => row.method === "PUT")).toBeTruthy());
  });

  it("keeps the variants when the confirmation is cancelled", async () => {
    const calls = renderEditor();
    await retypeColours("أزرق");
    await userEvent.click(screen.getByRole("button", { name: "حفظ الخيارات" }));
    await userEvent.click(await screen.findByRole("button", { name: "إلغاء" }));

    expect(calls.find((row) => row.method === "PUT")).toBeFalsy();
    expect(screen.getByText("أحمر / صغير")).toBeTruthy();
  });
});
