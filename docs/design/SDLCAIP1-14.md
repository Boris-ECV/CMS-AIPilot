# 設計文件 — SDLCAIP1-14 後台刪除確認互動

## 對應需求規格

G1 通過版本(Jira SDLCAIP1-14 描述):作為後台唯一管理者,在文章列表點擊
「刪除」後,需先看到明確的確認步驟才真正送出刪除,以避免誤觸意外刪除
已發布的文章。驗收條件(Gherkin,共 6 條):

1. 確認後成功刪除文章 → 呼叫 `DELETE /articles/{id}`,後端回 204,該
   文章從列表移除,其餘不變。
2. 取消確認不會刪除文章 → 不呼叫 API,文章仍在列表,狀態不變。
3. 刪除已不存在的文章(404)→ 視為已不存在,從列表移除,顯示非阻斷
   提示訊息。
4. 刪除時未登入或憑證過期(401)→ 呼叫既有 `useHandleUnauthorized`
   清除本地 token,導向登入頁,不顯示任何文章列表資料。
5. 資料庫刪除成功但靜態頁清除失敗(502,`error_code=STATIC_PAGE_DELETION_FAILED`)
   → 視為已刪除,從列表移除,顯示非阻斷警示訊息告知靜態頁清除可能失敗。
6. 非預期錯誤(其他 5xx 或網路例外)→ 文章仍顯示於列表,顯示通用錯誤
   訊息,可重試。

範圍外:確認 UI 元件形式(原生 `confirm()` vs 自訂 Modal,留給本設計
決定);批量刪除、多選刪除;刪除復原(undo);刪除成功/失敗訊息確切
文案與樣式(沿用既有錯誤訊息風格);刪除造成分頁狀態異動的自動調整
(沿用 SDLCAIP1-19 既有分頁行為);`ArticlesList.tsx` 以外頁面的刪除
入口;編輯功能(SDLCAIP1-13)與其入口行為;後端
`DELETE /articles/{id}` 端點本身的行為變更(已完成,不在本票範圍修改)。

依賴:blocked by SDLCAIP1-19(已 Done,提供
`data-testid="delete-article-{id}"` 刪除按鈕現為 no-op、
`frontend/src/auth/useHandleUnauthorized.ts`);blocked by SDLCAIP1-7、
SDLCAIP1-9(已 Done,後端刪除端點行為)。外部依賴既有
`frontend/src/api/client.ts` 的 `apiClient.request`/`ApiError`。

已讀取現況程式碼確認以下細節:
- `frontend/src/pages/ArticlesList.tsx`:刪除按鈕已存在
  (`data-testid="delete-article-{id}"`),`onClick` 目前為 no-op 佔位,
  註解明訂「wired up by SDLCAIP1-14」。
- `frontend/src/api/articles.ts`:目前只有 `listArticles`,尚無
  `deleteArticle`。
- `src/cms_aipilot/main.py` `delete_article`(第 259-279 行):
  - 找不到文章 → `HTTPException(status_code=404, detail="Article not found")`。
  - 刪除成功、靜態頁清除失敗 → `JSONResponse(status_code=502, content={"error_code": "STATIC_PAGE_DELETION_FAILED", "detail": "...", "article_id": article_id})`,
    **DynamoDB 記錄已在此之前被 `table.delete_item` 移除**(第 266 行,
    在呼叫 `_delete_static_page` 之前)。
  - 全部成功 → `Response(status_code=204)`。
  - 端點掛在 `articles_router`(`Depends(require_auth)`),未帶/過期
    token 一律 401(格式與其他端點一致,`{"detail": "Not authenticated"}`)。
  - 與規格描述完全一致,無需另外決策。

## 介面/API 契約

### 對外(呼叫既有後端,非本票新增後端 API)

**刪除文章 — `DELETE /articles/{article_id}`**

```
DELETE /articles/{article_id}
Authorization: Bearer <token>
```

- **204** — 成功,無 body。前端從列表 state 移除該筆文章。
- **404** — `{ "detail": "Article not found" }`。前端**不解析** body,
  只用狀態碼;視為已不存在,從列表 state 移除該筆文章,顯示非阻斷
  提示訊息(對應驗收條件 3)。
- **502**,`error_code=STATIC_PAGE_DELETION_FAILED` —
  ```json
  {
    "error_code": "STATIC_PAGE_DELETION_FAILED",
    "detail": "Article deleted but its static page could not be removed from S3.",
    "article_id": "string"
  }
  ```
  前端**不解析** body 內容(只用狀態碼 502 判斷這個分支;不用
  `error_code` 欄位做二次判斷,因為目前後端在刪除情境下只有這一種
  502 成因,狀態碼已足以區分,若未來後端新增其他 502 成因需要不同
  文案,才需要解析 `error_code`)。DynamoDB 記錄已刪除,前端從列表
  state 移除該筆文章,顯示非阻斷警示訊息(對應驗收條件 5)。
- **401** — `{ "detail": "Not authenticated" }`,header 含
  `WWW-Authenticate: Bearer`。前端呼叫既有
  `useHandleUnauthorized()`(清除 token + 導向登入頁),對應驗收條件 4。
- **其他狀態碼(非 204/401/404/502)或網路例外** — 文章保留於列表,顯示
  通用錯誤訊息,可重試(對應驗收條件 6)。

### 前端內部契約:API 呼叫函式

擴充既有 `frontend/src/api/articles.ts`(沿用 `apiClient.request`,不
重新設計 fetch 邏輯),新增:

```ts
// frontend/src/api/articles.ts(新增於既有函式之後)

export async function deleteArticle(id: string): Promise<void> {
  await apiClient.request<void>(`/articles/${id}`, {
    method: "DELETE",
  });
}
```

