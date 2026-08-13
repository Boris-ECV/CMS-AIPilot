import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  createArticle,
  getArticle,
  updateArticle,
} from "../api/articles";
import { ApiError } from "../api/client";
import { useHandleUnauthorized } from "../auth/useHandleUnauthorized";
import { ARTICLES_PATH } from "../routes";

const NOT_FOUND_MESSAGE = "找不到文章";
const TITLE_REQUIRED_MESSAGE = "請輸入標題";
const CONTENT_REQUIRED_MESSAGE = "請輸入內容";
const INVALID_INPUT_MESSAGE = "文章儲存失敗,請確認欄位內容後再試";
const PUBLISH_FAILED_MESSAGE =
  "文章儲存失敗:靜態頁面發布失敗,此次變更已被系統復原(文章未儲存/已被移除),請重新確認後再試一次";
const GENERIC_SUBMIT_ERROR_MESSAGE = "文章儲存失敗,請確認欄位內容後再試";

export function ArticleForm() {
  const { id } = useParams<{ id?: string }>();
  const isEditMode = Boolean(id);
  const navigate = useNavigate();
  const handleUnauthorized = useHandleUnauthorized();

  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [publishedAt, setPublishedAt] = useState("");

  const [loadError, setLoadError] = useState<string | null>(null);
  const [loading, setLoading] = useState(isEditMode);

  const [titleError, setTitleError] = useState<string | null>(null);
  const [contentError, setContentError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!isEditMode || !id) {
      setLoading(false);
      return;
    }

    let cancelled = false;

    async function load() {
      setLoading(true);
      setLoadError(null);
      try {
        const article = await getArticle(id as string);
        if (cancelled) return;
        setTitle(article.title);
        setContent(article.content);
        setPublishedAt(article.published_at.slice(0, 16));
      } catch (err) {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 401) {
          handleUnauthorized();
          return;
        }
        setLoadError(NOT_FOUND_MESSAGE);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void load();

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, isEditMode]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitError(null);

    const trimmedTitle = title.trim() === "";
    const trimmedContent = content.trim() === "";
    setTitleError(trimmedTitle ? TITLE_REQUIRED_MESSAGE : null);
    setContentError(trimmedContent ? CONTENT_REQUIRED_MESSAGE : null);
    if (trimmedTitle || trimmedContent) {
      return;
    }

    setSubmitting(true);
    try {
      const input = { title, content, published_at: publishedAt };
      if (isEditMode && id) {
        await updateArticle(id, input);
      } else {
        await createArticle(input);
      }
      navigate(ARTICLES_PATH);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        handleUnauthorized();
        return;
      }
      if (err instanceof ApiError && err.status === 422) {
        setSubmitError(INVALID_INPUT_MESSAGE);
      } else if (err instanceof ApiError && err.status === 502) {
        setSubmitError(PUBLISH_FAILED_MESSAGE);
      } else {
        setSubmitError(GENERIC_SUBMIT_ERROR_MESSAGE);
      }
    } finally {
      setSubmitting(false);
    }
  }

  function handleCancel() {
    navigate(ARTICLES_PATH);
  }

  if (loading) {
    return <p>載入中...</p>;
  }

  if (loadError) {
    return <p role="alert">{loadError}</p>;
  }

  return (
    <form onSubmit={handleSubmit}>
      <h1>{isEditMode ? "編輯文章" : "新增文章"}</h1>
      <div>
        <label htmlFor="title">標題</label>
        <input
          id="title"
          name="title"
          type="text"
          value={title}
          onChange={(event) => setTitle(event.target.value)}
        />
        {titleError && <p role="alert">{titleError}</p>}
      </div>
      <div>
        <label htmlFor="content">內容</label>
        <textarea
          id="content"
          name="content"
          value={content}
          onChange={(event) => setContent(event.target.value)}
        />
        {contentError && <p role="alert">{contentError}</p>}
      </div>
      <div>
        <label htmlFor="published_at">發布時間</label>
        <input
          id="published_at"
          name="published_at"
          type="datetime-local"
          value={publishedAt}
          onChange={(event) => setPublishedAt(event.target.value)}
          required
        />
      </div>
      {submitError && <p role="alert">{submitError}</p>}
      <button type="submit" disabled={submitting}>
        儲存
      </button>
      <button type="button" onClick={handleCancel}>
        取消
      </button>
    </form>
  );
}
