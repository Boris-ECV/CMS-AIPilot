# 設計文件 — SDLCAIP1-27 搜尋索引重新產生（更新／刪除文章觸發）

## 對應需求規格

G1 通過版本：作為網站前台訪客，文章被更新或刪除後，搜尋索引（`search/index.json`）
能同步反映異動，避免搜尋到已刪除或已過期的內容。驗收條件（Gherkin，共 5 條）：

1. 更新文章後索引反映最新標題/內容。
2. 刪除文章後索引不再包含該文章。
3. 刪除最後一篇文章後索引成為空陣列 `[]`。
4. 更新觸發的索引上傳失敗 → 502 `STATIC_PAGE_GENERATION_FAILED` + DynamoDB 回滾。
5. 刪除觸發的索引上傳失敗 → 502（同類命名風格如
   `STATIC_LIST_PAGE_REGENERATION_FAILED`），無回滾。

範圍外（已定案，不重新討論）：`create_article` 觸發的索引首次產生
（SDLCAIP1-26）、前台搜尋頁面 UI（SDLCAIP1-28）、`update` 「rollback 其實是整筆
刪除」既有語意落差的修正（沿用 SDLCAIP1-24 已定案：超出範圍）、舊索引項目的版本
歷史/還原機制。

架構決策依據：HUMAN-INPUT SDLCAIP1-25（已核准）——索引含 `id`/`title`/`content`
（全文）/`published_at`，S3 路徑 `search/index.json`。

依賴：**is blocked by SDLCAIP1-26**（提供索引首次產生的共用函式，設計階段
SDLCAIP1-26 尚未合併進 `src/cms_aipilot/main.py`，本文件依下方「共用函式契約」
自行定義 SDLCAIP1-26 應提供的簽章，比照 SDLCAIP1-24 當時對 SDLCAIP1-23 的處理
方式——**若 SDLCAIP1-26 實際合併後的簽章與本文件不同，開發階段以 SDLCAIP1-26
合併後的實際程式碼為準**，本票 developer 需相應調整呼叫方式，不需要重新走設計
階段）；SDLCAIP1-24（update/delete 觸發同步重建的既有模式先例，見下「現況」）。

## 現況（變更基準，讀自目前 `src/cms_aipilot/main.py`）

- `update_article`（第 396–415 行）：確認文章存在後 `table.put_item(...)` 覆寫整筆
  item，呼叫 `_publish_or_rollback(updated, table)`（第 201–225 行）。該函式**目前**
  依序執行 `_generate_and_upload_static_page(article)`（單篇文章頁）與
  `_generate_and_upload_list_pages(table)`（SDLCAIP1-23/24，首頁列表分頁）；任一步
  驟拋出 `StaticPageGenerationError` 即執行 rollback（`table.delete_item`，把整筆
  文章從 DynamoDB 刪除，非「還原成更新前版本」——SDLCAIP1-9 定案時的既有行為，本票
  不改變）並回傳既有 502 `STATIC_PAGE_GENERATION_FAILED`（`STATIC_PAGE_GENERATION_
  FAILED_RESPONSE` 常數，第 195–198 行）。

- `delete_article`（第 418–453 行）：確認文章存在後直接 `table.delete_item(...)`
  （無條件執行），依序執行兩個獨立、各自 try/except 的步驟：
  1. `_delete_static_page(article_id)`——失敗回傳既有 502
     `STATIC_PAGE_DELETION_FAILED`，**不**接續下一步。
  2. `_generate_and_upload_list_pages(table)`（SDLCAIP1-23/24）——失敗回傳 502
     `STATIC_LIST_PAGE_REGENERATION_FAILED`（新錯誤碼，SDLCAIP1-24 定案）。
  兩步驟皆成功才回傳 `204`。**此路徑沒有任何 rollback**——DynamoDB 的刪除已是既成
  事實，502 純粹是清理未完成的告知，本票沿用此語意。

