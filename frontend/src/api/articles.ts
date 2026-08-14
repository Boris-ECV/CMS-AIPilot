import { apiClient } from "./client";

export interface ArticleSummary {
  id: string;
  title: string;
  published_at: string; // ISO datetime string, as returned by the API
}

export interface ArticleListResponse {
  items: ArticleSummary[];
  total: number;
  total_pages: number;
  page: number;
  page_size: number;
}

export async function listArticles(
  page: number,
  pageSize = 10,
): Promise<ArticleListResponse> {
  return apiClient.request<ArticleListResponse>(
    `/articles?page=${page}&page_size=${pageSize}`,
  );
}

export interface Article {
  id: string;
  title: string;
  content: string;
  published_at: string; // ISO datetime string, as returned by the API
}

export interface ArticleInput {
  title: string;
  content: string;
  published_at: string; // ISO datetime string, sent as-is to the API
}

export async function getArticle(id: string): Promise<Article> {
  return apiClient.request<Article>(`/articles/${id}`);
}

export async function createArticle(input: ArticleInput): Promise<Article> {
  return apiClient.request<Article>("/articles", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function updateArticle(
  id: string,
  input: ArticleInput,
): Promise<Article> {
  return apiClient.request<Article>(`/articles/${id}`, {
    method: "PUT",
    body: JSON.stringify(input),
  });
}

export async function deleteArticle(id: string): Promise<void> {
  await apiClient.request<void>(`/articles/${id}`, {
    method: "DELETE",
  });
}
