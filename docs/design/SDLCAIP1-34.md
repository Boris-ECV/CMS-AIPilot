# 設計文件 — SDLCAIP1-34 前台文章詳細頁 UI 套用設計規範

## 對應需求規格

G1 通過版本：作為前台訪客，我希望文章詳細頁視覺符合 `docs/design-system.md` 定義的
規範，讓前台網站呈現一致、有質感的編輯感風格。驗收條件（Gherkin，共 5 條）：

1. `_generate_and_upload_static_page` 產生的 `<head>` 內含
   `<link rel="stylesheet" href="/design-tokens.css">`（絕對路徑，比照既有
   `href="/search.html"` 慣例；沿用 SDLCAIP1-30 已上傳至 bucket 根目錄的檔案）。
2. `_ARTICLE_PAGE_STYLE`（目前獨立寫死的內嵌樣式）色彩改為
   `var(--color-text-primary)`（標題/內文）、`var(--color-text-secondary)`
   （meta，取代寫死的 `#666`）；字體改為 `var(--font-family-base)`，不再寫死
   色碼。
3. `.article__title` 與 `.article__meta` 置中（`text-align: center`），
   `.article__content` 維持靠左（§6 對齊規則）。
4. 既有響應式斷點行為不變（768px/1025px、單欄無橫向捲動、平板 padding
   24px、桌機 max-width 800px 置中）；本 Story 只換色彩/字體/間距數值，不改
   斷點邏輯。
5. `tests/e2e/test_article_detail_page_e2e.py` 改用與
   `test_search_page_e2e.py` 相同的 `page.route`（假 https URL）+ `page.goto`
   攔截模式載入頁面與 `design-tokens.css`，既有版面斷言與新增的 token 色彩
   斷言全數通過。

範圍外（已定案，不重新討論）：文章內容渲染邏輯變更；斷點值或版面結構重新
設計；`design-tokens.css` 本身內容變更（已由 SDLCAIP1-30 定案）。

依賴：SDLCAIP1-30（`design-tokens.css` 已存在並已上傳至 S3 bucket 根目錄，
提供 `--color-*`/`--font-family-base`/`--space-*` 變數，本票只消費，不重新
定義）。

## 介面/API 契約

無新增/變更對外 HTTP API。本票只改變 `src/cms_aipilot/main.py` 內
`_generate_and_upload_static_page`（文章詳細頁）產生的靜態 HTML 字串內容，
S3 key（`articles/{article.id}.html`）、`ContentType`、DynamoDB 寫入、
`_publish_or_rollback`/`_publish_article_and_lists_or_rollback` 的呼叫順序與
既有錯誤處理路徑（`StaticPageGenerationError`、502 rollback）完全不動。

`<head>` 新舊對照（AC1）：

```html
<!-- 修改前 -->
<html lang="zh-Hant"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>{_ARTICLE_PAGE_STYLE}</style>
</head>

<!-- 修改後 -->
<html lang="zh-Hant"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link rel="stylesheet" href="/design-tokens.css">
<style>{_ARTICLE_DETAIL_PAGE_STYLE}</style>
</head>
```

`<link>` 置於 `<title>` 之後、`<style>` 之前，不自我封閉（比照本檔既有
`<meta ...>` 標籤風格，不用 `<link ... />`）；`href="/design-tokens.css"`
為絕對路徑，與既有 `href="/search.html"` 慣例一致（bucket 根目錄相對於任何
頁面所在深度都可用同一路徑引用，理由沿用 SDLCAIP1-30 設計文件「S3 Key 為
`design-tokens.css`（bucket 根目錄）」決策）。`<body>` 內既有
`<a href="/search.html">搜尋文章</a>`、`class="article"`/`article__title`/
`article__meta`/`article__content` 等既有 class 名稱與屬性完全不動，只改變
CSS 規則本身的值。

`_ARTICLE_DETAIL_PAGE_STYLE`（新常數，見「關鍵技術決策」為何不直接改
`_ARTICLE_PAGE_STYLE`）新舊值逐項對照：

