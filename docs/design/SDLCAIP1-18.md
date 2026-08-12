# 設計文件 — SDLCAIP1-18 後台前端骨架與登入頁

## 對應需求規格

G1 通過版本(見 `docs/PRD.md` SDLCAIP1-18 章節):作為唯一的 CMS 管理者,
需要一個登入表單輸入帳號密碼以取得 session,以便後續存取受保護的後台頁面
而不必手動呼叫 API。驗收條件(Gherkin,共 5 條):

1. 登入成功 → 呼叫 `POST /login` 取得 JWT、儲存供後續 API 呼叫使用,導向
   文章列表頁路由(路由本身可先預留,內容由 SDLCAIP1-19 定義)。
2. 帳密錯誤(401)→ 顯示錯誤訊息、不儲存任何 token、停留在登入頁。
3. 帳戶鎖定(429)→ 顯示鎖定提示訊息(不需精確倒數秒數)。
4. 未登入存取受保護頁面 → 導向登入頁,不發出該頁面的 API 請求。
5. 已登入的 API 呼叫 → 帶上 `Authorization: Bearer <token>` header。

範圍外(不在本票):文章列表頁內容(SDLCAIP1-19)、新增/編輯文章表單
(SDLCAIP1-13)、刪除確認互動(SDLCAIP1-14)、搜尋/篩選(SDLCAIP1-16)、
登出、Token 刷新、記住我、密碼重設 UI、響應式版面(後台僅需桌機版)。

**本票定位:** 這是專案第一個涉及後台 UI 的 Story,repo 內尚無任何前端
骨架(`project-profile.yaml` 明確註記)。本設計因此同時涵蓋「建立前端
專案骨架」與「登入頁功能」兩部分,但骨架本身只建到本票需要的最小程度
(路由、http client、登入頁、受保護路由 wrapper),不預先搭建 SDLCAIP1-19
之後才需要的頁面/元件。

## 介面/API 契約

### 對外(呼叫既有後端,非本票新增後端 API)

前端呼叫既有 `POST /login`(SDLCAIP1-10,`src/cms_aipilot/main.py`),
request/response 格式取自該端點現況實作,不重新發明:

**Request**
```json
{ "username": "string, min_length=1", "password": "string, min_length=1" }
```

**Response — 200 成功**
```json
{ "access_token": "string (JWT)", "token_type": "bearer" }
```

**Response — 401 帳密錯誤**
```json
{ "detail": "Invalid username or password" }
```
(FastAPI `HTTPException(status_code=401, detail=...)` 預設格式)

**Response — 429 帳戶鎖定**
```json
{
  "detail": "Account locked. Try again in <N> seconds.",
  "retry_after_seconds": 900
}
```
Header 額外含 `Retry-After: <N>`。

前端**不解析** `detail` 內的具體秒數字串或 `retry_after_seconds` 數值來做
精確倒數(規格明講「不需精確倒數秒數」)——只用「狀態碼是 429」這件事來
決定顯示固定文案的鎖定提示,不依賴 response body 內容做邏輯分支之外的
展示。這樣即使後端未來調整 `detail` 的措辭,前端也不會跟著壞掉。

### 前端內部契約:API client

新增 `frontend/src/api/client.ts`,提供一個薄封裝的 fetch wrapper:

```ts
// frontend/src/api/client.ts
export class ApiError extends Error {
  constructor(public status: number, public body: unknown) {
    super(`API error ${status}`);
  }
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

async function request<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const token = getStoredToken();
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  const res = await fetch(`${API_BASE_URL}${path}`, { ...init, headers });
  if (!res.ok) {
    let body: unknown = undefined;
    try {
      body = await res.json();
    } catch {
      /* body may be empty, e.g. 204 */
    }
    throw new ApiError(res.status, body);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const apiClient = { request };
```

`getStoredToken()` 見下方「Token 儲存」小節。**每一次** `request()` 呼叫
都會附上 `Authorization` header(若有 token),不限於文章相關端點——
本票只實際用到 `POST /login`(不帶 token)本身不需要這個 header,但這個
共用 client 從第一天就具備附加 header 的能力,供 SDLCAIP1-19 之後的頁面
直接複用,不必重新設計 client。

**登入函式簽章**(`frontend/src/api/auth.ts`):

