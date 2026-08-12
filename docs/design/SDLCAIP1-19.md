# 設計文件 — SDLCAIP1-19 後台文章列表頁(桌機版)

## 對應需求規格

G1 通過版本(見 `docs/PRD.md` SDLCAIP1-19 章節):作為唯一的 CMS 管理者,
需要在桌機版看到文章列表(標題、發布日期)並附分頁,以便檢視既有內容並
進入特定文章的編輯/刪除入口。驗收條件(Gherkin,共 5 條):

1. 有資料時列表正常呈現 → 依 `GET /articles?page=1` 回傳順序顯示每篇
   文章的標題與 `published_at`。
2. 空列表狀態 → `items` 為空陣列(`total=0`)時顯示明確的「尚無文章」
   空狀態訊息,不顯示表格列。
3. 未帶有效 token 導向登入頁 → token 不存在/過期、API 回 401 時,依
   SDLCAIP1-18 的受保護路由機制導向登入頁,不顯示任何文章資料。
4. 分頁行為與 API 回傳一致 → `total_pages > 1`(`page_size=10`)時僅顯示
   當頁最多 10 筆,分頁控制反映 `total`/`total_pages`/`page`;點擊下一頁
   以 `page=2` 重新呼叫 API 並更新畫面。
5. 每列提供編輯/刪除入口 → 至少一列渲染時,該列存在「編輯」與「刪除」
   可點擊入口(連結/按鈕),實際導覽與行為由 SDLCAIP1-13、SDLCAIP1-14
   實作,本票僅需入口存在。

範圍外:登入頁與前端骨架本身(SDLCAIP1-18);新增/編輯文章表單內容與
送出邏輯(SDLCAIP1-13);刪除確認互動與實際刪除呼叫(SDLCAIP1-14);
搜尋/篩選(SDLCAIP1-16);手機/平板響應式版面;內文摘要/snippet 顯示
(`GET /articles` 只回傳 `ArticleSummary`,不含 `content`);依欄位排序、
批量操作、即時更新。

依賴:blocked by SDLCAIP1-18(已 Done,建立前端骨架、`RequireAuth`、
`apiClient`、`/articles` 路由佔位 `ArticlesPlaceholder`);外部依賴
`GET /articles`(SDLCAIP1-5,已 Done,含 JWT 保護 SDLCAIP1-11,已 Done)。

## 介面/API 契約

### 對外(呼叫既有後端,非本票新增後端 API)

前端呼叫既有 `GET /articles`(`src/cms_aipilot/main.py` `list_articles`),
request/response 格式取自該端點現況實作,不重新發明:

**Request**

```
GET /articles?page={page}&page_size={page_size}
Authorization: Bearer <token>
```

- `page`:整數,預設 `1`,`ge=1`(後端 `Query(1, ge=1)`)。
- `page_size`:整數,預設 `10`,`ge=1`(後端 `Query(10, ge=1)`)。本票
  前端固定送 `page_size=10`,不提供 UI 讓使用者調整(規格未要求)。

**Response — 200 成功**

```json
{
  "items": [
    { "id": "string", "title": "string", "published_at": "2026-01-01T00:00:00" }
  ],
  "total": 0,
  "total_pages": 0,
  "page": 1,
  "page_size": 10
}
```

對應後端 Pydantic model `ArticleSummary`(`id`, `title`, `published_at`)
與 `ArticleListResponse`(`items`, `total`, `total_pages`, `page`,
`page_size`)。`items` 已由後端依 `published_at` 降冪排序(`main.py`
`items.sort(..., reverse=True)`),前端**不再重新排序**,依 API 回傳順序
原樣渲染(對應驗收條件 1「依 API 回傳順序顯示」)。

`total=0` 時後端 `total_pages` 為 `0`(`math.ceil(0/page_size) if total
else 0`)——前端空狀態判斷以 `items.length === 0`(等價 `total === 0`)
為準,不依賴 `total_pages` 的特殊值。

**Response — 401**(token 不存在或過期,由 `require_auth` 依賴丟出)

```json
{ "detail": "Not authenticated" }
```

Header 含 `WWW-Authenticate: Bearer`。前端**不解析** `detail` 文字,只用
狀態碼 401 觸發導向登入頁的既有機制(見下方「受保護路由與 401」)。

### 前端內部契約:API 呼叫函式

新增 `frontend/src/api/articles.ts`,沿用 SDLCAIP1-18 建立的
`apiClient.request`(已自動附加 `Authorization` header),不重新設計
fetch 邏輯:

```ts
// frontend/src/api/articles.ts
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
```

`published_at` 型別採 `string`(不轉 `Date`)——只用於顯示,不做日期運算
（排序已由後端完成),用字串直接渲染最簡單、無時區轉換風險;若未來需要
格式化顯示(如「YYYY-MM-DD」),在渲染層用 `Date` 解析,不改變此介面型別。

呼叫端(列表頁元件)捕捉 `ApiError`(`frontend/src/api/client.ts` 既有
類別):
- `status === 401` → 不在頁面內顯示任何文章資料或自訂錯誤訊息,而是
  依 SDLCAIP1-18 的 `RequireAuth` 機制導向登入頁(見下方技術決策,說明
  為何不是「頁面內攔截 401」而是「複用路由守衛」)。
- 其他狀態碼 → 顯示通用錯誤訊息「載入文章列表失敗,請稍後再試」
  (規格未定義非 401 錯誤情境的文案,採用與 SDLCAIP1-18 登入頁一致的
  固定文案風格,避免未捕捉例外讓頁面白屏;非規格要求的行為分支)。

## 資料模型

