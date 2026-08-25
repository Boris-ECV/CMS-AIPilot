# 設計文件 — SDLCAIP1-38 後台根路徑無畫面，未導向登入頁

## 對應需求規格

G1 通過版本：作為後台唯一管理者，希望直接開啟後台根路徑 `/` 就能被導向到
正確畫面（未登入 → `/login`；已登入 → `/articles`），不需記住或手動輸入
`/login`。驗收條件（Gherkin，共 3 條）：

1. 未登入時開啟 `/`，被導向到 `/login`，顯示登入表單。
2. 已登入時（token 存在判斷邏輯比照既有 `RequireAuth`）開啟 `/`，被導向
   到 `/articles`，顯示文章列表。
3. 既有 `/login`、`/articles`、`/articles/new`、`/articles/:id/edit` 路由
   與其測試不受影響，`npm run test` 全數通過。

範圍外：不含登入頁、文章列表頁本身的行為或樣式變更；不含「記住我」、自動
登入等額外機制；不含後端 API 變更。

依賴：無。

## 介面/API 契約

無。本票不新增/變更任何對外 HTTP 端點，純屬前端路由設定調整，不呼叫任何
API。

## 資料模型

無新增資料模型。不涉及任何資料表、欄位或索引；本票只觸碰
`frontend/src/App.tsx`（新增一條 `<Route>`），皆為前端路由設定。

## 關鍵技術決策

- **新增根路徑 `<Route path="/" element={<RootRedirect />} />`，`RootRedirect`
  為 `App.tsx` 內新增的極小型元件，複用 `RequireAuth` 已使用的
  `getStoredToken()`（`frontend/src/auth/token.ts`）判斷 token 是否存在，
  再用 `react-router-dom` 的 `<Navigate replace />` 導向 `/login` 或
  `/articles`**：
  ```tsx
  // App.tsx 內新增
  function RootRedirect() {
    const token = getStoredToken();
    return <Navigate to={token ? ARTICLES_PATH : LOGIN_PATH} replace />;
  }
  ```
  ```tsx
  <Routes>
    <Route path="/" element={<RootRedirect />} />
    <Route path={LOGIN_PATH} element={<LoginPage />} />
    <Route element={<RequireAuth />}>
      ...
    </Route>
  </Routes>
  ```
  理由：AC2 明確要求「比照 `RequireAuth` 現有的 token 存在判斷邏輯」——
  `RequireAuth`（`frontend/src/auth/RequireAuth.tsx`）本身就是靠
  `getStoredToken()` 回傳值是否為 `null` 來判斷，直接重用同一個函式即可
  保證兩處判斷邏輯永遠一致，不需另寫或包裝一份判斷式。不放在
  `RequireAuth` 內部改造（例如讓 `RequireAuth` 同時處理 `/` 與受保護路由）
  是因為 `RequireAuth` 現有語意是「未登入時擋下受保護頁面」，職責單一；
  根路徑的導向邏輯是雙向的（有 token 也要導向、不只是擋），用一個獨立的
  `RootRedirect` 元件表達更直接，也不影響 `RequireAuth` 既有測試與其他
  路由的行為（對應 AC3）。用 `<Navigate replace />`（而非
  `useNavigate` + `useEffect`）沿用 `RequireAuth` 已建立的同一種宣告式導向
  寫法，是這個程式庫既有的慣例，不另創第二種導向機制。`replace` 避免
  瀏覽器歷史留下無意義的 `/` 紀錄，導致使用者按上一頁又回到空白根路徑。

- **`RootRedirect` 元件直接定義在 `App.tsx` 內，不另開新檔案**：程式碼量
  僅 3 行、無獨立測試需求（行為完全由既有 `RequireAuth`/路由測試模式覆蓋
  即可驗證），比照 spec 範圍聲明的「小改動」定位，避免為極小邏輯新增檔案
  與 import，維持改動最小化。

## 開放設計問題（定稿時必須為空）

無。
