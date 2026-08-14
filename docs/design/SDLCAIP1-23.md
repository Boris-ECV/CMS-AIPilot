# 設計文件 — SDLCAIP1-23 首頁文章列表靜態頁產生（新增文章觸發）

## 對應需求規格

G1 通過版本：作為網站訪客，在有人發布新文章後，首頁文章列表（含分頁）能反映最新
內容，以便瀏覽到最新發布的文章。驗收條件（Gherkin，共 4 條）：

1. 文章數小於一頁容量時，`create_article` 成功後首頁第一頁靜態 HTML 重新產生並
   上傳至 S3，依 `published_at` 由新到舊排序，新文章在最前面。
2. 文章總數超過一頁容量時，`create_article` 成功後對應總頁數的**每一頁**靜態
   HTML 皆重新產生並上傳，每頁只含屬於該頁範圍的文章。
3. 新增第一篇文章（原本 0 篇）時，首頁第一頁顯示該篇文章，不再是空狀態。
4. 任一分頁靜態 HTML 產生/上傳失敗 → 回傳既有 502 `STATIC_PAGE_GENERATION_FAILED`，
   本次新增文章的 DynamoDB 寫入依現有 rollback 邏輯處理。

範圍外（已定案，不重新討論）：文章更新/刪除觸發的重新產生（SDLCAIP1-24，本票
**不**修改 `update_article`/`delete_article` 或它們呼叫的 `_publish_or_rollback`）、
文章詳細頁渲染（SDLCAIP1-20，已合併）、前端搜尋（SDLCAIP1-16）、分類/標籤、後台
管理 UI、舊分頁清理邏輯（新增只會增加文章數，不適用）、列表頁視覺樣式細節（沿用
SDLCAIP1-20 的 `_ARTICLE_PAGE_STYLE` 共用版型）。

架構決策依據：HUMAN-INPUT SDLCAIP1-22，已核准選項 A——異動時於 `create_article`
後端觸發點重新產生所有分頁，不建獨立批次流程。

依賴：SDLCAIP1-8（既有 create 觸發模式：`_publish_or_rollback` 包住
`_generate_and_upload_static_page`，失敗則 `table.delete_item` + 502）、
SDLCAIP1-9（`get_s3_client()`、錯誤處理慣例）、SDLCAIP1-20（`_ARTICLE_PAGE_STYLE`
共用 CSS）。

## 現況（變更基準）

`src/cms_aipilot/main.py`：

- `create_article`（第 223–238 行）：寫入 DynamoDB 後呼叫
  `_publish_or_rollback(created, table)`，該函式只產生/上傳**單篇文章**靜態頁
  （`articles/{id}.html`），失敗則刪除該 DynamoDB item、回傳 502。此函式同時被
  `update_article` 共用（第 292 行）。
- `list_articles`（`GET /articles`，第 241–263 行）：唯一既有分頁慣例——
  `page`/`page_size` query 參數（預設 `page_size=10`），對 DynamoDB 即時
  `table.scan()`、Python 端排序（`published_at` 由新到舊）、`math.ceil` 算
  `total_pages`、slice 出當頁項目。**此端點查活資料，不產生/讀取靜態檔**，本票
  不變更它，只借用其分頁數學與排序邏輯。
- 目前**沒有任何機制**產生首頁列表的靜態 HTML——`index.html` 或任何 `page/*.html`
  在 S3 上從未被本應用程式寫入過。

## 介面/API 契約

`POST /articles`（`create_article`）的請求/成功回應格式**不變**（`201`，body 為
既有 `Article` model）。本票新增的是成功路徑的**副作用**（多寫入若干 S3
object）與失敗路徑的**觸發條件擴大**：

- 成功（DynamoDB 寫入 + 單篇文章靜態頁上傳 + **所有**列表分頁靜態頁上傳皆成功）：
  `201 Created`，body 不變。
- 失敗（DynamoDB 寫入成功後，單篇文章靜態頁**或**任一列表分頁靜態頁上傳失敗）：
  沿用既有 `502 Bad Gateway`：
  ```json
  {
    "error": "STATIC_PAGE_GENERATION_FAILED",
    "message": "Article could not be published: static page upload failed."
  }
  ```
  回滾動作不變：刪除本次新增的 DynamoDB item（`table.delete_item(Key={"id": article.id})`）。
  雙重失敗（rollback delete 也失敗）沿用現況：`logger.error` 記錄，仍回傳同一 502，
  不重試。

`update_article`、`delete_article`、`GET /articles`、`GET /articles/{id}` 的行為
**完全不變**——本票只擴充 `create_article` 的成功/失敗路徑。

### S3 key 慣例（本票定案，範圍內產品決策）

