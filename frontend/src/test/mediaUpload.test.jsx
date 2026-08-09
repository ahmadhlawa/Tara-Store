import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import MediaPage from "../admin/pages/MediaPage.jsx";
import { page, respond, stubApi } from "./utils.jsx";

const asset = (id, name) => ({
  id,
  original_filename: name,
  stored_key: `2026/08/${id}.png`,
  content_type: "image/png",
  size_bytes: 2048,
  url: `/media/2026/08/${id}.png`,
  storage_provider: "local",
  uploaded_by_id: 1,
  created_at: "2026-08-01T00:00:00Z",
});

const png = (name) => new File([new Uint8Array([0x89, 0x50, 0x4e, 0x47])], name, { type: "image/png" });

/**
 * A media API that behaves like the real one: it keeps a library, rejects a second
 * upload of a name it already holds, and can be told to fail specific files.
 */
function setupApi({ existing = [], failOnce = [], failAlways = [] } = {}) {
  const library = existing.map((name, index) => asset(index + 1, name));
  const transient = new Set(failOnce);
  const posted = [];

  stubApi({
    "/api/v1/admin/media": () => page([...library].reverse()),
    "POST /api/v1/admin/media": ({ init }) => {
      const file = init.body.get("file");
      posted.push(file.name);
      if (transient.has(file.name)) {
        transient.delete(file.name);
        return respond(500, { error: { code: "server_error", message: "خطأ في الخادم." } });
      }
      if (failAlways.includes(file.name)) {
        return respond(500, { error: { code: "server_error", message: "خطأ في الخادم." } });
      }
      if (library.some((item) => item.original_filename === file.name)) {
        return respond(409, {
          error: { code: "duplicate_filename", message: "يوجد ملف بهذا الاسم بالفعل." },
        });
      }
      const created = asset(library.length + 1, file.name);
      library.push(created);
      return respond(201, created);
    },
  });

  return { library, posted };
}

const renderPage = async () => {
  render(<MediaPage />);
  await screen.findByText("اسحب الصور إلى هنا، أو");
};

const fileInput = () => screen.getByLabelText("اختيار صور للرفع");
const queueItems = () => screen.queryAllByTestId("upload-item");
const rowFor = (name) => queueItems().find((row) => within(row).queryByText(name));
const summary = () => screen.getByTestId("upload-summary").textContent;

const drop = (files) =>
  fireEvent.drop(screen.getByTestId("media-dropzone"), { dataTransfer: { files } });

