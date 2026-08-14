# 設計文件 — SDLCAIP1-24 首頁文章列表靜態頁重新產生（更新／刪除文章觸發）

## 對應需求規格

G1 通過版本：作為網站訪客，文章被更新或刪除後，首頁文章列表（含分頁）能同步反映
異動。驗收條件（Gherkin，共 4 條）：

1. 更新文章的 `published_at` 後，受影響的分頁靜態 HTML 重新產生並上傳，文章出現
   在正確排序位置（新→舊）。
2. 刪除文章後，對應分頁的靜態 HTML 重新產生並上傳，該頁不再包含被刪除的文章。
3. 刪除最後一篇文章後，首頁第一頁重新產生為空狀態頁面。
4. 更新/刪除觸發的列表頁上傳失敗時，比照 SDLCAIP1-9 既有錯誤處理慣例回報
   （502 / `STATIC_PAGE_*_FAILED` 類型），不讓錯誤被靜默吞掉。

範圍外（已定案，不重新討論）：`create_article` 觸發的列表頁產生與核心分頁邏輯本身
（SDLCAIP1-23 已提供，本票僅重用/視需要局部調整其共用函式）、文章詳細頁渲染
（SDLCAIP1-20）、前端搜尋（SDLCAIP1-16）、分類/標籤、後台管理 UI、「多餘舊分頁」
清理策略（本票只重新產生「仍存在頁數範圍內」的分頁，不處理總頁數縮減後的舊分頁
清除）、列表頁視覺樣式細節（沿用 SDLCAIP1-20 共用版型）。

架構決策依據：HUMAN-INPUT SDLCAIP1-22，已核准選項 A——異動時於觸發端點（本票即
`update_article`／`delete_article`）後端觸發點重新產生所有分頁，不建獨立批次流程。

依賴：blocked by SDLCAIP1-23（已提供 `LIST_PAGE_SIZE`／`_list_page_key`／
`_render_list_page_html`／`_generate_and_upload_list_pages` 共用邏輯，設計階段
SDLCAIP1-23 尚未合併進 `src/cms_aipilot/main.py`，本文件依其設計文件所定的函式簽章
作為契約）、SDLCAIP1-9（既有 `update_article`／`delete_article` 觸發與錯誤處理慣例，
見下「現況」）、SDLCAIP1-20（共用版型 `_ARTICLE_PAGE_STYLE`）。

## 現況（變更基準，讀自目前 `src/cms_aipilot/main.py`）

- `update_article`（第 276–295 行）：確認文章存在後 `table.put_item(...)` 覆寫整筆
  item，再呼叫 `_publish_or_rollback(updated, table)`（第 201–220 行）。該函式**目前
  只**產生/上傳單篇文章靜態頁（`articles/{id}.html`）；失敗時 rollback 動作是
  `table.delete_item(Key={"id": article.id})`——即把整筆文章從 DynamoDB
  **刪除**，而非還原成更新前的版本（該表沒有版本歷史，update 是覆寫，沒有「還原
  上一版」的資料可用）。這是 SDLCAIP1-9 定案時就存在的既有行為，本票不改變它，
  只在其失敗判定範圍內加入列表頁上傳。失敗回應維持既有 502
  `STATIC_PAGE_GENERATION_FAILED`（同 create_article 用的同一個常數）。

- `delete_article`（第 298–318 行）：確認文章存在後**直接** `table.delete_item(...)`
  （無條件執行，成功後才進下一步），再呼叫 `_delete_static_page(article_id)`
  刪除該文章的 `articles/{id}.html`；若刪除失敗，回傳既有 502
  `STATIC_PAGE_DELETION_FAILED`（`error_code`/`detail`/`article_id` 欄位）。**此路徑
  沒有任何 rollback**——DynamoDB 的刪除已經是既成事實，即使後續 S3 清理失敗也不會
  復原該筆資料；502 純粹是「告知呼叫端有一部分清理沒完成」，不是「這次刪除沒有
  發生」。這與 create/update 的「失敗即整筆回滾」語意不同，是本票必須沿用、而非
  統一的既有慣例。

- 目前**沒有**列表頁在 `update_article`/`delete_article` 成功後被重新產生——
  `index.html`/`page/*.html` 只會（依 SDLCAIP1-23 設計，尚未合併）在
  `create_article` 觸發，本票補上 update/delete 這兩個觸發點。

## 介面/API 契約

四個端點請求/成功回應格式**皆不變**（`update_article` 仍 `200`＋`Article` body；
`delete_article` 仍 `204` 無 body）。本票變更的是各自成功路徑後新增的**副作用**
（列表分頁 S3 object 重新上傳）與對應的**失敗回應**。