| 頁碼 | S3 Key |
|---|---|
| 第 1 頁 | `index.html` |
| 第 N 頁（N ≥ 2） | `page/{N}.html`（例：`page/2.html`） |

理由：`index.html` 對齊 S3 靜態網站託管（static website hosting）的 index
document 慣例，訪客造訪 bucket 根路徑時預設就會取得第一頁，不需額外的
redirect/rewrite 規則；後續頁面用 `page/{N}.html` 與既有 `articles/{id}.html`
（SDLCAIP1-8 定案）同層級並列，維持「用途前綴目錄」的一致命名風格。

### 靜態列表頁 HTML 結構（輸出契約）

```html
<!DOCTYPE html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>文章列表 - 第 {page} 頁</title>
  <style>{_ARTICLE_PAGE_STYLE}{list-specific CSS，見下}</style>
</head>
<body>
  <ul class="article-list">
    <li class="article-list__item">
      <a class="article-list__link" href="/articles/{id}.html">{title}</a>
      <time class="article-list__meta" datetime="{published_at_iso}">{published_at_display}</time>
    </li>
    <!-- 每篇文章重複一個 <li> -->
  </ul>
  <nav class="pagination">
    <!-- 有上一頁時 -->
    <a href="{prev_href}">上一頁</a>
    <span>第 {page} / {total_pages} 頁</span>
    <!-- 有下一頁時 -->
    <a href="{next_href}">下一頁</a>
  </nav>
</body>
</html>
```

- `{title}`：沿用既有 `html.escape()`（與單篇文章頁一致的轉義邊界）。
- `{published_at_iso}` / `{published_at_display}`：沿用 SDLCAIP1-20 定案格式
  （`.isoformat()` 作機器可讀屬性、`strftime("%Y-%m-%d %H:%M")` 作顯示文字）。
- 連結一律用**絕對根路徑**（`/articles/{id}.html`、`/index.html`、
  `/page/{n}.html`），不用相對路徑——因為 `page/{n}.html` 位於子目錄，若用相對
  路徑（如 `articles/{id}.html`）會被瀏覽器解析成
  `page/articles/{id}.html`，連結壞掉；第 1 頁與第 N 頁若各自用不同深度的相對
  路徑规则，會產生兩套需要分別維護的連結邏輯。統一用絕對路徑消除這個問題。
- `{prev_href}`/`{next_href}` 依上表 key 慣例組出（page 1 對應 `/index.html`）。
- 頁面 CSS：沿用 `_ARTICLE_PAGE_STYLE`（SDLCAIP1-20 定案的響應式基礎樣式），
  額外只加極簡的 `.article-list`/`.pagination` 排版（無底線列表、間距），不重新
  設計視覺（規格明文：視覺樣式細節沿用共用版型、範圍外）。

### 新增內部函式簽章（developer 依此實作，不用自行發明）

```python
LIST_PAGE_SIZE = 10  # 與 GET /articles 現有預設 page_size 一致（第 244 行）

def _list_page_key(page: int) -> str:
    """page=1 -> 'index.html'；page>=2 -> 'page/{page}.html'。"""

def _render_list_page_html(page_items: list[dict], page: int, total_pages: int) -> str:
    """page_items 為 DynamoDB 原始 item dict（含 id/title/published_at 字串）
    的當頁切片，已由呼叫端排序、切好；本函式只負責組 HTML 字串。"""

def _generate_and_upload_list_pages(table) -> None:
    """對 `table` 做 ConsistentRead=True 的 scan()，依 published_at 由新到舊
    排序，依 LIST_PAGE_SIZE 切頁，對每一頁呼叫 _render_list_page_html 並
    s3.put_object 上傳（key 用 _list_page_key）。任一頁上傳失敗即拋出
    StaticPageGenerationError(f"list-page-{page}", exc)（沿用既有例外類別，
    以 'list-page-{N}' 作為識別字串，供 log 訊息使用），中止後續頁面上傳。"""

def _publish_article_and_lists_or_rollback(article: Article, table) -> JSONResponse | None:
    """僅供 create_article 使用（不影響 update_article 既有的
    _publish_or_rollback）。依序呼叫 _generate_and_upload_static_page(article)
    與 _generate_and_upload_list_pages(table)，任一方拋出
    StaticPageGenerationError 即中止，執行既有 rollback
    （table.delete_item(Key={"id": article.id})，雙重失敗僅 log），回傳 502
    JSONResponse；全部成功回傳 None。"""
```

`create_article` 的呼叫從 `_publish_or_rollback(created, table)` 改為
`_publish_article_and_lists_or_rollback(created, table)`；其餘程式碼（`Article`
建構、`table.put_item(...)`、回傳邏輯）不變。

## 資料模型

