# 設計文件 — SDLCAIP1-26 搜尋索引產生（新增文章觸發）

## 對應需求規格

G1 通過版本：作為網站前台訪客，新發布的文章立即被收錄進搜尋索引（含標題與全文），
以便發布後馬上能透過關鍵字搜尋到它。驗收條件（Gherkin，共 4 條）：

1. `create_article` 成功後，`search/index.json` 被重新產生並覆蓋上傳，內容為 JSON
   陣列，含該新文章的項目（至少 `id`/`title`/`content`）。
2. 索引反映資料庫目前全部文章（既有 + 新增），筆數等於資料庫全部文章數。
3. 索引產生/上傳失敗 → 既有 502 `STATIC_PAGE_GENERATION_FAILED`（比照
   SDLCAIP1-8/23 慣例），本次新增的 DynamoDB item 回滾刪除。
4. 第一篇文章建立時，`search/index.json` 首次於 S3 出現，內容為僅含該篇的陣列。

範圍外（已定案，不重新討論）：`update`/`delete` 觸發的索引重新產生
（SDLCAIP1-27，blocked by 本票，已自行假設共用函式契約，見下「與 SDLCAIP1-27 的
介面對齊」）、前台搜尋 UI/比對/呈現（SDLCAIP1-28）、索引欄位除
`id`/`title`/`content`/`published_at` 以外的擴充、索引檔案分頁/分割、後台管理
UI 的搜尋/篩選。

架構決策依據：HUMAN-INPUT SDLCAIP1-25，已核准 Q1 選項 A（同步觸發）、Q2 選項 B
（索引含全文 `content`）、Q5 選項 B（路徑 `search/index.json`）。

依賴：SDLCAIP1-8/9（既有 create 觸發模式、S3 上傳/回滾慣例）、SDLCAIP1-23（「新增
時同步重建全量靜態輸出」模式先例：`_publish_article_and_lists_or_rollback`、
`ConsistentRead=True` scan、`StaticPageGenerationError` 重用）。

## 現況（變更基準，讀自目前 `src/cms_aipilot/main.py`）

- `create_article`（第 343–358 行）：`table.put_item(...)` 後呼叫
  `_publish_article_and_lists_or_rollback(created, table)`（第 318–340 行，
  SDLCAIP1-23 新增，僅供 `create_article` 使用，不影響 `update_article` 的
  `_publish_or_rollback`）。該函式依序執行 `_generate_and_upload_static_page`
  （單篇文章頁）與 `_generate_and_upload_list_pages`（首頁列表分頁）；任一步驟
  拋出 `StaticPageGenerationError` 即 `table.delete_item` 回滾、回傳既有 502
  `STATIC_PAGE_GENERATION_FAILED_RESPONSE`（第 195–198 行）。
- `_generate_and_upload_list_pages`（第 287–315 行）已示範本票要沿用的模式：
  `table.scan(ConsistentRead=True)` → 排序/整理 → `s3.put_object` 上傳；
  `total == 0` 時仍上傳空狀態內容，不略過上傳。
- `StaticPageGenerationError`（第 131–135 行）建構參數為 `(article_id: str,
  cause: Exception)`，log 訊息與「文章」或「頁面」無關，只是失敗識別字串——
  SDLCAIP1-23 已示範重用它代表 `"list-page-{N}"`。
- 目前**沒有**任何機制產生/上傳 `search/index.json`。

## 與 SDLCAIP1-27 的介面對齊

SDLCAIP1-27 設計階段（blocked by 本票）已自行假設本票會提供以下簽章：

```python
SEARCH_INDEX_KEY = "search/index.json"

def _build_search_index_entry(item: dict) -> dict: ...
def _generate_and_upload_search_index(table) -> None: ...
```

本文件維持與該假設**完全一致**的簽章與行為契約（函式名稱、參數、常數名、`"space
-index"` 例外識別字串命名——見下方「新增內部函式簽章」），不做調整。SDLCAIP1-27
不需要重新走設計流程即可對齊本票實際合併後的程式碼。

## 介面/API 契約

`POST /articles`（`create_article`）的請求/成功回應格式**不變**（`201`，body 為
既有 `Article` model）。本票新增的是成功路徑的**副作用**（多寫入一個 S3
object）與失敗路徑的**觸發條件擴大**：

- 成功（DynamoDB 寫入 + 單篇文章靜態頁 + 所有列表分頁 + 搜尋索引皆上傳成功）：
  `201 Created`，body 不變。
- 失敗（上述任一步驟失敗）：沿用既有 502 `STATIC_PAGE_GENERATION_FAILED`（不新增
  錯誤碼——AC3 字面即要求沿用此碼），回滾動作不變（`table.delete_item(Key={"id":
  article.id})`；雙重失敗僅 `logger.error`，不重試）。

`update_article`、`delete_article`、`GET /articles`、`GET /articles/{id}` 的行為
**完全不變**——本票只擴充 `create_article` 的成功/失敗路徑。

### `search/index.json` S3 Key 與內容契約（本票定案）

- Key：`search/index.json`（HUMAN-INPUT SDLCAIP1-25 Q5 選項 B 核准），與
  `articles/`、`page/` 同層級並列的「用途前綴目錄」命名風格一致。
- `ContentType`：`"application/json"`。
- Body：JSON 陣列，每個元素為

  ```json
  {
    "id": "<article id>",
    "title": "<article title>",
    "content": "<article full content>",
    "published_at": "<ISO 8601 字串，item 原始儲存格式>"
  }
  ```

  欄位依 HUMAN-INPUT SDLCAIP1-25 Q2 選項 B 核准：`content` 為全文，不截斷/摘要。
  `published_at` 維持 DynamoDB item 原始 ISO 字串，不重新格式化（供
  SDLCAIP1-28 前端 JS 直接使用）。
