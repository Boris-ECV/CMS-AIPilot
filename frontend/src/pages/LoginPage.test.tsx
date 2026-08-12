import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LoginPage } from "./LoginPage";
import { ArticlesPlaceholder } from "./ArticlesPlaceholder";
import { getStoredToken } from "../auth/token";
import { ARTICLES_PATH, LOGIN_PATH } from "../routes";

function renderLoginPage() {
  return render(
    <MemoryRouter initialEntries={[LOGIN_PATH]}>
      <Routes>
        <Route path={LOGIN_PATH} element={<LoginPage />} />
        <Route path={ARTICLES_PATH} element={<ArticlesPlaceholder />} />
      </Routes>
    </MemoryRouter>,
  );
}

async function fillAndSubmit(username: string, password: string) {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("帳號"), username);
  await user.type(screen.getByLabelText("密碼"), password);
  await user.click(screen.getByRole("button", { name: "登入" }));
}

describe("LoginPage", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it("AC1: 登入成功時呼叫 POST /login、儲存 token 並導向 /articles", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ access_token: "jwt-token-123", token_type: "bearer" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    renderLoginPage();
    await fillAndSubmit("admin", "correct-password");

    await waitFor(() => {
      expect(screen.getByText(/Articles list placeholder/)).toBeInTheDocument();
    });

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/login"),
      expect.objectContaining({ method: "POST" }),
    );
    expect(getStoredToken()).toBe("jwt-token-123");
  });

  it("AC2: 帳密錯誤(401)顯示錯誤訊息、不儲存 token、停留在登入頁", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({ detail: "Invalid username or password" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    renderLoginPage();
    await fillAndSubmit("admin", "wrong-password");

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent("帳號或密碼錯誤");
    });

    expect(getStoredToken()).toBeNull();
    expect(screen.getByRole("button", { name: "登入" })).toBeInTheDocument();
  });

  it("AC3: 帳戶鎖定(429)顯示鎖定提示訊息", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 429,
      json: async () => ({
        detail: "Account locked. Try again in 900 seconds.",
        retry_after_seconds: 900,
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    renderLoginPage();
    await fillAndSubmit("admin", "correct-password");

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent("帳戶已被鎖定");
    });
    expect(getStoredToken()).toBeNull();
  });
});
