import { Route, Routes } from "react-router-dom";
import { LoginPage } from "./pages/LoginPage";
import { ArticlesList } from "./pages/ArticlesList";
import { ArticleForm } from "./pages/ArticleForm";
import { RequireAuth } from "./auth/RequireAuth";
import {
  ARTICLES_PATH,
  ARTICLE_EDIT_PATH,
  ARTICLE_NEW_PATH,
  LOGIN_PATH,
} from "./routes";

export function App() {
  return (
    <Routes>
      <Route path={LOGIN_PATH} element={<LoginPage />} />
      <Route element={<RequireAuth />}>
        <Route path={ARTICLES_PATH} element={<ArticlesList />} />
        <Route path={ARTICLE_NEW_PATH} element={<ArticleForm />} />
        <Route path={ARTICLE_EDIT_PATH} element={<ArticleForm />} />
      </Route>
    </Routes>
  );
}
