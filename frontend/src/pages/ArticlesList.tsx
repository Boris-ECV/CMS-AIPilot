import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { deleteArticle, listArticles } from "../api/articles";
import type { ArticleSummary } from "../api/articles";
import { ApiError } from "../api/client";
import { useHandleUnauthorized } from "../auth/useHandleUnauthorized";
import { editPath } from "../routes";

const PAGE_SIZE = 10;
const GENERIC_ERROR_MESSAGE = "載入文章列表失敗,請稍後再試";
const EMPTY_STATE_MESSAGE = "尚無文章";
const DELETE_GENERIC_ERROR_MESSAGE = "刪除文章失敗,請稍後再試";
const DELETE_NOT_FOUND_NOTICE = "該文章已不存在,已從列表移除";
const DELETE_STATIC_PAGE_WARNING = "文章已刪除,但靜態頁清除可能失敗,請確認網站頁面";

export function ArticlesList() {
  const [articles, setArticles] = useState<ArticleSummary[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
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

  async function handleDeleteClick(article: ArticleSummary) {
    const confirmed = window.confirm(
      `確定要刪除文章「${article.title}」嗎?`,
    );
    if (!confirmed) return;

    setNotice(null);
    setError(null);
    try {
      await deleteArticle(article.id);
      setArticles((current) => current.filter((item) => item.id !== article.id));
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        handleUnauthorized();
        return;
      }
      if (err instanceof ApiError && err.status === 404) {
        setArticles((current) => current.filter((item) => item.id !== article.id));
        setNotice(DELETE_NOT_FOUND_NOTICE);
        return;
      }
      if (err instanceof ApiError && err.status === 502) {
        setArticles((current) => current.filter((item) => item.id !== article.id));
        setNotice(DELETE_STATIC_PAGE_WARNING);
        return;
      }
      setError(DELETE_GENERIC_ERROR_MESSAGE);
    }
  }

  if (error) {
    return <p role="alert">{error}</p>;
  }

  if (articles.length === 0) {
    return (
      <div>
        {notice && <p role="status">{notice}</p>}
        <p>{EMPTY_STATE_MESSAGE}</p>
      </div>
    );
  }

  return (
    <div>
      {notice && <p role="status">{notice}</p>}
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
                    void handleDeleteClick(article);
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
