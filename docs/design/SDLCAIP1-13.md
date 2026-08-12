# 設計文件 — SDLCAIP1-13 後台新增/編輯文章表單

## 對應需求規格

G1 通過版本(見 `docs/PRD.md` SDLCAIP1-13 章節):作為唯一的 CMS 管理者,
需要一個表單可以新增文章或編輯既有文章(標題、純文字內文、發布時間),
以便不必手動呼叫 API 即可發布/更新網站內容。驗收條件(Gherkin,共 12 條):

1. 開啟新增表單,欄位為空。
2. 開啟編輯表單,欄位預先填入既有文章資料(`GET /articles/{id}` 200)。
3. 開啟編輯表單但文章已不存在(`GET /articles/{id}` 404)→ 顯示找不到
   文章,不顯示表單。
4. 成功建立新文章(`POST /articles` 201)→ 導向列表頁。
5. 成功編輯既有文章(`PUT /articles/{id}` 200)→ 導向列表頁。
6. 驗證錯誤 — 標題為空 → 前端擋下送出,不導向,保留其他欄位值。
7. 驗證錯誤 — 內容為空 → 同上。
8. 後端回傳 422 → 顯示通用錯誤訊息,不導向。
9. 儲存失敗 — 靜態頁上傳失敗 502(既有後端行為:此情境下該文章已被
   後端整筆刪除作為回滾)→ 前端顯示明確失敗訊息,不得宣稱已儲存成功,
   不導向。
10. 送出表單時 token 已失效 401 → 前端清除 token 並導向登入頁。
11. 取消編輯,返回列表頁,不呼叫 API。

範圍外:分類/標籤/草稿狀態欄位;富文本編輯器(content 為純文字);
圖片/附件上傳;表單自動儲存草稿/離開頁面二次確認彈窗;文章列表頁本身
(SDLCAIP1-19)、刪除確認互動(SDLCAIP1-14)、搜尋/篩選(SDLCAIP1-16);
後端 API 契約變更(不重新設計,純消費既有 API);手機/平板響應式版面;
401 全域攔截器的實作位置(留給 developer 判斷)。

依賴:SDLCAIP1-18(前端骨架/`apiClient`/認證慣例,已 Done);
SDLCAIP1-19(文章列表頁提供新增/編輯入口,設計已定稿 —
`docs/design/SDLCAIP1-19.md` 保留了 `ARTICLE_EDIT_PATH`/`editPath()` 與
共用 hook `useHandleUnauthorized` 供本票直接接手,見下方風險說明);
外部依賴既有後端 API `POST /articles`、`PUT /articles/{id}`、
`GET /articles/{id}`(SDLCAIP1-4/6/8,已 Done,含 JWT 保護 SDLCAIP1-11)。

## 介面/API 契約

### 對外(呼叫既有後端,非本票新增後端 API)

Request/response 格式取自 `src/cms_aipilot/main.py` 現況實作
(`create_article`、`update_article`、`get_article`),不重新發明。

**新增文章 — `POST /articles`**

```
POST /articles
Authorization: Bearer <token>
Content-Type: application/json

{ "title": "string", "content": "string", "published_at": "2026-01-01T00:00:00" }
```

對應後端 `ArticleCreate`(`title: str, min_length=1`、
`content: str, min_length=1`、`published_at: datetime`)。

- **201** — 成功,body 為建立後的 `Article`
  (`{ "id": "...", "title": "...", "content": "...", "published_at": "..." }`)。
  前端導向 `ARTICLES_PATH`。
- **422** — Pydantic 驗證失敗(FastAPI 預設格式,
  `{ "detail": [{ "loc": [...], "msg": "...", "type": "..." }] }`)。前端**不解析**
  `detail` 內容,只用狀態碼 422 觸發通用錯誤訊息,不導向(驗收條件 8)。
- **502** — `STATIC_PAGE_GENERATION_FAILED_RESPONSE`:
  ```json
  { "error": "STATIC_PAGE_GENERATION_FAILED", "message": "Article could not be published: static page upload failed." }
  ```
  後端 `_publish_or_rollback` 在此情境下已將剛寫入 DynamoDB 的文章項目
  `delete_item` 回滾——**新增情境下,「成功建立」實際上已被後端復原,
  文章並不存在**。前端不解析 body 內容(只用狀態碼判斷),但訊息文案
  需反映「未儲存成功」而非單純「請重試」(見下方技術決策)。
- **401** — 缺失/過期/無效 token,`{ "detail": "Not authenticated" }`,
  header 含 `WWW-Authenticate: Bearer`。不解析 body,只用狀態碼。

**編輯文章 — `PUT /articles/{article_id}`**

```
PUT /articles/{article_id}
Authorization: Bearer <token>
Content-Type: application/json

{ "title": "string", "content": "string", "published_at": "2026-01-01T00:00:00" }
```

