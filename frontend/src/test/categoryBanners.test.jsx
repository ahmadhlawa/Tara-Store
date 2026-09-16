import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import CategoryBannersPage from "../admin/pages/CategoryBannersPage.jsx";
import { page, stubApi } from "./utils.jsx";

const root = { id: 1, name: "هدايا", slug: "gifts", parent_id: null, image_url: "/media/category.jpg", banner_image_url: null };
const child = { ...root, id: 2, name: "فرعي", slug: "child", parent_id: 1 };
const media = { id: 9, original_filename: "banner.jpg", content_type: "image/jpeg", size_bytes: 1000, url: "/media/banner.jpg", created_at: "2026-09-01T00:00:00Z" };

describe("category banners admin page", () => {
  it("lists roots only and saves a single Media Library selection", async () => {
    const calls = stubApi({
      "/api/v1/admin/categories": page([root, child]),
      "/api/v1/admin/media": page([media]),
      "PATCH /api/v1/admin/categories/1": { ...root, banner_image_url: media.url },
    });
    render(<CategoryBannersPage />);

    expect(screen.getByText(/2100 × 500/)).toBeInTheDocument();
    expect(await screen.findByText("هدايا")).toBeInTheDocument();
    expect(screen.queryByText("فرعي")).not.toBeInTheDocument();
    expect(screen.getByText("لا يوجد بانر مخصّص")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "اختيار من مكتبة الوسائط" }));
    const dialog = await screen.findByRole("dialog", { name: "مكتبة الوسائط" });
    await userEvent.click(await within(dialog).findByText("banner.jpg"));
    await userEvent.click(within(dialog).getByRole("button", { name: "اختيار" }));

    await waitFor(() => expect(calls.some((call) => call.method === "PATCH" && JSON.parse(call.body).banner_image_url === media.url)).toBe(true));
    expect(await screen.findByRole("button", { name: "إزالة البانر" })).toBeInTheDocument();
  });
});