- `_generate_and_upload_list_pages`（第 287–315 行）已示範本票要沿用的模式：
  `table.scan(ConsistentRead=True)` → 排序/整理 → `s3.put_object` 上傳；`total == 0`
  時仍上傳「空狀態」內容（見 SDLCAIP1-24 對 `total_pages` 下限的調整），不略過
  上傳，避免 S3 上殘留刪除前的舊內容——本票的搜尋索引函式需要同樣的「空清單也要
  上傳」保證（對應 AC3）。

- 目前**沒有**任何機制產生/上傳 `search/index.json`——SDLCAIP1-26（尚未實作）將
  補上 `create_article` 觸發的首次產生，本票補上 update/delete 這兩個觸發點。

## 共用函式契約（由 SDLCAIP1-26 提供，本票依此契約撰寫）

> **注意**：以下簽章由本文件（SDLCAIP1-27 設計階段）先行定義，供兩票並行設計時
> 對齊介面；SDLCAIP1-26 是實際提供方。若 SDLCAIP1-26 合併後的簽章與此不同，
> **一律以 SDLCAIP1-26 合併後的實際程式碼為準**，developer 在實作本票時需對照
> 當時 `main.py` 現況調整，不需另外走設計流程。

```python
SEARCH_INDEX_KEY = "search/index.json"


def _build_search_index_entry(item: dict) -> dict:
    """將 DynamoDB 原始 item dict（含 id/title/content/published_at 字串）轉為
    索引項目 {"id", "title", "content", "published_at"}（HUMAN-INPUT SDLCAIP1-25
    核准欄位：content 為全文，不截斷/摘要）。published_at 維持 ISO 字串
    （item 原始儲存格式，不重新格式化），供前端 SDLCAIP1-28 的 vanilla JS 直接
    使用，不需額外的日期解析。"""


def _generate_and_upload_search_index(table) -> None:
    """對 `table` 做 ConsistentRead=True 的 scan()，對每筆 item 呼叫
    _build_search_index_entry，組成 JSON 陣列（json.dumps(..., ensure_ascii=False)
    以正確輸出中文全文，不轉義成 \\uXXXX），以 s3.put_object 上傳至
    SEARCH_INDEX_KEY（ContentType="application/json"）。scan() 回傳空清單時仍
    上傳空陣列 `[]`（不略過上傳——比照 _generate_and_upload_list_pages 對
    total == 0 的既有處理）。上傳失敗即拋出
    StaticPageGenerationError("search-index", exc)（沿用既有例外類別，
    'search-index' 作為 log 訊息的識別字串，不新增例外類別）。"""
```

- `_generate_and_upload_search_index` 由 SDLCAIP1-26 在 `create_article` 觸發路徑
  提供並使用；本票（update/delete）重用同一函式，不重新實作 scan/組陣列/上傳邏輯。
- 排序：與 `_generate_and_upload_list_pages` 不同，索引本身不做分頁/呈現排序（前台
  搜尋頁 SDLCAIP1-28 純前端子字串比對，不依賴索引陣列順序），因此契約不要求
  `_generate_and_upload_search_index` 對 `items` 排序——這是 SDLCAIP1-26 的實作
  細節，本票的 AC 不對排序有任何要求，不在此定案。

## 介面/API 契約

`PUT /articles/{id}`（`update_article`）與 `DELETE /articles/{id}`（`delete_article`）
的請求/成功回應格式**皆不變**（`update_article` 仍 `200` + `Article` body；
`delete_article` 仍 `204` 無 body）。本票變更的是各自成功路徑後新增的**副作用**
（`search/index.json` 重新上傳）與對應的**失敗回應**。

### `PUT /articles/{id}`（`update_article`）

- 成功（DynamoDB 覆寫 + 單篇文章靜態頁 + 所有列表分頁 + 搜尋索引皆上傳成功）：
  `200 OK`，body 為更新後的 `Article`，不變。
