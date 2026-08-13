import { Route, Routes } from "react-router-dom";
import { LoginPage } from "./pages/LoginPage";
import { ArticlesList } from "./pages/ArticlesList";
import { RequireAuth } from "./auth/RequireAuth";
import { ARTICLES_PATH, LOGIN_PATH } from "./routes";

export function App() {
  return (
    <Routes>
      <Route path={LOGIN_PATH} element={<LoginPage />} />
      <Route element={<RequireAuth />}>
        <Route path={ARTICLES_PATH} element={<ArticlesList />} />
      </Route>
    </Routes>
  );
}
