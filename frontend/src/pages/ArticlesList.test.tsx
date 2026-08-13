import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ArticlesList } from "./ArticlesList";
import { setStoredToken, getStoredToken } from "../auth/token";
import { ARTICLES_PATH, LOGIN_PATH } from "../routes";

function renderArticlesList() {
  return render(
    <MemoryRouter initialEntries={[ARTICLES_PATH]}>
      <Routes>
        <Route path={LOGIN_PATH} element={<h1>登入</h1>} />
        <Route path={ARTICLES_PATH} element={<ArticlesList />} />
      </Routes>
    </MemoryRouter>,
  );
}

function makeListResponse(overrides: Partial<{
  items: { id: string; title: string; published_at: string }[];
  total: number;
  total_pages: number;
  page: number;
  page_size: number;
}> = {}) {
  return {
    items: [],
    total: 0,
    total_pages: 0,
    page: 1,
    page_size: 10,
    ...overrides,
  };
}

describe("ArticlesList", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
    setStoredToken("valid-token");
  });

  it("AC1: 有資料時依 API 回傳順序顯示每篇文章的標題與 published_at", async () => {
    const items = [
      { id: "1", title: "第一篇文章", published_at: "2026-02-01T00:00:00" },
      { id: "2", title: "第二篇文章", published_at: "2026-01-01T00:00:00" },
    ];
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => makeListResponse({ items, total: 2, total_pages: 1 }),
    });
    vi.stubGlobal("fetch", fetchMock);

    renderArticlesList();

    await waitFor(() => {
      expect(screen.getByText("第一篇文章")).toBeInTheDocument();
    });
    const rows = screen.getAllByRole("row").slice(1); // skip header row
    expect(rows).toHaveLength(2);
    expect(within(rows[0]).getByText("第一篇文章")).toBeInTheDocument();
    expect(within(rows[0]).getByText("2026-02-01T00:00:00")).toBeInTheDocument();
    expect(within(rows[1]).getByText("第二篇文章")).toBeInTheDocument();
  });

  it("AC2: 空列表時顯示「尚無文章」空狀態,不顯示表格列", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => makeListResponse(),
    });
    vi.stubGlobal("fetch", fetchMock);

    renderArticlesList();

    await waitFor(() => {
      expect(screen.getByText("尚無文章")).toBeInTheDocument();
    });
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("AC3: API 回 401 時清除 token 並導向登入頁,不顯示文章資料", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({ detail: "Not authenticated" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    renderArticlesList();

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "登入" })).toBeInTheDocument();
    });
    expect(getStoredToken()).toBeNull();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("AC4: 分頁行為與 API 回傳一致,點擊下一頁以 page=2 重新呼叫 API 並更新畫面", async () => {
    const page1Items = Array.from({ length: 10 }, (_, i) => ({
      id: `p1-${i}`,
      title: `文章 ${i}`,
      published_at: "2026-01-01T00:00:00",
    }));
    const page2Items = [
      { id: "p2-0", title: "第 11 篇", published_at: "2025-12-01T00:00:00" },
    ];
    const fetchMock = vi.fn().mockImplementation((url: string) => {
      if (url.includes("page=2")) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () =>
            makeListResponse({ items: page2Items, total: 11, total_pages: 2, page: 2 }),
        });
      }
      return Promise.resolve({
        ok: true,
        status: 200,
        json: async () =>
          makeListResponse({ items: page1Items, total: 11, total_pages: 2, page: 1 }),
      });
    });
    vi.stubGlobal("fetch", fetchMock);

    renderArticlesList();

    await waitFor(() => {
      expect(screen.getAllByRole("row")).toHaveLength(11); // header + 10 rows
    });

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "下一頁" }));

    await waitFor(() => {
      expect(screen.getByText("第 11 篇")).toBeInTheDocument();
    });
    expect(screen.getAllByRole("row")).toHaveLength(2); // header + 1 row
    expect(fetchMock).toHaveBeenLastCalledWith(
      expect.stringContaining("page=2"),
      expect.anything(),
    );
  });

  it("AC5: 每列提供編輯連結與刪除按鈕入口", async () => {
    const items = [{ id: "42", title: "文章 42", published_at: "2026-01-01T00:00:00" }];
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => makeListResponse({ items, total: 1, total_pages: 1 }),
    });
    vi.stubGlobal("fetch", fetchMock);

    renderArticlesList();

    await waitFor(() => {
      expect(screen.getByText("文章 42")).toBeInTheDocument();
    });

    const editLink = screen.getByRole("link", { name: "編輯" });
    expect(editLink).toHaveAttribute("href", "/articles/42/edit");

    const deleteButton = screen.getByTestId("delete-article-42");
    expect(deleteButton.tagName).toBe("BUTTON");
  });
});