- 失敗（DynamoDB 覆寫成功後，單篇文章靜態頁、任一列表分頁、**或搜尋索引**上傳
  失敗）：沿用既有 502 `STATIC_PAGE_GENERATION_FAILED`（`STATIC_PAGE_GENERATION_
  FAILED_RESPONSE`，不新增錯誤碼——AC4 字面即要求沿用此碼），並執行既有 rollback
  （`table.delete_item(Key={"id": article.id})`）。

  函式變更：擴充現有 `_publish_or_rollback(article, table)`（第 201–225 行），在
  既有 `try` 區塊內、`_generate_and_upload_list_pages(table)` 之後追加：

  ```python
  def _publish_or_rollback(article: Article, table) -> JSONResponse | None:
      try:
          _generate_and_upload_static_page(article)
          _generate_and_upload_list_pages(table)
          _generate_and_upload_search_index(table)          # 新增
      except StaticPageGenerationError as upload_exc:
          ...  # rollback + 502，完全不變（三個步驟共用同一個 except）
      return None
  ```

  `update_article` 呼叫端程式碼（`_publish_or_rollback(updated, table)`）**不需要
  改動**——擴充在函式內部完成，與 SDLCAIP1-24 當時擴充同一函式的模式一致。

### `DELETE /articles/{id}`（`delete_article`）

- 成功（DynamoDB 刪除 + 單篇文章靜態頁刪除 + 所有列表分頁 + 搜尋索引皆重新上傳
  成功）：`204 No Content`，不變。
- 單篇文章靜態頁刪除失敗：沿用既有 502 `STATIC_PAGE_DELETION_FAILED`，此時**不**
  嘗試列表頁或搜尋索引重新產生（維持既有「先刪單篇頁，失敗就先回報」順序，不變）。
- 單篇文章靜態頁刪除成功、列表頁重新產生失敗：沿用既有 502
  `STATIC_LIST_PAGE_REGENERATION_FAILED`，此時**不**嘗試搜尋索引重新產生（同樣的
  「依序判斷、失敗就先回報」原則）。
- 單篇文章靜態頁刪除、列表頁重新產生皆成功，**搜尋索引**上傳失敗：新增回應（沿用
  既有慣例命名風格，同屬 502 家族）：
  ```json
  {
    "error_code": "STATIC_SEARCH_INDEX_REGENERATION_FAILED",
    "detail": "Article deleted but the search index could not be regenerated.",
    "article_id": "<article_id>"
  }
  ```
  狀態碼 `502`。**沒有 rollback**（DynamoDB 刪除已成立，與現行
  `STATIC_PAGE_DELETION_FAILED`/`STATIC_LIST_PAGE_REGENERATION_FAILED` 路徑一致的
  「告知未完成清理，不復原」語意）。

  `delete_article` 內部流程調整為：

  ```python
  table.delete_item(...)                                # 不變
  try: _delete_static_page(article_id)
  except StaticPageDeletionError: return 502 STATIC_PAGE_DELETION_FAILED   # 不變

  try: _generate_and_upload_list_pages(table)
  except StaticPageGenerationError: return 502 STATIC_LIST_PAGE_REGENERATION_FAILED  # 不變

  try: _generate_and_upload_search_index(table)                            # 新增
  except StaticPageGenerationError: return 502 STATIC_SEARCH_INDEX_REGENERATION_FAILED  # 新增

  return Response(status_code=204)                       # 不變
  ```

### AC3（刪除最後一篇文章後索引成為空陣列 `[]`）

由 `_generate_and_upload_search_index`（SDLCAIP1-26 提供）的契約保證：`scan()`
回傳空清單時仍序列化並上傳 `[]`，不略過上傳步驟（比照 SDLCAIP1-24 對
`_generate_and_upload_list_pages` 在 `total == 0` 時仍上傳空狀態頁的既有處理）。
本票（`delete_article`）呼叫此函式的時機是在 `table.delete_item` 之後、
`ConsistentRead=True` 的 scan 保證讀到刪除後的最新狀態，故刪除最後一篇文章後
`items == []`，索引正確變成空陣列。此行為本身由 SDLCAIP1-26 的函式契約提供，
本票不需要額外處理，只需正確呼叫。

