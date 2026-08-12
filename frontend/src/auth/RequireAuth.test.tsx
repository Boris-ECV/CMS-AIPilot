import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { RequireAuth } from "./RequireAuth";
import { ArticlesList } from "../pages/ArticlesList";
import { LoginPage } from "../pages/LoginPage";
import { setStoredToken } from "./token";
import { ARTICLES_PATH, LOGIN_PATH } from "../routes";

function renderProtectedRoute() {
  return render(
    <MemoryRouter initialEntries={[ARTICLES_PATH]}>
      <Routes>
        <Route path={LOGIN_PATH} element={<LoginPage />} />
        <Route element={<RequireAuth />}>
          <Route path={ARTICLES_PATH} element={<ArticlesList />} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

describe("RequireAuth", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it("AC4: 未登入時導向登入頁,且不發出受保護頁面的 API 請求", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    renderProtectedRoute();

    expect(screen.getByRole("heading", { name: "登入" })).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("已登入時可看到受保護頁面內容", async () => {
    setStoredToken("valid-token");
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ items: [], total: 0, total_pages: 0, page: 1, page_size: 10 }),
    });
    vi.stubGlobal("fetch", fetchMock);

    renderProtectedRoute();

    await waitFor(() => {
      expect(screen.getByText("尚無文章")).toBeInTheDocument();
    });
  });
});