| 選擇器 / 屬性 | 修改前 | 修改後 |
|---|---|---|
| `body { font-family }` | `system-ui, -apple-system, "Segoe UI", sans-serif` | `var(--font-family-base)` |
| `body { padding }`（預設） | `16px` | `var(--space-4)`（16px，數值不變） |
| `.article__title { color }` | （未設定，繼承瀏覽器預設黑） | `var(--color-text-primary)` |
| `.article__title { margin }` | `0 0 8px` | `0 0 var(--space-2)`（8px，數值不變） |
| `.article__title { text-align }` | （未設定） | `center`（新增，AC3） |
| `.article__meta { color }` | `#666` | `var(--color-text-secondary)` |
| `.article__meta { margin-bottom }` | `16px` | `var(--space-4)`（16px，數值不變） |
| `.article__meta { text-align }` | （未設定） | `center`（新增，AC3） |
| `.article__content { color }` | （未設定） | `var(--color-text-primary)` |
| `.article__content { text-align }` | （未設定，預設 `left`） | 不新增宣告——瀏覽器預設值已是 `left`，AC3「維持靠左」不要求顯式宣告 |
| `@media 768–1024px` `body { padding }` | `24px` | `var(--space-5)`（24px，數值不變） |
| `@media ≥1025px` `body { padding }` | `32px` | `var(--space-6)`（32px，數值不變） |
| `.article__title { font-size }`（三個斷點：1.5rem/1.75rem/2rem） | 寫死 rem 值 | **不變**，見下方關鍵技術決策（AC2 字面只要求 `font-family`，未要求 `font-size` 改用 token） |
| `body { line-height: 1.6 }` | 寫死 | **不變**（AC2 未提及 line-height token） |
| `* { box-sizing }`、`.article { max-width }`、`img, pre, table { max-width }`、`.article__content { white-space }` | 寫死 | **不變**（與色彩/字體/間距無關） |

## 資料模型

無新增資料模型。不新增/變更 DynamoDB 欄位、資料表或索引；本票只觸碰
`src/cms_aipilot/main.py` 內的 Python 字串常數與 `tests/e2e/
test_article_detail_page_e2e.py`。

## 關鍵技術決策

- **新增獨立常數 `_ARTICLE_DETAIL_PAGE_STYLE`（`_generate_and_upload_static_page`
  專用），不直接修改共用的 `_ARTICLE_PAGE_STYLE`**：`_ARTICLE_PAGE_STYLE`
  目前被三處共用——`_generate_and_upload_static_page`（文章詳細頁，本票範圍）、
  `_render_list_page_html`（列表頁，`_ARTICLE_PAGE_STYLE + _LIST_PAGE_STYLE`）、
  `_generate_and_upload_search_page`（搜尋頁，`_ARTICLE_PAGE_STYLE +
  _SEARCH_PAGE_STYLE`）。AC1 的 Given 子句明確把本票範圍鎖定在
  `_generate_and_upload_static_page` 產生的 `<head>`；若直接改共用常數為
  `var(--color-*)`/`var(--font-family-base)`，列表頁與搜尋頁會一併吃到這些
  改動，但這兩個頁面的 `<head>` 並未（也不在本票範圍內）新增
  `design-tokens.css` 的 `<link>`，屆時這些 `var()` 會因變數未定義而失效
  （屬性宣告整條失效，回退為瀏覽器預設值），造成列表頁/搜尋頁的視覺在未經
  spec 要求、未經測試覆蓋的情況下悄悄劣化（例如 meta 文字從 `#666` 退化成
  瀏覽器預設黑，而非設計系統定義的任何一個 token 值）。依「範圍紀律」不擴大
  本票範圍去同時處理列表頁/搜尋頁（那是未來 Story 的工作），因此拆出獨立
  常數，把改動嚴格限制在文章詳細頁；`_ARTICLE_PAGE_STYLE` 本身與其在列表頁/
  搜尋頁的既有用法完全不動。

- **`.article__title`/`.article__meta` 的 `font-size` 響應式數值（1.5rem/
  1.75rem/2rem）維持寫死，不改用 `--font-size-h1` 等字級 token**：AC2 字面
  只列出「色彩改為 token」與「字體改為 `var(--font-family-base)`」兩項，未
  提及字級（`font-size`）token 化；`design-tokens.css` 的 `--font-size-h1`
  是單一固定值（`2rem`），不具備本頁現有的三段式響應式字級（768px 前
  1.5rem、768–1024px 之間 1.75rem、≥1025px 才是 2rem），若強行套用固定
  token 會改變 AC4 明確要求「與套用前一致」的既有斷點版面行為。維持寫死是
  在不逾越 AC2 字面範圍、且不違反 AC4「不改斷點邏輯與版面行為」前提下的
  唯一選擇；`line-height: 1.6`、`box-sizing`、`max-width` 等其餘與色彩/
  字體家族/間距無關的既有規則，同理不動。

