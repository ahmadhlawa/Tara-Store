import { render } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";
import AdminApp from "../admin/AdminApp.jsx";

describe("Admin theme boundary", () => {
  it("wraps the standalone login route in the Admin root, outside public theme scope", async () => {
    const { container } = render(
      <MemoryRouter initialEntries={["/admin/login"]}>
        <Routes>
          <Route path="/admin/*" element={<AdminApp />} />
        </Routes>
      </MemoryRouter>,
    );

    const adminRoot = container.querySelector(".admin-app");
    expect(adminRoot).toBeInTheDocument();
    expect(adminRoot.closest(".vs-public")).toBeNull();
    expect(adminRoot.querySelector("form")).toBeInTheDocument();
  });
});