## 資料模型

無新增資料模型。不新增 DynamoDB 欄位、資料表或索引；沿用既有 `articles` 表即時
`scan()` 作為搜尋索引重新產生的資料來源（與 `_generate_and_upload_list_pages`
同一張表、同一種讀取方式）。`search/index.json` 本身是 S3 object，不是資料庫
資料模型變更；其結構（`id`/`title`/`content`/`published_at` 陣列）已由 HUMAN-INPUT
SDLCAIP1-25 核准，非本票決定範圍。

## 關鍵技術決策

- **在既有 `_publish_or_rollback`／`delete_article` 內各自追加一個步驟，而非另開
  新函式**：兩者都已是 SDLCAIP1-24 定案的「依序執行多個 S3 副作用，任一失敗即
  回報」模式，搜尋索引只是同一模式下的第三/第四個步驟，沿用既有結構降低變更面積，
  與 SDLCAIP1-24 當時擴充 `_publish_or_rollback` 加入列表頁的做法一致。

- **update 的搜尋索引失敗與既有列表頁/單篇頁失敗共用同一個 502
  `STATIC_PAGE_GENERATION_FAILED` 與同一個 rollback 動作**：AC4 字面明確要求
  `STATIC_PAGE_GENERATION_FAILED`（不是新錯誤碼），且三個上傳步驟對訪客而言都是
  「這次更新沒有完整同步上線」，用同一個 `StaticPageGenerationError` 例外與同一個
  `except` 區塊處理，不新增第三種部分失敗狀態需要規格額外決定如何呈現。

- **delete 新增獨立錯誤碼 `STATIC_SEARCH_INDEX_REGENERATION_FAILED`，不與既有兩個
  delete 錯誤碼共用**：三者是不同失敗來源（刪除單篇文章靜態頁 vs. 重新產生列表頁
  vs. 重新產生搜尋索引），呼叫端需要能分辨是哪一種清理沒完成；命名沿用
  `STATIC_*_FAILED` 前綴風格，符合 AC5「同類命名風格如
  `STATIC_LIST_PAGE_REGENERATION_FAILED`」的字面要求（AC5 本身用「如」字表明允許
  沿用風格產生新識別字串，非要求逐字重用既有碼——與 SDLCAIP1-24 設計 AC4 時的
  判斷一致）。

- **delete 三個步驟依序判斷、後一步只在前一步成功後才執行**：沿用 SDLCAIP1-24
  已定案的既有順序與提早返回慣例，只在其後再疊加一步；避免把三個獨立的 S3 操作
  揉進同一個 try/except，讓錯誤訊息可以準確指出是哪一步驟失敗。

- **delete 路徑搜尋索引重新產生失敗時不做任何 rollback**：與現行
  `STATIC_PAGE_DELETION_FAILED`/`STATIC_LIST_PAGE_REGENERATION_FAILED` 路徑一致——
  DynamoDB 的刪除已成立且不可逆，502 純粹是清理未完成的告知，不新增 delete 沒有
  對應可回滾狀態的「失敗即整筆回滾」語意。

- **AC3（空陣列）不需要本票額外邏輯，完全依賴 SDLCAIP1-26 提供的
  `_generate_and_upload_search_index` 契約中「空清單仍上傳 `[]`」的保證**：這是
  SDLCAIP1-26 該函式的通用行為（不論由 create/update/delete 哪個觸發點呼叫），
  本票只是眾多呼叫端之一，不需要為「最後一篇文章」情境寫特殊分支，與
  `_generate_and_upload_list_pages`（SDLCAIP1-23 提供、SDLCAIP1-24 呼叫）的既有
  分工模式相同。

## 開放設計問題（定稿時必須為空）

無。
