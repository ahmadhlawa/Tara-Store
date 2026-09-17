import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import ResourceScreen from "../admin/ResourceScreen.jsx";
import ProductEditorPage from "../admin/pages/ProductEditorPage.jsx";
import SettingsPage from "../admin/pages/SettingsPage.jsx";
import { adminApi } from "../api/adminApi.js";

function expectArabicOnly() {
  expect(screen.queryAllByLabelText(/English/i)).toHaveLength(0);
  expect(screen.queryByRole("button", { name: /AR → EN|EN → AR|Translate/i })).not.toBeInTheDocument();
  expect(screen.queryByText("استبدال المسودة بالترجمة")).not.toBeInTheDocument();
  expect(screen.queryByText("اعتماد الإنجليزية الحالية")).not.toBeInTheDocument();
}

describe("Arabic-only Admin saves", () => {
  it("saves Arabic with no translation controls or requests", async () => {
    const create = vi.fn().mockResolvedValue({ id: 1 });
    render(<ResourceScreen title="الأقسام" columns={[]} fields={[{ name: "name", title: "اسم القسم" }]}
      fetchList={async () => []} createItem={create} createLabel="إضافة قسم" />);
    await userEvent.click(screen.getByRole("button", { name: "إضافة قسم" }));
    expectArabicOnly();
    await userEvent.type(screen.getByLabelText("اسم القسم"), "شمعة");
    await userEvent.click(screen.getByRole("button", { name: "حفظ" }));
    await waitFor(() => expect(create).toHaveBeenCalledWith({ name: "شمعة" }));
    expect(globalThis.fetch).not.toHaveBeenCalled();
  });

  it("keeps product and option editing Arabic-only with ordinary save payloads", async () => {
    vi.spyOn(adminApi, "listCategories").mockResolvedValue({ items: [] });
    vi.spyOn(adminApi, "listProducts").mockResolvedValue({ items: [] });
    const create = vi.spyOn(adminApi, "createProduct").mockResolvedValue({ id: 2 });
    const options = vi.spyOn(adminApi, "replaceOptions").mockResolvedValue([]);
    render(<MemoryRouter><ProductEditorPage mode="create" /></MemoryRouter>);
    await userEvent.type(screen.getByLabelText("اسم المنتج"), "شمعة");
    await userEvent.click(screen.getByRole("button", { name: "+ إضافة خيار" }));
    await userEvent.type(screen.getByLabelText("اسم الخيار 1"), "الرائحة");
    await userEvent.type(screen.getByLabelText("قيمة 1 للخيار 1"), "ورد");
    expectArabicOnly();
    await userEvent.click(screen.getByRole("button", { name: "حفظ" }));
    await waitFor(() => expect(create).toHaveBeenCalled());
    expect(create.mock.calls[0][0]).not.toHaveProperty("translations");
    await waitFor(() => expect(options).toHaveBeenCalled());
    expect(options.mock.calls[0][1][0]).not.toHaveProperty("translations");
    expect(options.mock.calls[0][1][0].values[0]).not.toHaveProperty("translations");
    expect(globalThis.fetch).not.toHaveBeenCalled();
  });

  it("keeps store contact fields Arabic-only without translation requests", async () => {
    vi.spyOn(adminApi, "getSettings").mockResolvedValue({ id: 1, address: "رام الله", working_hours: "يومياً" });
    const save = vi.spyOn(adminApi, "updateSettings").mockResolvedValue({});
    render(<SettingsPage />);
    await screen.findByLabelText("العنوان");
    expectArabicOnly();
    await userEvent.click(screen.getByRole("button", { name: "حفظ" }));
    await waitFor(() => expect(save).toHaveBeenCalled());
    expect(save.mock.calls[0][0]).not.toHaveProperty("translations");
    expect(globalThis.fetch).not.toHaveBeenCalled();
  });
});