describe("admin bulk media upload", () => {
  it("searches the library and clearing restores the full list", async () => {
    const calls = stubApi({
      "/api/v1/admin/media": ({ path }) =>
        path.includes("q=VST") ? page([asset(1, "VST-1001-01.jpg")]) : page([asset(2, "other.jpg")]),
    });
    await renderPage();

    const search = screen.getByLabelText("بحث باسم الملف");
    await userEvent.type(search, "VST");
    expect(await screen.findByText("VST-1001-01.jpg")).toBeInTheDocument();
    await userEvent.clear(search);
    expect(await screen.findByText("other.jpg")).toBeInTheDocument();
    expect(calls.some((call) => call.path.includes("q=VST"))).toBe(true);
  });

  it("renames an asset and keeps the editor open on failure or cancel", async () => {
    let renamed = false;
    stubApi({
      "/api/v1/admin/media": () => page([asset(1, renamed ? "NEW.jpg" : "OLD.jpg")]),
      "PATCH /api/v1/admin/media/1": ({ init }) => {
        const { original_filename } = JSON.parse(init.body);
        if (original_filename === "taken.jpg") {
          return respond(409, { error: { code: "duplicate_filename", message: "الاسم مستخدم بالفعل." } });
        }
        renamed = true;
        return asset(1, original_filename);
      },
    });
    await renderPage();

    await userEvent.click(await screen.findByRole("button", { name: "تعديل الاسم" }));
    const editor = screen.getByLabelText("اسم الملف");
    await userEvent.clear(editor);
    await userEvent.type(editor, "taken.jpg");
    await userEvent.click(screen.getByRole("button", { name: "حفظ" }));
    expect(await screen.findByText("الاسم مستخدم بالفعل.")).toBeInTheDocument();
    expect(screen.getByLabelText("اسم الملف")).toHaveValue("taken.jpg");

    await userEvent.clear(editor);
    await userEvent.type(editor, "NEW.jpg");
    await userEvent.click(screen.getByRole("button", { name: "حفظ" }));
    expect(await screen.findByText("NEW.jpg")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "تعديل الاسم" }));
    await userEvent.click(screen.getByRole("button", { name: "إلغاء" }));
    expect(screen.queryByLabelText("اسم الملف")).not.toBeInTheDocument();
  });

  it("queues every file chosen from the picker and uploads them all", async () => {
    const { library } = setupApi();
    await renderPage();

    await userEvent.upload(fileInput(), [png("a.png"), png("b.png"), png("c.png")]);

    expect(queueItems()).toHaveLength(3);
    await waitFor(() => expect(summary()).toContain("3 تم رفعه"));
    expect(library.map((item) => item.original_filename)).toEqual(["a.png", "b.png", "c.png"]);
  });

  it("queues every dropped file", async () => {
    setupApi();
    await renderPage();

    drop([png("one.png"), png("two.png"), png("three.png")]);

    expect(queueItems()).toHaveLength(3);
    expect(queueItems().map((row) => row.textContent)).toEqual(
      expect.arrayContaining([expect.stringContaining("one.png")]),
    );
    await waitFor(() => expect(summary()).toContain("3 تم رفعه"));
  });

  it("shows uploaded assets in the library with their original filenames", async () => {
    const { posted } = setupApi();
    await renderPage();

    await userEvent.upload(fileInput(), [png("صورة-المنتج.png"), png("second.png")]);

    await waitFor(() => expect(summary()).toContain("2 تم رفعه"));
    // The client filename is what the catalog importer resolves by — it must survive.
    expect(posted).toEqual(["صورة-المنتج.png", "second.png"]);
    // Once refreshed the name appears twice: in the queue row and on the library card.
    await waitFor(() => expect(screen.getAllByText("صورة-المنتج.png")).toHaveLength(2));
    expect(screen.getAllByText("second.png")).toHaveLength(2);
  });

  it("keeps uploading the rest when one file fails, then retries the failure", async () => {
    setupApi({ failOnce: ["bad.png"] });
    await renderPage();

    await userEvent.upload(fileInput(), [
      png("ok1.png"),
      png("bad.png"),
      png("ok2.png"),
      png("ok3.png"),
    ]);

    await waitFor(() => expect(summary()).toBe("3 تم رفعه، 1 فشل"));
    expect(within(rowFor("bad.png")).getByText("خطأ في الخادم.")).toBeTruthy();

    await userEvent.click(within(rowFor("bad.png")).getByRole("button", { name: "إعادة المحاولة" }));
    await waitFor(() => expect(summary()).toBe("4 تم رفعه، 0 فشل"));
  });

  it("rejects a filename the library already holds without stopping the queue", async () => {
    const { library } = setupApi({ existing: ["hero.png"] });
    await renderPage();

    await userEvent.upload(fileInput(), [png("hero.png"), png("fresh.png")]);

    await waitFor(() => expect(summary()).toBe("1 تم رفعه، 1 فشل"));
    expect(within(rowFor("hero.png")).getByText("يوجد ملف بهذا الاسم بالفعل.")).toBeTruthy();
    // No ambiguous second row for the same name, and the original is untouched.
    expect(library.filter((item) => item.original_filename === "hero.png")).toHaveLength(1);
  });

  it("marks an unsupported file failed locally and uploads the valid ones", async () => {
    const { posted } = setupApi();
    await renderPage();

    drop([png("good.png"), new File(["x"], "notes.txt", { type: "text/plain" })]);

    await waitFor(() => expect(summary()).toBe("1 تم رفعه، 1 فشل"));
    expect(within(rowFor("notes.txt")).getByText("نوع الملف غير مدعوم.")).toBeTruthy();
    expect(posted).toEqual(["good.png"]);
  });
});
