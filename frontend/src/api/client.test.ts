import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "./client";
import { setStoredToken } from "../auth/token";

describe("apiClient.request", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it("AC5: 已登入時,API 呼叫帶上 Authorization: Bearer <token> header", async () => {
    setStoredToken("stored-jwt-abc");
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ items: [] }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await apiClient.request("/articles");

    const [, init] = fetchMock.mock.calls[0];
    const headers = init.headers as Headers;
    expect(headers.get("Authorization")).toBe("Bearer stored-jwt-abc");
  });

  it("未登入(無 token)時不帶 Authorization header", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ items: [] }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await apiClient.request("/articles");

    const [, init] = fetchMock.mock.calls[0];
    const headers = init.headers as Headers;
    expect(headers.get("Authorization")).toBeNull();
  });
});