回傳型別為 `void`:204 情境下 `apiClient.request` 已回傳
`undefined`(`client.ts` 第 31 行 `if (res.status === 204) return
undefined as T`);404/502/401/其他非 2xx 一律經 `ApiError` 拋出,呼叫端
用 `err.status` 判斷分支,`deleteArticle` 本身不需要回傳任何 body 內容
——與 `client.ts` 既有慣例一致(呼叫端捕捉 `ApiError` 判斷狀態碼,不在
API 函式內做分支)。

### 前端內部契約:確認互動

刪除按鈕的 `onClick` 改為呼叫元件內 `handleDeleteClick(article)`
函式,流程如下(虛擬碼,實作細節見下方技術決策):

```ts
async function handleDeleteClick(article: ArticleSummary) {
  const confirmed = window.confirm(`確定要刪除文章「${article.title}」嗎?`);
  if (!confirmed) return; // 驗收條件 2:不呼叫 API

  try {
    await deleteArticle(article.id);
    removeFromList(article.id);
    // 204 成功,不額外顯示訊息(規格未要求),或顯示非阻斷成功提示
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) {
      handleUnauthorized();
      return;
    }
    if (err instanceof ApiError && err.status === 404) {
      removeFromList(article.id);
      setNotice("該文章已不存在,已從列表移除");
      return;
    }
    if (err instanceof ApiError && err.status === 502) {
      removeFromList(article.id);
      setNotice("文章已刪除,但靜態頁清除可能失敗,請確認網站頁面");
      return;
    }
    setError("刪除文章失敗,請稍後再試");
  }
}
```

## 資料模型

無新增資料模型。本票不新增/變更任何資料表、欄位或索引,亦不新增/變更
後端 API 契約(`DELETE /articles/{id}` 已由 SDLCAIP1-7/9 提供)。

## 關鍵技術決策

- **確認 UI 採用原生 `window.confirm()`,不引入自訂 Modal 元件**:規格
  明訂確認 UI 元件形式範圍外,只要求「明確、需使用者主動確認的步驟」。
  `window.confirm()` 是瀏覽器原生同步阻斷式對話框,天然滿足「使用者
  必須主動選擇確認或取消才能繼續」的要求,且不需新增任何元件/樣式/
  焦點管理邏輯(自訂 Modal 需處理鍵盤焦點、ESC 關閉、遮罩點擊等,規格
  未要求這些細節,屬於本票不必要的額外複雜度)。若未來有票要求自訂
  視覺風格的確認對話框,可在該票替換此處實作,呼叫端介面
  (`handleDeleteClick` 內部邏輯)不受影響。

- **404 與 502 均視為「已刪除」從列表移除,但用不同的非阻斷訊息文案
  區分**:直接沿用規格驗收條件 3、5 的明確指示(規格已明講兩者都要
  移除,只是訊息不同),不是本設計自行決定的產品行為。「非阻斷」的
  具體實作方式為:訊息顯示在頁面上但不使用 `window.alert()`
  (阻斷式對話框會打斷操作流程,與「非阻斷」字面矛盾),而是用元件
  state(`notice`)渲染一段可視訊息文字,使用者可繼續操作列表其餘
  項目;訊息不需要使用者手動關閉(規格未要求),沿用既有頁面「下一次
  操作/重新載入即覆蓋前一則訊息」的最簡處理,不引入 toast 函式庫。

- **`notice`(非阻斷提示/警示,對應 404/502)與 `error`(可重試的失敗
  訊息,對應驗收條件 6)分開用兩個獨立 state,不合併成單一「訊息」
  state**:兩者語意不同——`notice` 情境下刪除已經發生(文章已從列表
  移除,不需要使用者重試任何動作);`error` 情境下刪除未發生(文章
  仍在列表,使用者可能需要重新點擊刪除)。合併成單一 state 會讓「是否
  重試」的可視線索(文章是否還在列表)與訊息文字所在位置耦合不清,
  分開命名可讓實作與測試明確對應各自的驗收條件(3/5 用 `notice`,6 用
  `error`)。沿用 `ArticlesList.tsx` 現有的 `error` state 語意(目前
  用於列表載入失敗)供刪除的驗收條件 6 復用,不重新命名既有 state。

- **刪除流程沿用 `ArticlesList.tsx` 既有的錯誤分支順序慣例
  (401 優先,見 SDLCAIP1-19 設計文件的資料載入分支)**:刪除的
  `catch` 區塊同樣先判斷 401 呼叫 `useHandleUnauthorized()`,再判斷
  404、502,最後才是「其他」的通用分支,與既有列表載入邏輯及
  SDLCAIP1-13 表單邏輯的「401 優先判斷」順序一致,避免不同頁面對同一
  錯誤碼有不同的判斷優先順序造成維護時的認知負擔。

- **刪除成功(204)後從列表 state 直接移除該筆文章,不重新呼叫
  `listArticles` 整頁重新載入**:規格驗收條件 1 只要求「該文章從列表
  移除,其餘不變」,未要求重新整頁抓取最新分頁資料(是否因為刪除導致
  當頁筆數變化而需要調整分頁,已明訂為範圍外,沿用 SDLCAIP1-19 既有
  分頁行為)。就地移除是滿足此驗收條件最小、且不觸發額外 API 呼叫的
  作法;`totalPages`/`page` state 維持不變。

## 前端目錄/檔案結構(新增/變更)

```
frontend/src/
  api/
    articles.ts       # 新增:deleteArticle()
  pages/
    ArticlesList.tsx  # 變更:刪除按鈕 onClick 改為呼叫 handleDeleteClick,
                       #   新增 notice state,沿用既有 error state
```

## 開放設計問題(定稿時必須為空)

無。
