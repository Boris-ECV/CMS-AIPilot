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

  describe("刪除確認互動(SDLCAIP1-14)", () => {
    function makeFetchMock(
      handleDelete: (url: string, init?: RequestInit) => Promise<unknown> | unknown,
    ) {
      const items = [
        { id: "42", title: "文章 42", published_at: "2026-01-01T00:00:00" },
      ];
      return vi.fn().mockImplementation((url: string, init?: RequestInit) => {
        if (init?.method === "DELETE") {
          return handleDelete(url, init);
        }
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => makeListResponse({ items, total: 1, total_pages: 1 }),
        });
      });
    }

    async function renderWithArticleAndClickDelete() {
      renderArticlesList();
      await waitFor(() => {
        expect(screen.getByText("文章 42")).toBeInTheDocument();
      });
      const user = userEvent.setup();
      await user.click(screen.getByTestId("delete-article-42"));
      return user;
    }

    it("SDLCAIP1-14 AC1: 確認刪除且 API 回 204 時,呼叫 DELETE /articles/{id} 並就地移除該文章", async () => {
      const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
      const fetchMock = makeFetchMock(() =>
        Promise.resolve({ ok: true, status: 204, json: async () => undefined }),
      );
      vi.stubGlobal("fetch", fetchMock);

      await renderWithArticleAndClickDelete();

      expect(confirmSpy).toHaveBeenCalledWith("確定要刪除文章「文章 42」嗎?");
      await waitFor(() => {
        expect(screen.getByText("尚無文章")).toBeInTheDocument();
      });
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/articles/42"),
        expect.objectContaining({ method: "DELETE" }),
      );
    });

    it("SDLCAIP1-14 AC2: 取消確認時不呼叫刪除 API,文章仍在列表", async () => {
      vi.spyOn(window, "confirm").mockReturnValue(false);
      const deleteHandler = vi.fn();
      const fetchMock = makeFetchMock(deleteHandler);
      vi.stubGlobal("fetch", fetchMock);

      await renderWithArticleAndClickDelete();

      expect(deleteHandler).not.toHaveBeenCalled();
      expect(screen.getByText("文章 42")).toBeInTheDocument();
    });

    it("SDLCAIP1-14 AC3: API 回 404 時視為已不存在,從列表移除並顯示非阻斷提示", async () => {
      vi.spyOn(window, "confirm").mockReturnValue(true);
      const fetchMock = makeFetchMock(() =>
        Promise.resolve({
          ok: false,
          status: 404,
          json: async () => ({ detail: "Article not found" }),
        }),
      );
      vi.stubGlobal("fetch", fetchMock);

      await renderWithArticleAndClickDelete();

      await waitFor(() => {
        expect(screen.getByText("尚無文章")).toBeInTheDocument();
      });
      expect(screen.getByRole("status")).toHaveTextContent(
        "該文章已不存在,已從列表移除",
      );
    });

    it("SDLCAIP1-14 AC4: API 回 401 時清除 token 並導向登入頁,不顯示文章列表資料", async () => {
      vi.spyOn(window, "confirm").mockReturnValue(true);
      const fetchMock = makeFetchMock(() =>
        Promise.resolve({
          ok: false,
          status: 401,
          json: async () => ({ detail: "Not authenticated" }),
        }),
      );
      vi.stubGlobal("fetch", fetchMock);

      await renderWithArticleAndClickDelete();

      await waitFor(() => {
        expect(screen.getByRole("heading", { name: "登入" })).toBeInTheDocument();
      });
      expect(getStoredToken()).toBeNull();
      expect(screen.queryByRole("table")).not.toBeInTheDocument();
    });

    it("SDLCAIP1-14 AC5: API 回 502(靜態頁清除失敗)時視為已刪除,從列表移除並顯示非阻斷警示", async () => {
      vi.spyOn(window, "confirm").mockReturnValue(true);
      const fetchMock = makeFetchMock(() =>
        Promise.resolve({
          ok: false,
          status: 502,
          json: async () => ({
            error_code: "STATIC_PAGE_DELETION_FAILED",
            detail: "Article deleted but its static page could not be removed from S3.",
            article_id: "42",
          }),
        }),
      );
      vi.stubGlobal("fetch", fetchMock);

      await renderWithArticleAndClickDelete();

      await waitFor(() => {
        expect(screen.getByText("尚無文章")).toBeInTheDocument();
      });
      expect(screen.getByRole("status")).toHaveTextContent(
        "文章已刪除,但靜態頁清除可能失敗,請確認網站頁面",
      );
    });

    it("SDLCAIP1-14 AC6: 非預期錯誤(如 500)時文章仍保留在列表,顯示可重試的通用錯誤訊息", async () => {
      vi.spyOn(window, "confirm").mockReturnValue(true);
      const fetchMock = makeFetchMock(() =>
        Promise.resolve({
          ok: false,
          status: 500,
          json: async () => ({ detail: "Internal Server Error" }),
        }),
      );
      vi.stubGlobal("fetch", fetchMock);

      await renderWithArticleAndClickDelete();

      await waitFor(() => {
        expect(fetchMock).toHaveBeenCalledWith(
          expect.stringContaining("/articles/42"),
          expect.objectContaining({ method: "DELETE" }),
        );
      });
      // AC6 requires the article to remain visible in the list alongside
      // a retryable generic error message.
      await waitFor(() => {
        expect(screen.getByText("刪除文章失敗,請稍後再試")).toBeInTheDocument();
      });
      expect(screen.getByText("文章 42")).toBeInTheDocument();
    });
  });
});