### `PUT /articles/{id}`（`update_article`）

- 成功（DynamoDB 覆寫 + 單篇文章靜態頁 + **所有**列表分頁皆上傳成功）：`200 OK`，
  body 為更新後的 `Article`，不變。
- 失敗（DynamoDB 覆寫成功後，單篇文章靜態頁**或**任一列表分頁上傳失敗）：沿用既有
  502 `STATIC_PAGE_GENERATION_FAILED`（同 create_article/現行 update_article 用的
  同一常數，不新增錯誤碼），並執行既有 rollback（`table.delete_item`，即把該文章
  整筆刪除——沿用既有行為，本票不修正此語意，見下「關鍵技術決策」）。

  函式變更：擴充現有 `_publish_or_rollback(article, table)`（SDLCAIP1-23 合併後，
  此函式唯一呼叫端只剩 `update_article`——`create_article` 屆時已改呼叫
  SDLCAIP1-23 新增的 `_publish_article_and_lists_or_rollback`），內部依序：
  1. `_generate_and_upload_static_page(article)`（不變）
  2. 成功後接著呼叫 `_generate_and_upload_list_pages(table)`（SDLCAIP1-23 提供）
  3. 任一步驟拋出 `StaticPageGenerationError` → 執行既有 rollback
     （`table.delete_item(Key={"id": article.id})`，雙重失敗僅 log，行為不變）→
     回傳既有 502 JSONResponse。
  4. 全部成功回傳 `None`。

  `update_article` 呼叫端程式碼（`_publish_or_rollback(updated, table)`）**不需要
  改動**——擴充在函式內部完成。

### `DELETE /articles/{id}`（`delete_article`）

- 成功（DynamoDB 刪除 + 單篇文章靜態頁刪除 + **所有**列表分頁皆重新上傳成功）：
  `204 No Content`，不變。
- 單篇文章靜態頁刪除失敗：沿用既有 502 `STATIC_PAGE_DELETION_FAILED`（格式不變），
  此時**不**嘗試列表頁重新產生（維持現有「先刪單篇頁，失敗就先回報」的順序，不
  疊加第二種失敗一起處理，降低單一失敗路徑要判斷兩種原因的複雜度）。
- 單篇文章靜態頁刪除成功、但列表頁重新產生/上傳失敗：新增回應（沿用既有慣例的
  命名風格，同屬 502 家族，`STATIC_PAGE_*_FAILED` 類型）：
  ```json
  {
    "error_code": "STATIC_LIST_PAGE_REGENERATION_FAILED",
    "detail": "Article deleted but the homepage list pages could not be regenerated.",
    "article_id": "<article_id>"
  }
  ```
  狀態碼 `502`。同樣**沒有 rollback**（DynamoDB 刪除已成立，與現行
  `STATIC_PAGE_DELETION_FAILED` 路徑一致的「告知未完成清理，不復原」語意）。

  `delete_article` 內部流程調整為：
  ```
  table.delete_item(...)                      # 不變
  try: _delete_static_page(article_id)         # 不變
  except StaticPageDeletionError: return 502 STATIC_PAGE_DELETION_FAILED  # 不變

  try: _generate_and_upload_list_pages(table)   # 新增
  except StaticPageGenerationError: return 502 STATIC_LIST_PAGE_REGENERATION_FAILED  # 新增

  return Response(status_code=204)              # 不變
  ```

### 對 `_generate_and_upload_list_pages`（SDLCAIP1-23）的必要調整

SDLCAIP1-23 設計文件中，此函式的呼叫時機（僅 `create_article` 成功寫入後）保證
`scan()` 讀到的 `total` 恆 ≥ 1，因此當時的分頁迴圈（依 `total_pages =
math.ceil(total/LIST_PAGE_SIZE)`，`total_pages` 為 0 時迴圈不執行）從未在
`total == 0` 的情況下被呼叫過。本票的 `delete_article` 觸發點會出現「刪除最後一篇
文章後 `total == 0`」的情況（AC3），此時若沿用原迴圈，`total_pages == 0` 會導致
**完全不呼叫** `_render_list_page_html`／不上傳任何頁面，S3 上的 `index.html` 會
維持刪除前的舊內容（不是空狀態，是不同步）。

因此本票要求對 `_generate_and_upload_list_pages` 做以下調整（不影響
`create_article` 既有呼叫情境的行為，因為 `total > 0` 時計算結果完全相同）：