無新增資料模型。本票不新增/變更任何資料表、欄位或索引,亦不新增後端
API(`GET /articles` 已由 SDLCAIP1-5 提供)。

## 關鍵技術決策

- **新增 `frontend/src/pages/ArticlesList.tsx` 取代
  `frontend/src/pages/ArticlesPlaceholder.tsx`,並更新
  `frontend/src/App.tsx` 路由設定改指向新元件**:`ArticlesPlaceholder`
  是 SDLCAIP1-18 明訂「本票僅為佔位,SDLCAIP1-19 取代其內容」
  (見 `docs/design/SDLCAIP1-18.md`)。`ARTICLES_PATH`(定義於
  `frontend/src/routes.ts`)保持不變,登入頁的導向邏輯不需改動。
  `ArticlesPlaceholder.tsx` 於本票刪除(不再被任何路由引用)。

- **401 處理複用既有 `RequireAuth` 路由守衛,不在頁面元件內另建 401
  攔截邏輯**:`RequireAuth` 目前只檢查「本地是否存有 token」,不驗證
  過期(見 SDLCAIP1-18 設計文件說明,驗證交給後端 API 呼叫時的 401)。
  本票是第一個「token 存在但可能已過期」情境真正會發生的頁面(登入頁
  本身不需要 token)。做法:`listArticles` 呼叫收到 401 時,呼叫既有
  `clearStoredToken()`(`frontend/src/auth/token.ts`)清除本地 token,
  再用 `react-router` 的 `navigate(LOGIN_PATH, { replace: true })`
  導向登入頁——效果上等同 `RequireAuth` 守衛,但因為判斷依據是「API
  回應」而非「路由進入前」,無法單純包在 `RequireAuth` 元件裡,而是在
  `ArticlesList` 的資料取得邏輯中捕捉 401 後手動觸發同樣的清除+導向,
  呼叫的是與 `RequireAuth` 相同的 token 清除/導向元件,避免各頁面各自
  發明一套 401 處理方式。此邏輯抽成共用 hook
  `frontend/src/auth/useHandleUnauthorized.ts`,供本票及未來頁面
  (SDLCAIP1-13/14 若也呼叫受保護 API)共用,不必各自重寫。

- **分頁狀態(`page`)用元件內 `useState`,不寫入 URL query string**:
  規格驗收條件僅要求「點擊下一頁時改以 `page=2` 呼叫 API 並更新畫面」,
  未要求分頁狀態可被書籤/重新整理保留、也未要求瀏覽器上一頁/下一頁鍵
  切換分頁。用 URL query string 雖然更「正確」,但屬於規格沒要求的額外
  行為(且會引入 `react-router` 的 `useSearchParams` 依賴與同步邏輯),
  故採最小實作:`const [page, setPage] = useState(1)`,分頁按鈕呼叫
  `setPage`,`useEffect` 依 `page` 變化重新呼叫 `listArticles`。

- **編輯/刪除入口的具體形狀,是本票必須為 SDLCAIP1-13/14 定出、但規格
  未明講的介面決策**(判斷取捨,見下方風險揭露):
  - 編輯入口為**連結**(`<Link to={editPath(article.id)}>編輯</Link>`),
    路徑常數新增於 `frontend/src/routes.ts`:
    `export const ARTICLE_EDIT_PATH = "/articles/:id/edit";` 與輔助函式
    `export function editPath(id: string) { return \`/articles/${id}/edit\`; }`。
    本票**不**在 `App.tsx` 註冊此路由對應的頁面元件(該路由目前無
    對應頁面,點擊會導致 `react-router` 顯示 404/空白)——路由路徑本身
    先定出以讓 SDLCAIP1-13 直接接手,不必再協調路徑格式;是否要本票
    順手註冊一個空路由佔位,規格與 SDLCAIP1-18 先例都未要求,不做。
  - 刪除入口為**按鈕**(`<button type="button">刪除</button>`),`onClick`
    先綁定為 no-op(空函式,或僅 `console.debug` 佔位),不彈出確認對話框
    或呼叫任何刪除 API——因為刪除是「動作」而非「導覽」,沒有 URL 可預留;
    SDLCAIP1-14 需要的是這顆按鈕存在於 DOM 中且可被測試選取
    (建議加上穩定的 `data-testid="delete-article-{id}"`,供 SDLCAIP1-14
    的測試直接掛上真正的 onClick,不必更動按鈕本身的存在方式)。

- **列表渲染用 HTML `<table>`,而非卡片/清單版面**:規格要求「表格列」
  措辭(驗收條件 2「不顯示表格列」隱含有資料時是表格列),且桌機版
  (本票範圍限定,響應式版面不在範圍)適合表格呈現標題+日期+操作按鈕
  的多欄資料。

- **資料載入用元件內 `useEffect` + `useState`,不引入資料請求函式庫
  (如 react-query)**:與 SDLCAIP1-18「登入表單用內建 state,不引入
  表單函式庫」的理由一致——本票只有一支查詢(無 mutation、無快取需求、
  無背景重新驗證需求),用內建 hook 已足夠,避免為單一查詢引入額外
  相依套件。

## 前端目錄/檔案結構(新增/變更)

```
frontend/src/
  routes.ts                     # 新增 ARTICLE_EDIT_PATH、editPath()
  App.tsx                       # /articles 路由改指向 ArticlesList
  api/
    articles.ts                 # 新增:listArticles()
  auth/
    useHandleUnauthorized.ts    # 新增:401 → 清 token + 導向登入頁的共用 hook
  pages/
    ArticlesList.tsx            # 新增,取代 ArticlesPlaceholder.tsx(刪除後者)
```

## 開放設計問題(定稿時必須為空)

無。
