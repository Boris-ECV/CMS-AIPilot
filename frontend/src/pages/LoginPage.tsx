import { useState } from "react";
import type { FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { login } from "../api/auth";
import { ApiError } from "../api/client";
import { setStoredToken } from "../auth/token";
import { ARTICLES_PATH } from "../routes";
import "../styles/design-tokens.css";
import "./LoginPage.css";

const INVALID_CREDENTIALS_MESSAGE = "帳號或密碼錯誤";
const ACCOUNT_LOCKED_MESSAGE = "帳戶已被鎖定,請稍後再試";
const GENERIC_ERROR_MESSAGE = "登入失敗,請稍後再試";

export function LoginPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const navigate = useNavigate();

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const response = await login({ username, password });
      setStoredToken(response.access_token);
      navigate(ARTICLES_PATH);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 401) {
          setError(INVALID_CREDENTIALS_MESSAGE);
        } else if (err.status === 429) {
          setError(ACCOUNT_LOCKED_MESSAGE);
        } else {
          setError(GENERIC_ERROR_MESSAGE);
        }
      } else {
        setError(GENERIC_ERROR_MESSAGE);
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className="login-page__form" onSubmit={handleSubmit}>
      <h1 className="login-page__title">登入</h1>
      <div className="login-page__field">
        <label htmlFor="username">帳號</label>
        <span id="username-required" className="login-page__required">
          必填
        </span>
        <input
          id="username"
          name="username"
          type="text"
          value={username}
          onChange={(event) => setUsername(event.target.value)}
          required
          aria-describedby="username-required"
        />
      </div>
      <div className="login-page__field">
        <label htmlFor="password">密碼</label>
        <span id="password-required" className="login-page__required">
          必填
        </span>
        <input
          id="password"
          name="password"
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          required
          aria-describedby="password-required"
        />
      </div>
      {error && (
        <p role="alert" className="login-page__error">
          {error}
        </p>
      )}
      <button className="login-page__submit" type="submit" disabled={submitting}>
        登入
      </button>
    </form>
  );
}
