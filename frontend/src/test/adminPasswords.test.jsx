import { describe, expect, it } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { AdminsPage } from "../admin/pages/AccountScreens.jsx";
import { page, stubApi } from "./utils.jsx";

const row = { id: 5, email: "admin@example.com", full_name: "Admin", role: "admin", is_active: true };

async function open(edit = false) {
  const calls = stubApi({
    "/api/v1/admin/admins": page(edit ? [row] : []),
    "POST /api/v1/admin/admins": row,
    "PATCH /api/v1/admin/admins/5": row,
  });
  render(<AdminsPage />);
  await screen.findByRole("heading", { name: "حسابات الإدارة" });
  if (edit) await screen.findByText(row.email);
  fireEvent.click(screen.getByRole("button", { name: edit ? "تعديل" : "حساب جديد" }));
  return { calls, dialog: within(screen.getByRole("dialog")) };
}

describe("Admin password confirmation", () => {
  it.each([false, true])("blocks mismatched passwords when editing=%s", async (edit) => {
    const { calls, dialog } = await open(edit);
    fireEvent.change(dialog.getByLabelText(edit ? "كلمة المرور الجديدة" : "كلمة المرور", { exact: true }), { target: { value: "ActualPassw0rd!" } });
    fireEvent.change(dialog.getByLabelText(edit ? "تأكيد كلمة المرور الجديدة" : "تأكيد كلمة المرور", { exact: true }), { target: { value: "DifferentPassw0rd!" } });
    fireEvent.click(dialog.getByRole("button", { name: "حفظ" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("غير متطابقين");
    expect(calls.filter((c) => c.method !== "GET")).toHaveLength(0);
  });

  it.each([false, true])("sends only the actual untrimmed password when editing=%s", async (edit) => {
    const { calls, dialog } = await open(edit);
    for (const name of edit ? ["كلمة المرور الجديدة", "تأكيد كلمة المرور الجديدة"] : ["كلمة المرور", "تأكيد كلمة المرور"]) {
      const control = dialog.getByLabelText(name, { exact: true });
      expect(control).toHaveAttribute("type", "password");
      expect(control).toHaveAttribute("autocomplete", "new-password");
      fireEvent.change(control, { target: { value: " ActualPassw0rd! " } });
    }
    fireEvent.click(dialog.getByRole("button", { name: "حفظ" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    const payload = JSON.parse(calls.find((c) => c.method === (edit ? "PATCH" : "POST")).body);
    expect(payload.password).toBe(" ActualPassw0rd! ");
    expect(payload).not.toHaveProperty("confirm_password");
  });

  it("keeps the existing password on an edit with both fields empty", async () => {
    const { calls, dialog } = await open(true);
    fireEvent.click(dialog.getByRole("button", { name: "حفظ" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    const payload = JSON.parse(calls.find((c) => c.method === "PATCH").body);
    expect(payload).not.toHaveProperty("password");
    expect(payload).not.toHaveProperty("confirm_password");
  });

  it("requires a password for creation", async () => {
    const { calls, dialog } = await open();
    fireEvent.click(dialog.getByRole("button", { name: "حفظ" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("أدخل كلمة المرور");
    expect(calls.filter((c) => c.method !== "GET")).toHaveLength(0);
  });
});