- **200** — 成功,body 為更新後的 `Article`。前端導向 `ARTICLES_PATH`。
- **404** — `article_id` 不存在(`{ "detail": "Article not found" }`)。
  規格 12 條驗收條件未明列「送出編輯時 404」這個情境(該條僅涵蓋
  *開啟*編輯表單時的 404,見下)——本設計將其併入下方「其他非
  401/422/502 狀態碼」的通用錯誤處理分支,不另建特殊 UI(判斷依據:
  這是既有後端行為的自然結果〔文章在使用者開啟表單後被他人/另一分頁
  刪除〕,規格既未特別定義文案,採用與 422 相同等級的通用錯誤訊息,
  不導向,不視為需要送回 Refining 的產品缺口)。
- **422 / 502 / 401** — 格式與 `POST /articles` 相同。502 情境下,後端
  同樣先 `put_item` 覆寫再於失敗時 `delete_item` 回滾——**編輯情境下,
  該文章在此次 PUT 呼叫後已被後端整筆刪除**,前端訊息文案需明確反映
  「變更未儲存、文章已被移除」而非「編輯失敗請重試」(見下方技術決策,
  對應驗收條件 9)。

**讀取單篇文章(開啟編輯表單)— `GET /articles/{article_id}`**

```
GET /articles/{article_id}
Authorization: Bearer <token>
```

- **200** — body 為 `Article`
  (`id`、`title`、`content`、`published_at`)。前端用此資料預填表單
  (驗收條件 2)。
- **404** — `{ "detail": "Article not found" }`。前端顯示「找不到文章」
  訊息,**不顯示表單**(驗收條件 3)。
- **401** — 同上,清除 token 並導向登入頁。

### 前端內部契約:API 呼叫函式

擴充既有 `frontend/src/api/articles.ts`(SDLCAIP1-19 建立,沿用
`apiClient.request`,不重新設計 fetch 邏輯),新增:

```ts
// frontend/src/api/articles.ts(新增於既有 ArticleSummary/ArticleListResponse/listArticles 之後)

export interface Article {
  id: string;
  title: string;
  content: string;
  published_at: string; // ISO datetime string, as returned by the API
}

export interface ArticleInput {
  title: string;
  content: string;
  published_at: string; // ISO datetime string, sent as-is to the API
}

export async function getArticle(id: string): Promise<Article> {
  return apiClient.request<Article>(`/articles/${id}`);
}

export async function createArticle(input: ArticleInput): Promise<Article> {
  return apiClient.request<Article>("/articles", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function updateArticle(id: string, input: ArticleInput): Promise<Article> {
  return apiClient.request<Article>(`/articles/${id}`, {
    method: "PUT",
    body: JSON.stringify(input),
  });
}
```

`ArticleInput` 與 `Article` 分開定義(而非直接重用 `Article` 並省略
`id`):`Article` 是「後端回傳形狀」,`ArticleInput` 是「前端送出形狀」,
兩者目前欄位相同但語意不同來源,分開命名可避免未來任一方新增欄位
(例如後端回傳額外的 metadata)時被誤用為送出格式。

## 資料模型

無新增資料模型。本票不新增/變更任何資料表、欄位或索引,亦不新增/變更
後端 API 契約(`POST /articles`、`PUT /articles/{id}`、
`GET /articles/{id}` 已由既有票據提供)。

## 關鍵技術決策

- **新增/編輯共用單一元件 `frontend/src/pages/ArticleForm.tsx`,不拆成
  兩個獨立元件**:兩者的欄位、前端驗證規則、送出後導向、錯誤處理分支
  完全相同,唯一差異是(a)是否在掛載時呼叫 `getArticle` 預填、
  (b)送出時呼叫 `createArticle` 還是 `updateArticle`。用
  `useParams<{ id?: string }>()` 判斷模式:路由帶 `id` 參數即為編輯
  模式,否則為新增模式。拆成兩個元件只會複製貼上表單 JSX 與驗證邏輯,
  不符合「不重複發明」的原則;沿用 `ArticleForm` 單一元件,由兩個路由
  共用同一 `element`。

- **新增路由常數 `ARTICLE_NEW_PATH = "/articles/new"`(`routes.ts`),
  沿用 SDLCAIP1-19 已保留的 `ARTICLE_EDIT_PATH = "/articles/:id/edit"`
  與 `editPath(id)`**:已讀取 `docs/design/SDLCAIP1-19.md` 確認上述
  常數命名與路徑字串,本票不重新定義或變更其格式,直接在
  `frontend/src/App.tsx` 的 `RequireAuth` 區塊內註冊
  `<Route path={ARTICLE_NEW_PATH} element={<ArticleForm />} />` 與
  `<Route path={ARTICLE_EDIT_PATH} element={<ArticleForm />} />`(SDLCAIP1-19
  只保留路徑字串,未註冊對應元件,本票是明訂要接手的一方)。