```ts
export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
}

export async function login(credentials: LoginRequest): Promise<LoginResponse> {
  return apiClient.request<LoginResponse>("/login", {
    method: "POST",
    body: JSON.stringify(credentials),
  });
}
```

呼叫端(登入頁元件)捕捉 `ApiError`,依 `error.status` 分流:
- `401` → 顯示「帳號或密碼錯誤」(固定文案,不逐字顯示後端 `detail`,
  避免耦合後端措辭;規格只要求「顯示錯誤訊息」,未要求逐字轉發)。
- `429` → 顯示「帳戶已被鎖定,請稍後再試」(固定文案,同上理由)。
- 其他狀態碼(如 500)→ 顯示通用錯誤訊息「登入失敗,請稍後再試」
  (規格未定義此情境的訊息文案,採用與 401/429 一致的固定文案風格,
  非規格要求的行為分支,單純避免未捕捉例外讓頁面白屏)。

## 資料模型

無新增資料模型。本票不新增/變更任何資料表、欄位或索引(後端 DynamoDB
結構不變)。前端瀏覽器端的 token 儲存屬於「介面/技術決策」範疇,非
「資料模型」——見下方技術決策。

## 關鍵技術決策

- **前端骨架落於新頂層目錄 `frontend/`,獨立於 `src/cms_aipilot/`
  (後端 Lambda 部署單元)**:避免前端建置產物/`node_modules` 混入後端
  部署 zip;`project-profile.yaml` 的 `structure.src` 只列後端路徑,
  本票新增前端後,建議該檔案的 human owner 補一行
  `frontend: "frontend/"`(架構師不代為修改此 human-owned 檔案,僅在此
  註記建議)。

- **Vite + React + TypeScript(非 JS)**:`project-profile.yaml` 已聲明
  frameworks 含 `react, vite`；選 TypeScript 而非純 JS,是因為
  `LoginRequest`/`LoginResponse` 這類 API 契約用型別直接鏡射
  `main.py` 的 Pydantic model,能在編譯期抓到前後端契約不一致(例如
  欄位改名),對單人維護的專案而言比執行期才發現的落差更省事;專案目前
  無既有前端程式碼可依循慣例,故此為本票新立的慣例,供後續前端 Story
  沿用。

- **路由庫選 `react-router`(v6+),而非純條件渲染**:雖然 v1 只有登入頁 +
  一個列表頁路由佔位,規模上條件渲染也能做,但驗收條件 1 明確要求
  「導向到列表頁的路由」要存在或可預留,且 SDLCAIP1-19 之後會迅速長出
  多個頁面路由(列表、編輯);一開始就用標準路由庫,避免 SDLCAIP1-19
  的 developer 還要先把條件渲染重構成路由系統才能加頁面。`react-router`
  是 React 生態最主流的選擇,無需額外評估其他函式庫。

- **Token 儲存採 `localStorage`,而非 `sessionStorage`**:規格明講此為
  技術判斷、非需求歧義。選擇理由——後台僅單一管理者使用桌機瀏覽器
  (Epic 範圍已排除手機/平板),重新整理分頁或關閉分頁後仍希望維持登入
  狀態(避免每次重整都要重新輸入密碼,而 JWT 效期已由 SDLCAIP1-10 訂為
  8 小時,足夠支撐一次工作階段跨分頁/重整);`sessionStorage` 會在每次
  關閉分頁後強制重新登入,對單一管理者的日常編輯情境是不必要的摩擦。
  安全性权衡:`localStorage` 可被同源 XSS 讀取,但本專案後台目前無
  第三方腳本/使用者輸入渲染為可執行內容的介面(文章內容在前台是純
  文字轉靜態 HTML,已由 `main.py` 用 `html.escape` 處理),XSS 風險面
  相對小;若未來新增高風險介面,應重新評估此決策,但非本票範圍。

- **Token 存取封裝在單一模組 `frontend/src/auth/token.ts`**
  (`getStoredToken`/`setStoredToken`/`clearStoredToken`),不讓元件直接
  呼叫 `localStorage`:讓儲存機制未來若要換(例如改 httpOnly cookie)
  時只需改一個檔案,API client 與路由守衛都透過這個模組間接讀寫。