```python
def _generate_and_upload_list_pages(table) -> None:
    """...（既有 docstring 不變）...
    total_pages 至少為 1：即使 table 目前沒有任何文章（total == 0），仍會產生並
    上傳第 1 頁（index.html）作為空狀態頁面（page_items 為空、total_pages=1），
    確保 S3 上的列表頁不會停留在刪除前的舊內容。"""
    total_pages = max(1, math.ceil(total / LIST_PAGE_SIZE)) if total else 1
    for page in range(1, total_pages + 1):
        ...  # 其餘邏輯不變
```

`_render_list_page_html(page_items=[], page=1, total_pages=1)` 在既有版型下自然
產生「`<ul class="article-list">` 內無任何 `<li>`、`<nav class="pagination">` 內因
`page == total_pages == 1` 不出現上一頁/下一頁連結」的頁面——不需要另外設計專門的
空狀態樣板（沿用 SDLCAIP1-23 已定案「不另外設計空狀態樣板」的判斷，只是把它套用
到本票新出現的 `total == 0` 情境）。

## 資料模型

無新增資料模型。不新增 DynamoDB 欄位、資料表或索引；沿用 SDLCAIP1-23 的
`articles` 表即時 `scan()` 作為列表頁重新產生的資料來源。

## 關鍵技術決策

- **擴充既有 `_publish_or_rollback` 本體，而非另開新函式給 update_article**：
  SDLCAIP1-23 合併後，此函式唯一呼叫端只剩 `update_article`（`create_article`
  改用 SDLCAIP1-23 新增的 `_publish_article_and_lists_or_rollback`），因此直接在
  `_publish_or_rollback` 內加入列表頁生成步驟只會影響 update 這一條路徑，不會像
  SDLCAIP1-23 撰寫當下（`update_article` 仍共用此函式）那樣有「連帶影響
  update_article 未核准行為」的風險。呼叫端程式碼因此不需要改動，降低變更面積。

- **update 的失敗回應與 rollback 動作沿用既有 `STATIC_PAGE_GENERATION_FAILED` +
  `table.delete_item`，不修正「rollback 其實是刪除整筆」的語意落差**：這是
  SDLCAIP1-9 定案時就存在的既有行為（`articles` 表無版本歷史，物理上無法還原
  「更新前的版本」），修正它是一個獨立的產品/技術決策（例如要不要導入版本欄位或
  改用條件式寫入還原），超出本票「讓列表頁同步反映異動」的範圍，故維持現狀，只
  在既有失敗判定範圍內新增列表頁這個新的失敗來源。

- **delete 失敗回應新增獨立錯誤碼 `STATIC_LIST_PAGE_REGENERATION_FAILED`，不與既有
  `STATIC_PAGE_DELETION_FAILED` 共用**：兩者是不同失敗來源（刪除單篇文章靜態頁
  vs. 重新產生列表頁），呼叫端（例如未來要重試或監控告警的維運腳本）需要能分辨
  是哪一種清理沒完成；命名沿用既有 `STATIC_PAGE_*_FAILED` 前綴風格，符合 AC4
  「比照現有錯誤處理慣例回報」的字面要求（該條驗收條件本身也用「如」字表明允許
  沿用風格產生新識別字串，非要求逐字重用既有碼）。

- **delete 兩種失敗（單篇頁刪除 vs. 列表頁重新產生）依序判斷、不合併成單一步驟**：
  維持現有程式碼「先刪單篇靜態頁，失敗就先回報」的既有順序與提早返回慣例，只在其
  後補一步；避免把兩個獨立的 S3 操作揉進同一個 try/except，讓錯誤訊息可以準確
  指出是哪一步驟失敗。

- **delete 路徑列表頁重新產生失敗時不做任何 rollback**：與現行
  `STATIC_PAGE_DELETION_FAILED` 路徑一致——DynamoDB 的刪除已成立且不可逆（無「復原
  已刪除文章」的功能），502 純粹是清理未完成的告知，呼叫端可依 `article_id` 之後
  自行重試/人工排查，維持與既有 delete 慣例一致的語意，不新增 create/update 的
  「失敗即整筆回滾」語意到 delete（該語意對 delete 沒有對應的可回滾狀態）。

- **`_generate_and_upload_list_pages` 的 `total_pages` 下限調整為 1**：只有這樣才能
  讓 `total == 0`（AC3：刪除最後一篇文章）時仍然產生並上傳一頁空狀態
  `index.html`，覆蓋掉刪除前的舊內容；`total > 0` 時計算結果與 SDLCAIP1-23 原設計
  完全相同，不影響 `create_article` 既有情境（該情境下 `total` 恆 ≥ 1，此調整不
  可觸達）。

## 開放設計問題（定稿時必須為空）

無。
