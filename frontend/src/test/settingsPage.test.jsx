import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import SettingsPage from "../admin/pages/SettingsPage.jsx";

vi.mock("../api/adminApi.js", () => ({
  adminApi: {
    getSettings: vi.fn().mockResolvedValue({
      phone: "970594402699",
      whatsapp: "970594402699",
      working_hours: "من الساعة العاشرة صباحا حتى السابعة مساء",
      instagram_visible: true,
      facebook_visible: true,
      tiktok_visible: true,
      youtube_visible: true,
    }),
    updateSettings: vi.fn(),
  },
}));

describe("روابط المتجر", () => {
  it("limits owner controls to contact and independently visible social links", async () => {
    render(<SettingsPage />);

    expect(await screen.findByRole("heading", { name: "روابط المتجر" })).toBeInTheDocument();
    expect(screen.getByText("بيانات التواصل")).toBeInTheDocument();
    expect(screen.getByText("روابط التواصل الاجتماعي")).toBeInTheDocument();
    expect(screen.getByLabelText("الهاتف")).toHaveValue("970594402699");
    expect(screen.getByLabelText("واتساب")).toHaveValue("970594402699");
    expect(screen.getByLabelText("ساعات العمل")).toHaveValue("من الساعة العاشرة صباحا حتى السابعة مساء");
    expect(screen.getAllByLabelText("إظهار في الموقع")).toHaveLength(4);
    expect(screen.queryByText("وضع الصيانة")).not.toBeInTheDocument();
    expect(screen.queryByText("العملة")).not.toBeInTheDocument();
    expect(screen.queryByText("الفوترة")).not.toBeInTheDocument();
  });
});
