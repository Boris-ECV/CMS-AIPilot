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
