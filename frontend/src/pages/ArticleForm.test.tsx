import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ArticleForm } from "./ArticleForm";
import { setStoredToken, getStoredToken } from "../auth/token";
import { ARTICLES_PATH, ARTICLE_NEW_PATH, LOGIN_PATH, editPath } from "../routes";

function renderArticleForm(initialPath: string) {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path={LOGIN_PATH} element={<h1>登入</h1>} />
        <Route path={ARTICLES_PATH} element={<h1>文章列表</h1>} />
        <Route path={ARTICLE_NEW_PATH} element={<ArticleForm />} />
        <Route path="/articles/:id/edit" element={<ArticleForm />} />
      </Routes>
    </MemoryRouter>,
  );
}

function jsonResponse(status: number, body: unknown) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  });
}

async function fillValidForm() {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("標題"), "我的標題");
  await user.type(screen.getByLabelText("內容"), "我的內容");
  const dateInput = screen.getByLabelText("發布時間");
  await user.clear(dateInput);
  await user.type(dateInput, "2026-08-13T10:00");
  return user;
}

describe("ArticleForm", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
    setStoredToken("valid-token");
  });

  it("AC1: 新增模式開啟表單時,標題/內容/發布時間皆為空,不預先帶入任何資料", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    renderArticleForm(ARTICLE_NEW_PATH);

    expect(await screen.findByRole("heading", { name: "新增文章" })).toBeInTheDocument();
    expect(screen.getByLabelText("標題")).toHaveValue("");
    expect(screen.getByLabelText("內容")).toHaveValue("");
    expect(screen.getByLabelText("發布時間")).toHaveValue("");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("AC2: 編輯模式開啟表單時,GET /articles/{id} 回 200 會將標題/內容/發布時間預先帶入表單", async () => {
    const fetchMock = vi.fn().mockImplementation(() =>
      jsonResponse(200, {
        id: "42",
        title: "既有標題",
        content: "既有內容",
        published_at: "2026-01-01T09:30:00",
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    renderArticleForm(editPath("42"));

    await waitFor(() => {
      expect(screen.getByLabelText("標題")).toHaveValue("既有標題");
    });
    expect(screen.getByLabelText("內容")).toHaveValue("既有內容");
    expect(screen.getByLabelText("發布時間")).toHaveValue("2026-01-01T09:30");
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/articles/42"),
      expect.anything(),
    );
  });

  it("AC3: 編輯模式下 GET /articles/{id} 回 404 時顯示找不到文章的錯誤訊息,且不顯示可送出的表單欄位", async () => {
    const fetchMock = vi.fn().mockImplementation(() =>
      jsonResponse(404, { detail: "Not Found" }),
    );
    vi.stubGlobal("fetch", fetchMock);

    renderArticleForm(editPath("does-not-exist"));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent("找不到文章");
    });
    expect(screen.queryByLabelText("標題")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("內容")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "儲存" })).not.toBeInTheDocument();
  });

  it("AC4: 新增模式下填寫有效資料送出,呼叫 POST /articles 帶入 title/content/published_at,201 後導向文章列表頁", async () => {
    const fetchMock = vi.fn().mockImplementation(() =>
      jsonResponse(201, {
        id: "99",
        title: "我的標題",
        content: "我的內容",
        published_at: "2026-08-13T10:00:00",
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    renderArticleForm(ARTICLE_NEW_PATH);
    await screen.findByRole("heading", { name: "新增文章" });
    const user = await fillValidForm();
    await user.click(screen.getByRole("button", { name: "儲存" }));

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "文章列表" })).toBeInTheDocument();
    });

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/articles"),
      expect.objectContaining({ method: "POST" }),
    );
    const [, init] = fetchMock.mock.calls[0];
    const body = JSON.parse(init.body as string);
    expect(body).toEqual({
      title: "我的標題",
      content: "我的內容",
      published_at: "2026-08-13T10:00",
    });
  });

  it("AC5: 編輯模式下修改欄位後送出,呼叫 PUT /articles/{id} 帶入更新後的資料,200 後導向文章列表頁", async () => {
    const fetchMock = vi.fn().mockImplementation((_url: string, init?: RequestInit) => {
      if (init?.method === "PUT") {
        return jsonResponse(200, {
          id: "42",
          title: "更新後標題",
          content: "既有內容",
          published_at: "2026-01-01T09:30:00",
        });
      }
      return jsonResponse(200, {
        id: "42",
        title: "既有標題",
        content: "既有內容",
        published_at: "2026-01-01T09:30:00",
      });
    });
    vi.stubGlobal("fetch", fetchMock);

    renderArticleForm(editPath("42"));
    await waitFor(() => {
      expect(screen.getByLabelText("標題")).toHaveValue("既有標題");
    });

    const user = userEvent.setup();
    const titleInput = screen.getByLabelText("標題");
    await user.clear(titleInput);
    await user.type(titleInput, "更新後標題");
    await user.click(screen.getByRole("button", { name: "儲存" }));

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "文章列表" })).toBeInTheDocument();
    });

    const putCall = fetchMock.mock.calls.find(
      (call: unknown[]) => (call[1] as RequestInit | undefined)?.method === "PUT",
    );
    expect(putCall).toBeDefined();
    expect(putCall![0]).toContain("/articles/42");
    const body = JSON.parse((putCall![1] as RequestInit).body as string);
    expect(body.title).toBe("更新後標題");
  });

  it("AC6: 標題留空送出時顯示「請輸入標題」錯誤,不導向,已填寫的其他欄位保留", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    renderArticleForm(ARTICLE_NEW_PATH);
    await screen.findByRole("heading", { name: "新增文章" });

    const user = userEvent.setup();
    await user.type(screen.getByLabelText("內容"), "我的內容");
    const dateInput = screen.getByLabelText("發布時間");
    await user.type(dateInput, "2026-08-13T10:00");
    await user.click(screen.getByRole("button", { name: "儲存" }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent("請輸入標題");
    });
    expect(screen.getByRole("heading", { name: "新增文章" })).toBeInTheDocument();
    expect(screen.getByLabelText("內容")).toHaveValue("我的內容");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("AC7: 內容留空送出時顯示「請輸入內容」錯誤,不導向,已填寫的其他欄位保留", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    renderArticleForm(ARTICLE_NEW_PATH);
    await screen.findByRole("heading", { name: "新增文章" });

    const user = userEvent.setup();
    await user.type(screen.getByLabelText("標題"), "我的標題");
    const dateInput = screen.getByLabelText("發布時間");
    await user.type(dateInput, "2026-08-13T10:00");
    await user.click(screen.getByRole("button", { name: "儲存" }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent("請輸入內容");
    });
    expect(screen.getByRole("heading", { name: "新增文章" })).toBeInTheDocument();
    expect(screen.getByLabelText("標題")).toHaveValue("我的標題");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("AC8: 後端回 422 時顯示通用的「輸入無效」訊息,不導向,欄位資料保留", async () => {
    const fetchMock = vi.fn().mockImplementation(() =>
      jsonResponse(422, { detail: "Validation error" }),
    );
    vi.stubGlobal("fetch", fetchMock);

    renderArticleForm(ARTICLE_NEW_PATH);
    await screen.findByRole("heading", { name: "新增文章" });
    const user = await fillValidForm();
    await user.click(screen.getByRole("button", { name: "儲存" }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(
        "文章儲存失敗,請確認欄位內容後再試",
      );
    });
    expect(screen.getByRole("heading", { name: "新增文章" })).toBeInTheDocument();
    expect(screen.getByLabelText("標題")).toHaveValue("我的標題");
  });

  it("AC9: 後端回 502(靜態頁面產生失敗)時顯示明確失敗訊息且不聲稱已儲存成功,不導向", async () => {
    const fetchMock = vi.fn().mockImplementation(() =>
      jsonResponse(502, { detail: "STATIC_PAGE_GENERATION_FAILED" }),
    );
    vi.stubGlobal("fetch", fetchMock);

    renderArticleForm(ARTICLE_NEW_PATH);
    await screen.findByRole("heading", { name: "新增文章" });
    const user = await fillValidForm();
    await user.click(screen.getByRole("button", { name: "儲存" }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });
    const alertText = screen.getByRole("alert").textContent ?? "";
    expect(alertText).not.toContain("儲存成功");
    expect(alertText.length).toBeGreaterThan(0);
    expect(screen.getByRole("heading", { name: "新增文章" })).toBeInTheDocument();
  });

  it("AC10: 送出時後端回 401,清除已儲存的 token 並導向登入頁", async () => {
    const fetchMock = vi.fn().mockImplementation(() =>
      jsonResponse(401, { detail: "Not authenticated" }),
    );
    vi.stubGlobal("fetch", fetchMock);

    renderArticleForm(ARTICLE_NEW_PATH);
    await screen.findByRole("heading", { name: "新增文章" });
    const user = await fillValidForm();
    await user.click(screen.getByRole("button", { name: "儲存" }));

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "登入" })).toBeInTheDocument();
    });
    expect(getStoredToken()).toBeNull();
  });

  it("AC11: 點擊取消時導向文章列表頁,且不呼叫 POST/PUT", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    renderArticleForm(ARTICLE_NEW_PATH);
    await screen.findByRole("heading", { name: "新增文章" });

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "取消" }));

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "文章列表" })).toBeInTheDocument();
    });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("邊界情況:編輯模式下 GET /articles/{id} 回 401 時清除 token 並導向登入頁", async () => {
    const fetchMock = vi.fn().mockImplementation(() =>
      jsonResponse(401, { detail: "Not authenticated" }),
    );
    vi.stubGlobal("fetch", fetchMock);

    renderArticleForm(editPath("42"));

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "登入" })).toBeInTheDocument();
    });
    expect(getStoredToken()).toBeNull();
  });
});
