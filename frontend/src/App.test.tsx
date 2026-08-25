import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";
import { setStoredToken } from "./auth/token";

function renderApp() {
  return render(
    <MemoryRouter initialEntries={["/"]}>
      <App />
    </MemoryRouter>,
  );
}

describe("App root path redirect", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it("未登入時開啟根路徑導向登入頁", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    renderApp();

    expect(screen.getByRole("heading", { name: "登入" })).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("已登入時開啟根路徑導向文章列表", async () => {
    setStoredToken("valid-token");
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ items: [], total: 0, total_pages: 0, page: 1, page_size: 10 }),
    });
    vi.stubGlobal("fetch", fetchMock);

    renderApp();

    await waitFor(() => {
      expect(screen.getByText("尚無文章")).toBeInTheDocument();
    });
  });
});
