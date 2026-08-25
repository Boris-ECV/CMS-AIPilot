import { Navigate, Route, Routes } from "react-router-dom";
import { LoginPage } from "./pages/LoginPage";
import { ArticlesList } from "./pages/ArticlesList";
import { ArticleForm } from "./pages/ArticleForm";
import { RequireAuth } from "./auth/RequireAuth";
import { getStoredToken } from "./auth/token";
import {
  ARTICLES_PATH,
  ARTICLE_EDIT_PATH,
  ARTICLE_NEW_PATH,
  LOGIN_PATH,
} from "./routes";

function RootRedirect() {
  const token = getStoredToken();
  return <Navigate to={token ? ARTICLES_PATH : LOGIN_PATH} replace />;
}

export function App() {
  return (
    <Routes>
      <Route path="/" element={<RootRedirect />} />
      <Route path={LOGIN_PATH} element={<LoginPage />} />
      <Route element={<RequireAuth />}>
        <Route path={ARTICLES_PATH} element={<ArticlesList />} />
        <Route path={ARTICLE_NEW_PATH} element={<ArticleForm />} />
        <Route path={ARTICLE_EDIT_PATH} element={<ArticleForm />} />
      </Route>
    </Routes>
  );
}
