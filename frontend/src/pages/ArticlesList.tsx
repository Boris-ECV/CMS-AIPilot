import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listArticles } from "../api/articles";
import type { ArticleSummary } from "../api/articles";
import { ApiError } from "../api/client";
import { useHandleUnauthorized } from "../auth/useHandleUnauthorized";
import { editPath } from "../routes";

const PAGE_SIZE = 10;
const GENERIC_ERROR_MESSAGE = "載入文章列表失敗,請稍後再試";
const EMPTY_STATE_MESSAGE = "尚無文章";

export function ArticlesList() {
  const [articles, setArticles] = useState<ArticleSummary[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const handleUnauthorized = useHandleUnauthorized();

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setError(null);
      try {
        const response = await listArticles(page, PAGE_SIZE);
        if (cancelled) return;
        setArticles(response.items);
        setTotalPages(response.total_pages);
      } catch (err) {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 401) {
          handleUnauthorized();
          return;
        }
        setError(GENERIC_ERROR_MESSAGE);
      }
    }

    void load();

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page]);

  if (error) {
    return <p role="alert">{error}</p>;
  }

  if (articles.length === 0) {
    return <p>{EMPTY_STATE_MESSAGE}</p>;
  }

  return (
    <div>
      <table>
        <thead>
          <tr>
            <th>標題</th>
            <th>發布日期</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {articles.map((article) => (
            <tr key={article.id}>
              <td>{article.title}</td>
              <td>{article.published_at}</td>
              <td>
                <Link to={editPath(article.id)}>編輯</Link>
                <button
                  type="button"
                  data-testid={`delete-article-${article.id}`}
                  onClick={() => {
                    /* no-op: wired up by SDLCAIP1-14 */
                  }}
                >
                  刪除
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div>
        <button
          type="button"
          disabled={page <= 1}
          onClick={() => setPage((current) => current - 1)}
        >
          上一頁
        </button>
        <span>
          第 {page} 頁,共 {totalPages} 頁
        </span>
        <button
          type="button"
          disabled={page >= totalPages}
          onClick={() => setPage((current) => current + 1)}
        >
          下一頁
        </button>
      </div>
    </div>
  );
}
