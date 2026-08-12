import { apiClient } from "./client";

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
}

export async function login(credentials: LoginRequest): Promise<LoginResponse> {
  return apiClient.request<LoginResponse>("/login", {
    method: "POST",
    body: JSON.stringify(credentials),
  });
}