無新增資料模型。不新增 DynamoDB 欄位、資料表或索引。分頁所需的排序（`published_at`）
與總數（`len(items)`）皆由既有 `articles` 表即時 `scan()` 計算，與 `GET /articles`
（第 241–263 行）採同一來源、同一排序邏輯，不需要另外持久化頁碼或分頁中介資料。

## 關鍵技術決策

- **`LIST_PAGE_SIZE = 10` 為 Python 常數，而非環境變數**：比照現有
  `LOCKOUT_THRESHOLD`/`LOCKOUT_DURATION_SECONDS`（第 29–30 行）的模式——這些是
  應用行為門檻，寫死在程式碼；env var 目前只用於部署期會變的資源識別
  （bucket 名稱、table 名稱）。數值選 10 是為了與 `GET /articles` 現有預設
  `page_size=10`（第 244 行）一致，避免「即時查詢」與「靜態頁」呈現不同頁數
  切法造成訪客困惑。

- **`table.scan(ConsistentRead=True)`，而非沿用 `list_articles` 的預設
  （eventually consistent）scan**：`_generate_and_upload_list_pages` 是在
  `create_article` 剛 `put_item` 成功後立刻呼叫，若用預設 eventually
  consistent scan，理論上可能讀不到剛寫入的那筆（尤其在跨 partition 的
  scan 情境），導致 AC1「新文章出現在最前面」與 AC3「不再是空狀態」在極端
  情況下失敗。`ConsistentRead=True` 保證讀到的資料包含所有已成功的寫入，
  用效能換正確性是合理取捨（列表頁生成頻率等同文章新增頻率，非高頻路徑）。
  `list_articles`（`GET /articles`）本身不變、不受此決策影響。

- **新增 `_publish_article_and_lists_or_rollback`，不修改既有
  `_publish_or_rollback`**：範圍外明訂本票不處理 update/delete 觸發
  （SDLCAIP1-24），而 `_publish_or_rollback` 目前被 `update_article` 共用
  （第 292 行）。若直接在 `_publish_or_rollback` 內加入列表頁重新產生，會讓
  `PUT /articles/{id}` 也連帶重新產生列表頁——這是規格未核准、屬於下一張票
  的行為，故另開一個只給 `create_article` 用的新函式，兩者共用
  `StaticPageGenerationError`/rollback 的錯誤處理慣例，但觸發範圍不重疊。

- **列表分頁失敗與單篇文章頁失敗共用同一個 502 回應與 rollback 路徑**：
  spec AC4 只說「產生或上傳任一分頁靜態 HTML 至 S3 失敗」就回既有 502，
  未區分是單篇文章頁還是列表頁失敗；兩者對訪客而言都是「這次發文沒有完整
  上線」，用同一個 `StaticPageGenerationError` 例外類型、同一個 rollback
  動作（刪除剛寫入的 article item）處理，維持 SDLCAIP1-8 定案的「失敗即整
  筆回滾」語意，不新增第二種部分失敗/部分成功的狀態需要規格決定如何呈現。

- **重用 `StaticPageGenerationError`（傳入 `f"list-page-{page}"` 作為
  `article_id` 參數）而非新增獨立例外類別**：該類別的建構參數/log 訊息格式
  （`"Failed to generate static page for article_id=%s"`）本來就與具體是
  「文章」還是「頁面」無關，只是一個失敗識別字串；新增平行的
  `ListPageGenerationError` 只會讓 `_publish_article_and_lists_or_rollback`
  需要 catch 兩種例外類型，徒增複雜度而無實質差異。

- **列表頁連結一律用絕對根路徑，不用相對路徑**：因為 `page/{n}.html`
  （N≥2）位於子目錄而 `index.html` 在根目錄，兩者對「同一篇文章」或「同一個
  其他分頁」的相對路徑深度不同，若用相對路徑會需要依當前頁碼算不同的
  `../` 前綴，容易出錯；改用 `/articles/{id}.html` 等絕對路徑後，
  `_render_list_page_html` 產生連結時不需要知道自己輸出的頁面最終部署在哪一層。

- **不另外設計「空狀態」HTML 樣板**：AC3 的 Given 是「系統目前沒有任何文章」，
  但 `_generate_and_upload_list_pages` 只會在 `create_article` 成功寫入
  **之後**被呼叫，此時 `scan()` 至少會讀到剛寫入的那一篇，`total` 恆
  ≥ 1——本函式的呼叫時機下不存在「產生出的頁面本身是空的」情境。「由空狀態
  轉為有內容」指的是 S3 上此前從未存在 `index.html`（沒有任何機制產生過），
  新增第一篇文章時才第一次寫入它；不需要另外設計/實作一個「零篇文章」版型。

## 開放設計問題（定稿時必須為空）

無。