- `total == 0` 時（理論上 `create_article` 的呼叫時機下 scan 至少讀到剛寫入的
  一筆，見「關鍵技術決策」）仍序列化並上傳 `[]`，不略過上傳——比照
  `_generate_and_upload_list_pages` 的既有處理，維持一致性以供 SDLCAIP1-27
  的 delete 路徑（刪除最後一篇文章）重用同一函式時行為正確。
- 陣列順序：不要求排序（前台搜尋 SDLCAIP1-28 為純前端子字串比對，不依賴索引
  陣列順序），維持 `scan()` 回傳順序即可，不額外排序。

### 新增內部函式簽章（developer 依此實作，不用自行發明）

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

`_publish_article_and_lists_or_rollback`（第 318–340 行）擴充為在既有 `try` 區塊
內、`_generate_and_upload_list_pages(table)` 之後追加一步：

```python
def _publish_article_and_lists_or_rollback(article: Article, table) -> JSONResponse | None:
    try:
        _generate_and_upload_static_page(article)
        _generate_and_upload_list_pages(table)
        _generate_and_upload_search_index(table)          # 新增
    except StaticPageGenerationError as upload_exc:
        ...  # rollback + 502，完全不變（三個步驟共用同一個 except）
    return None
```

`create_article` 呼叫端程式碼（`_publish_article_and_lists_or_rollback(created,
table)`）**不需要改動**——擴充在函式內部完成，與 SDLCAIP1-23 當時擴充加入
`_generate_and_upload_list_pages` 的模式一致。

## 資料模型

無新增資料模型。不新增 DynamoDB 欄位、資料表或索引。索引所需的全部文章資料來自
既有 `articles` 表即時 `scan()`，與 `_generate_and_upload_list_pages` 同一張表、
同一種讀取方式（`ConsistentRead=True`）。`search/index.json` 本身是 S3 object，
不是資料庫層的資料模型變更。

## 關鍵技術決策

- **在既有 `_publish_article_and_lists_or_rollback` 內追加一個步驟，而非另開新
  函式**：該函式已是 SDLCAIP1-23 定案的「依序執行多個 S3 副作用，任一失敗即回報」
  模式，搜尋索引只是同一模式下的第三個步驟，沿用既有結構降低變更面積，與
  SDLCAIP1-23 當時在 `_publish_or_rollback`/`_publish_article_and_lists_or_
  rollback` 疊加列表頁步驟的做法一致。

- **搜尋索引上傳失敗與既有單篇頁/列表頁失敗共用同一個 502
  `STATIC_PAGE_GENERATION_FAILED` 與同一個 rollback 動作**：AC3 字面明確要求沿用
  既有 502 `STATIC_PAGE_GENERATION_FAILED` 慣例（未要求新錯誤碼），且三個上傳
  步驟對訪客而言都是「這次發文沒有完整上線」，用同一個
  `StaticPageGenerationError` 例外與同一個 `except` 區塊處理，不新增第三種部分
  失敗狀態需要規格額外決定如何呈現。

- **`table.scan(ConsistentRead=True)`，而非預設 eventually consistent scan**：
  `_generate_and_upload_search_index` 在 `create_article` 剛 `put_item` 成功後
  立刻被呼叫，若用預設 eventually consistent scan，理論上可能讀不到剛寫入的
  那筆，導致 AC1「索引含該新文章」在極端情況下失敗。與
  `_generate_and_upload_list_pages` 同一取捨（用效能換正確性，非高頻路徑）。

- **重用 `StaticPageGenerationError`（傳入 `"search-index"` 作為 `article_id`
  參數），不新增獨立例外類別**：該類別的建構參數/log 訊息本來就與具體是「文章」
  「頁面」還是「索引」無關，只是一個失敗識別字串；SDLCAIP1-23 已示範用
  `"list-page-{N}"` 重用同一模式。新增平行例外類別只會讓
  `_publish_article_and_lists_or_rollback` 需要 catch 多種例外類型，徒增複雜度
  而無實質差異。

- **索引 `total == 0` 時仍上傳空陣列 `[]`，不略過上傳**：比照
  `_generate_and_upload_list_pages` 對 `total == 0` 的既有處理，保持兩者行為
  一致；更重要的是這是 SDLCAIP1-27（delete 觸發）將重用的同一函式的通用契約——
  SDLCAIP1-27 的 AC3（刪除最後一篇文章後索引成為空陣列）完全依賴此行為，若本票
  的實作在空清單時略過上傳，會讓 SDLCAIP1-27 的驗收條件失效。雖然在
  `create_article` 觸發路徑下（`put_item` 成功後才呼叫）`scan()` 實務上恆
  `total ≥ 1`，此保證仍寫入函式契約以確保跨呼叫端的一致行為。

- **陣列不額外排序**：搜尋索引不像列表頁需要「由新到舊」呈現順序——
  SDLCAIP1-28（前台搜尋，範圍外）為純前端子字串比對，AC 對排序沒有任何要求，
  維持 `scan()` 回傳順序即可，避免無謂的排序成本與未來若排序邏輯變動時的
  維護負擔。

- **函式簽章與 SDLCAIP1-27 設計階段的假設完全一致，不調整**：SDLCAIP1-27 已
  自行定義 `SEARCH_INDEX_KEY`、`_build_search_index_entry`、
  `_generate_and_upload_search_index` 的簽章與行為契約（含空陣列上傳保證、
  `ensure_ascii=False`、`StaticPageGenerationError("search-index", exc)`）。
  本票定案後與該假設沒有落差，SDLCAIP1-27 不需要因本票調整設計。

## 開放設計問題（定稿時必須為空）

無。