- **前端必填驗證用元件內 state + 送出前檢查,不引入表單驗證函式庫**:
  與 SDLCAIP1-18(登入表單)、SDLCAIP1-19(資料載入)一致的「單一簡單
  情境不需額外相依套件」原則。作法:`handleSubmit` 先檢查
  `title.trim() === ""` / `content.trim() === ""`,任一為真則設定對應
  欄位的錯誤訊息、`return` 阻止呼叫 API,不清空任何欄位值(受控元件
  本就不會因驗證失敗而重置,天然滿足驗收條件 6/7「保留其他欄位值」)。

- **錯誤路徑判斷順序:401 → 422 → 502 → 其他**,共用 SDLCAIP1-19 建立的
  `frontend/src/auth/useHandleUnauthorized.ts`:`catch (err)` 區塊先呼叫
  `handleUnauthorized(err)`(回傳 `boolean` 表示是否已處理 401 並完成
  清除 token + 導向登入頁);已處理則直接 `return`,不再往下判斷其他
  狀態碼,避免與 502/422 分支重複處理同一個錯誤。未處理則依
  `err instanceof ApiError` 判斷 `err.status`:
  - `422` → 顯示通用錯誤訊息「文章儲存失敗,請確認欄位內容後再試」。
  - `502` → 顯示「文章儲存失敗:靜態頁面發布失敗,此次變更已被系統復原
    (文章未儲存/已被移除),請重新確認後再試一次」——文案明確反映
    「未成功」且不用「請重試」這種可能被誤解為「只是網路問題」的
    輕描淡寫措辭,對應驗收條件 9 的「不得宣稱已儲存成功」要求。新增
    與編輯共用此文案(兩者在 502 情境下,後端都已將該筆資料
    `delete_item` 回滾,見上方介面章節)。
  - 其他狀態碼(含 PUT 情境下罕見的 404,見上方介面章節)→ 顯示與
    422 相同等級的通用錯誤訊息,不導向。
  三種分支均不呼叫 `navigate`,滿足「不導向」要求;僅 201/200 成功路徑
  呼叫 `navigate(ARTICLES_PATH)`。

- **開啟編輯表單時的 404,與送出表單時的錯誤分開處理,用獨立 state
  (`loadError` vs `submitError`)**:驗收條件 3 要求「不顯示表單」,若
  和送出錯誤共用同一個 state/UI 位置,會在使用者修正送出錯誤後难以
  區分兩種情境的呈現邏輯(一個要藏表單,一個要留著表單讓使用者修改)。
  掛載時 `useEffect` 呼叫 `getArticle`(僅編輯模式,`id` 存在時執行),
  失敗且為 404 時設定 `loadError`,元件渲染時 `loadError` 非空則整頁
  只顯示「找不到文章」訊息,不渲染 `<form>`;非 404 的載入失敗(含 401,
  同樣先經 `useHandleUnauthorized` 判斷)歸類為同一種「找不到文章」等級
  的通用失敗顯示(規格未定義編輯表單載入時非 404/401 的其他錯誤文案,
  沿用同一段落訊息,不另外新增文字)。

- **發布時間欄位用 `<input type="datetime-local">`,送出前轉換為 ISO
  8601 字串**:規格只說「發布時間」,未指定確切輸入元件與格式;
  `datetime-local` 是瀏覽器原生元件,不需額外套件即可提供日期+時間
  選擇,產出格式(`YYYY-MM-DDTHH:mm`)可直接送給後端(Pydantic
  `datetime` 可解析,不含時區資訊時以本機時間視角處理,與後端現況
  一致,後端本身也未處理時區轉換)。編輯模式預填時,將
  `Article.published_at`(後端回傳含秒數的 ISO 字串)裁切至分鐘精度
  (`.slice(0, 16)`)以符合 `datetime-local` 輸入框可接受的格式。

- **取消按鈕為單純導覽,不呼叫任何 API 或清除表單 state**:
  `<button type="button" onClick={() => navigate(ARTICLES_PATH)}>取消</button>`,
  滿足驗收條件 11「不呼叫 API」,沒有其他規格要求(如離開前確認彈窗,
  已明訂範圍外)。

## 前端目錄/檔案結構(新增/變更)

```
frontend/src/
  routes.ts                     # 新增 ARTICLE_NEW_PATH;沿用 SDLCAIP1-19 的 ARTICLE_EDIT_PATH/editPath()
  App.tsx                       # 新增 ARTICLE_NEW_PATH、ARTICLE_EDIT_PATH 兩條路由,element 均為 ArticleForm
  api/
    articles.ts                 # 新增:Article、ArticleInput、getArticle()、createArticle()、updateArticle()
  pages/
    ArticleForm.tsx             # 新增:新增/編輯共用表單元件(依 useParams 的 id 是否存在切換模式)
```

## 開放設計問題(定稿時必須為空)

無。