- **間距數值（`padding`/`margin`）改用 `var(--space-*)`，但代入後的
  計算值與修改前逐一相同（16px→`--space-4`、8px→`--space-2`、24px→
  `--space-5`、32px→`--space-6`）**：Scenario 4 的 Given/Then 明確把
  「間距數值」與「色彩/字體」並列為本 Story 換成 token 的對象，同時要求
  「與套用前一致」的版面行為；`docs/design-system.md` §4 的間距 scale 恰好
  與本頁既有寫死值逐一吻合，因此可以直接一對一替換為對應 token 而不產生任何
  可觀察的版面差異，同時滿足 AC4 的字面雙重要求（改用 token、行為不變）。

- **e2e 測試改用假 https URL + `page.route`/`page.goto` 攔截模式，比照
  `test_search_page_e2e.py` 的 `SEARCH_PAGE_URL`/`_load_with_index` 寫法，
  新增第二個 `page.route` 攔截 `**/design-tokens.css`**：AC5 明確指定沿用
  `test_search_page_e2e.py` 既有模式，理由與該檔案既有註解相同——
  `page.set_content` 產生的文件 origin 為 `about:blank`，外部
  `<link rel="stylesheet">` 不會實際發出請求、樣式表不會生效，
  `getComputedStyle` 讀到的 CSS 自訂屬性值會是未定義，無法驗證 AC2 的 token
  斷言。具體改法：
  1. 新增 `ARTICLE_PAGE_URL = "https://e2e-article-page.example/articles/a1.html"`
     常數（比照 `SEARCH_PAGE_URL`）。
  2. 新增 `DESIGN_TOKENS_URL = "https://e2e-article-page.example/design-tokens.css"`；
     測試 fixture 內直接讀取 `src/cms_aipilot/static/design-tokens.css`
     檔案內容（可 `import` `main._DESIGN_TOKENS_PATH` 常數重用路徑，不重新
     寫死路徑字串），作為 `route.fulfill(content_type="text/css", body=...)`
     的回應內容——不呼叫 `_generate_and_upload_design_tokens()`（該函式的
     副作用是 S3 上傳，測試只需要檔案內容本身）。
  3. 既有 `_generated_html(monkeypatch, article)` 輔助函式維持不動（產生
     `_generate_and_upload_static_page` 的輸出字串）；新增輔助函式
     `_load_article_page(page, monkeypatch, article)`：呼叫
     `_generated_html`、對 `ARTICLE_PAGE_URL` 與 `**/design-tokens.css`
     各掛一個 `page.route(...).fulfill(...)`，最後 `page.goto(ARTICLE_PAGE_URL)`
     取代原本的 `page.set_content(html)`。所有既有測試（
     `TestArticleDetailPageFullContentRendersInBrowser`、
     `TestArticleDetailPageMobileLayout`、`TestArticleDetailPageTabletLayout`、
     `TestArticleDetailPageDesktopLayout`、
     `TestArticleDetailPageEscapingRendersAsText`）一律改呼叫這個新輔助函式
     取代原本的 `html = _generated_html(...); page.set_content(html)` 兩行，
     其餘既有斷言（文字可見性、`_no_horizontal_scroll`、`.article`
     `bounding_box`、escaping 相關斷言）不改變。
  4. 新增一個測試類別（例如 `TestArticleDetailPageDesignTokensApplied`），
     斷言：`getComputedStyle(article__meta).color` 為 `rgb(17, 17, 17)`
     （`--color-text-secondary: #111111`，區別於修改前的 `#666` =
     `rgb(102, 102, 102)`，也區別於「token 未載入時」瀏覽器預設繼承黑
     `rgb(0, 0, 0)`，三者互不相同，可明確驗證 token 確實生效而非巧合或
     retreat 到瀏覽器預設值）；`getComputedStyle(body).fontFamily` 包含
     `"PingFang TC"`（`--font-family-base` 字體堆疊中修改前字串
     `system-ui`/`Segoe UI` 不含的獨有子字串，可明確區分 token 是否生效）；
     `getComputedStyle(article__title).textAlign` 與
     `getComputedStyle(article__meta).textAlign` 皆為 `"center"`；
     `getComputedStyle(article__content).textAlign` 為 `"left"`（AC3）。

## 開放設計問題（定稿時必須為空）

無。