- **受保護路由用 wrapper 元件 `RequireAuth`,而非在每個頁面元件內各自
  檢查**:與 SDLCAIP1-11 後端用 router 層級共用依賴、不逐路由重複的
  精神一致(見 `docs/design/SDLCAIP1-11.md`「關鍵技術決策」)。實作:

  ```tsx
  // frontend/src/auth/RequireAuth.tsx
  import { Navigate, Outlet } from "react-router-dom";
  import { getStoredToken } from "./token";

  export function RequireAuth() {
    const token = getStoredToken();
    if (!token) {
      return <Navigate to="/login" replace />;
    }
    return <Outlet />;
  }
  ```

  路由設定範例(`frontend/src/App.tsx`):

  ```tsx
  <Routes>
    <Route path="/login" element={<LoginPage />} />
    <Route element={<RequireAuth />}>
      <Route path="/articles" element={<ArticlesPlaceholder />} />
    </Route>
  </Routes>
  ```

  `RequireAuth` 只檢查「本地是否存有 token」,不驗證 token 是否過期/
  簽章有效(驗證交給後端在實際 API 呼叫時回 401)——符合驗收條件 4
  「沒有已儲存 token → 導向登入頁、不發出該頁面的 API 請求」的字面
  要求;token 存在但已過期的情況,由頁面實際呼叫受保護 API 時收到
  401 處理(此為 SDLCAIP1-19 該頁面自身要處理的錯誤情境,非本票範圍,
  本票只交付路由守衛本身)。

  `/articles` 路徑下方元件 `ArticlesPlaceholder` 僅為本票的路由佔位
  (符合驗收條件 1「路徑可預留」),不实作列表內容;SDLCAIP1-19 會替換
  此佔位為真正的列表頁。

- **登入成功後導向 `/articles`(寫死路徑常數,不做設定檔)**:規格只要求
  「路徑本身由 SDLCAIP1-19 定義,此票只需要路由存在或可預留」;因此本票
  先以 `/articles` 作為佔位路徑常數(定義於 `frontend/src/routes.ts`
  單一位置),SDLCAIP1-19 若需要不同路徑,只需改這一個常數,不影響登入頁
  邏輯本身。

- **表單狀態用 React 內建 `useState`,不引入表單函式庫
  (如 react-hook-form)**:登入表單只有 2 個欄位、無複雜驗證規則
  (帳密皆為 `min_length=1`,由後端最終把關),用內建 state 已足夠,
  避免為單一簡單表單引入額外相依套件。

## 前端目錄/檔案結構(新增)

```
frontend/
  package.json
  vite.config.ts
  tsconfig.json
  index.html
  .env.example              # VITE_API_BASE_URL=http://localhost:8000
  src/
    main.tsx
    App.tsx                 # 路由設定
    routes.ts               # 路徑常數(如 LOGIN_PATH, ARTICLES_PATH)
    api/
      client.ts             # 共用 fetch wrapper(附 Authorization header)
      auth.ts                # login() 函式
    auth/
      token.ts              # getStoredToken/setStoredToken/clearStoredToken
      RequireAuth.tsx        # 受保護路由 wrapper
    pages/
      LoginPage.tsx
      ArticlesPlaceholder.tsx  # 本票僅佔位,SDLCAIP1-19 取代其內容
```

測試放在 `frontend/src/**/*.test.tsx`(與現有後端 `tests/` 鏡射
`src/` 的慣例對齊,但前端測試檔與原始檔同層——此為前端生態慣用作法,
與 `project-profile.yaml` 現有 `test_layout` 針對 Python 的敘述不衝突,
該欄位描述的是既有 Python 測試佈局,不涵蓋前端)。

## project-profile.yaml 建議新增內容(人類擁有,架構師僅提案不代為修改)

`project-profile.yaml` 為 human-owned 檔案,以下為建議 human 補上的
`commands` 段落(供 developer/CI 執行前端建置與測試):

```yaml
commands:
  frontend_setup: "cd frontend && npm install"
  frontend_build: "cd frontend && npm run build"
  frontend_test: "cd frontend && npm run test"
  frontend_lint: "cd frontend && npm run lint"
```

對應 `frontend/package.json` 的 npm scripts 建議:

```json
{
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "test": "vitest run",
    "lint": "eslint ."
  }
}
```

測試框架建議 `vitest`(Vite 官方推薦、與既有 Vite 設定共用轉譯管線,
免額外設定 Babel/webpack)+ `@testing-library/react`(渲染登入表單、
斷言 401/429 訊息與導向行為)。

## 開放設計問題(定稿時必須為空)

無。
