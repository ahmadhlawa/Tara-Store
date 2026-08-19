import { describe, expect, it } from "vitest";
import { automaticSeo } from "../admin/seo.js";

describe("automaticSeo", () => {
  it("derives sanitized metadata from ordinary content", () => {
    expect(automaticSeo({
      title: "  عنوان المنتج  ",
      summary: "<p>وصف <strong>قصير</strong>&nbsp; للمنتج</p>",
    })).toEqual({ seo_title: "عنوان المنتج", seo_description: "وصف قصير للمنتج" });
  });

  it("preserves non-empty stored metadata while filling blanks", () => {
    expect(automaticSeo({
      title: "عنوان جديد",
      description: "وصف جديد",
      existing: { seo_title: "عنوان محفوظ", seo_description: "" },
    })).toEqual({ seo_title: "عنوان محفوظ", seo_description: "وصف جديد" });
  });
});
