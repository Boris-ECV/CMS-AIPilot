# 設計文件 — SDLCAIP1-36 前台搜尋頁 UI 套用設計規範

## 對應需求規格

G1 通過版本：作為前台訪客，我希望搜尋頁（`search.html`）視覺符合
`docs/design-system.md` 定義的規範，讓前台網站呈現一致、有質感的編輯感風格。
驗收條件（Gherkin，共 7 條）：

1. `_generate_and_upload_search_page` 產生的 `<head>` 內含
   `<link rel="stylesheet" href="/design-tokens.css">`（絕對路徑，比照既有
   `href="/search.html"`／SDLCAIP1-34/35 慣例；沿用 SDLCAIP1-30 已上傳至
   bucket 根目錄的檔案，本票只消費不重新定義）。
2. `.search-form__input` 間距改用 `var(--space-*)`，代入後與套用前的
   px 數值逐一相同。
3. `.article-list__item`／`.article-list__link`（沿用 `_LIST_PAGE_STYLE`
   的既有 class 命名，但目前未被 wire 進 `search.html` 的 `<style>` 標籤）
   需在搜尋頁自身的樣式中定義——實作方式（新增獨立常數 vs. 併入既有
   `_SEARCH_PAGE_STYLE`）明確留給本 Designing 階段決定；且明確**不得**依賴
   sibling ticket SDLCAIP1-35 對 `_LIST_PAGE_STYLE` 的改動。
4. 搜尋結果只渲染標題，不含摘要／內文片段（先前草稿的錯誤假設已於 G1
   訂正，本次設計不得重新引入）。
5. 既有 vanilla JS 子字串比對邏輯與 `#search-empty` 無結果訊息不動；
   `--color-error` **不**套用在該無結果訊息上。
6. 既有測試全數通過，並新增 e2e 測試檔（沿用 `page.route` + `page.goto`
   攔截模式，非 `page.set_content`——理由與 SDLCAIP1-34/35 相同：`<link>`
   需要真實 origin 才能解析並被攔截）。

範圍外（已定案，不重新討論）：搜尋／索引邏輯變更；斷點或版面結構重新設計；
渲染摘要／內文片段；改動共用的 `_LIST_PAGE_STYLE`（SDLCAIP1-35 的範圍）或
`_ARTICLE_PAGE_STYLE` 本身；本票新增的 `.article-list__item`／
`.article-list__link` 樣式僅限 `search.html` 生效；無結果訊息不套用
`--color-error`。

依賴：SDLCAIP1-30（Done，提供 `design-tokens.css`，本票只消費）。明確
**不**依賴 SDLCAIP1-35。

## 介面/API 契約

無新增/變更對外 HTTP API。本票只改變 `src/cms_aipilot/main.py` 內
`_generate_and_upload_search_page` 產生的靜態 HTML 字串內容（含新增/調整的
`_SEARCH_PAGE_STYLE` 常數），S3 key（`SEARCH_PAGE_KEY = "search.html"`）、
`ContentType`、既有的 `StaticPageGenerationError("search-page", ...)` 錯誤
處理路徑與 502 rollback 完全不動；`_SEARCH_PAGE_SCRIPT`（比對邏輯、
`#search-empty` 顯示/隱藏）與 `SEARCH_INDEX_KEY`/`_build_search_index_entry`
（搜尋索引產生邏輯）完全不動。

`<head>` 新舊對照（AC1）：

```html
<!-- 修改前 -->
<html lang="zh-Hant"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>搜尋文章</title>
<style>{_ARTICLE_PAGE_STYLE}{_SEARCH_PAGE_STYLE}</style>
</head>

<!-- 修改後 -->
<html lang="zh-Hant"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>搜尋文章</title>
<style>{_ARTICLE_PAGE_STYLE}{_SEARCH_PAGE_STYLE}</style>
<link rel="stylesheet" href="/design-tokens.css">
</head>
```

`<link>` 置於既有 `<style>` 之後、`</head>` 之前——比照 `_render_list_page_html`
（SDLCAIP1-35，程式碼現況第 340 行）目前的既有放法，而非
`_generate_and_upload_static_page`（SDLCAIP1-34）把 `<link>` 放在
`<style>` 之前的放法。目前 codebase 這兩種放法並存（`main.py` 兩處各自獨立
組字串，無共用 head-builder，SDLCAIP1-35 設計文件已記錄此點供未來收斂
參考）；`design-tokens.css` 只定義 `:root` 自訂屬性、不含任何選擇器規則，
兩種放法對最終 computed style 完全等價，故本票挑選與程式碼現況中「較晚合併
的搜尋頁鄰居」一致的放法（`_render_list_page_html`），純粹是撰碼慣例選擇，
不影響行為。`<body>` 內既有 `id="search-form"`／`id="search-input"`／
`id="search-results"`／`id="search-empty"`／`<script>` 內容與
`<a href="/search.html">搜尋文章</a>`（此連結不存在於 search.html 自身）
等既有結構完全不動，只改變 CSS 規則本身的值與新增規則。

`_SEARCH_PAGE_STYLE` 新舊值逐項對照：

| 選擇器 / 屬性 | 修改前 | 修改後 |
|---|---|---|
| `.search-form__input { padding }` | `8px 12px` | `var(--space-2) var(--space-3)`（8px/12px，數值不變） |
| `.search-form__input { margin-bottom }` | `16px` | `var(--space-4)`（16px，數值不變） |
| `.search-form__input { font-size }` | `1rem` | **不變**（AC2 字面只要求「間距」token 化，未提及字級） |
| `.search-form__input { width, box-sizing }` | `100%` / `border-box` | **不變**（與間距/色彩/字體無關） |
| `.article-list__item { padding }`（新增） | （不存在，未 wire） | `var(--space-3) 0`（AC3，新規則） |
| `.article-list__item { text-align }`（新增） | （不存在） | `center`（design-system.md §6：標題置中） |
| `.article-list__link { color }`（新增） | （不存在，繼承瀏覽器預設藍底線） | `var(--color-text-primary)`（AC3） |
| `.article-list__link { font-size }`（新增） | （不存在） | `1.125rem`（字面量，見「關鍵技術決策」） |
| `.article-list__link { text-decoration }`（新增） | （不存在） | `none`（見「關鍵技術決策」） |

`_ARTICLE_PAGE_STYLE`（`body { font-family: system-ui, ... }` 等，search.html
與列表頁共用的既有常數）本票完全不動——AC1/AC2/AC3 字面範圍僅限
`_SEARCH_PAGE_STYLE` 與新增的 `<link>`，理由與「關鍵技術決策」一致。

## 資料模型

無新增資料模型。不新增/變更 DynamoDB 欄位、資料表或索引；`SEARCH_INDEX_KEY`
（`search/index.json`）的內容結構、`_build_search_index_entry` 完全不動——
本票只觸碰 `src/cms_aipilot/main.py` 內 `_SEARCH_PAGE_STYLE` 字串常數與
`_generate_and_upload_search_page` 的 head 組字串邏輯，以及新增的 e2e 測試檔。

## 關鍵技術決策

- **AC3 實作方式：直接在既有 `_SEARCH_PAGE_STYLE` 常數內新增
  `.article-list__item`／`.article-list__link` 規則，不另外拆出獨立常數**：
  這與 SDLCAIP1-34 為 `_ARTICLE_DETAIL_PAGE_STYLE` 拆出獨立常數的判斷表面
  相似（都是「不要動共用常數」），但情境不同——SDLCAIP1-34 之所以拆新常數，
  是因為 `_ARTICLE_PAGE_STYLE` 本身被三處頁面共用，直接改會外溢到未經
  spec 要求/未經測試覆蓋的其他頁面。而 `_SEARCH_PAGE_STYLE`
  （`src/cms_aipilot/main.py` 現況第 425 行起）**只**被
  `_generate_and_upload_search_page` 一處使用，本來就是搜尋頁專屬常數，不
  是共用常數；在其中新增規則不會外溢到列表頁或文章詳細頁。因此不需要像
  SDLCAIP1-34 那樣為了隔離而拆出新常數——多拆一個常數在此處只是無意義的
  間接層。同時，因為完全不觸碰 `_LIST_PAGE_STYLE`（`_render_list_page_html`
  專用，SDLCAIP1-35 的範圍），AC3「不得依賴 SDLCAIP1-35 對
  `_LIST_PAGE_STYLE` 的改動」的要求自動滿足——兩者是不同 Python 常數，
  程式碼層級零耦合。

- **`.article-list__item`／`.article-list__link` 的規則值（`padding:
  var(--space-3) 0`、`text-align: center`、`color: var(--color-text-primary)`、
  `font-size: 1.125rem`、`text-decoration: none`）與 `_LIST_PAGE_STYLE`
  post-SDLCAIP1-35 的同名選擇器數值相同，但為獨立依據
  `docs/design-system.md` 決定，非複製依賴**：`--space-3`（12px）作為項目
  間距、`center` 對齊符合 §6「標題置中」、`--color-text-primary` 符合 §1
  色彩規則、不加 `border`/`box-shadow`/`background-color` 符合 §7「卡片/
  列表項…不用邊框、陰影、背景色塊」。`font-size: 1.125rem` 維持字面量、
  不套用任何字級 token：`design-system.md` §3 字級階層表無對應 18px 的
  既定層級，AC3 未要求字級 token 化，理由與 SDLCAIP1-35 設計文件對同一
  class 的既有判斷一致（各自獨立推導、非抄襲程式碼，但因為權威來源
  design-system.md 相同，結果數值自然一致，屬預期收斂而非巧合風險）。
  `text-decoration: none` 沿用瀏覽器對 `<a>` 預設底線之外的既有慣例（列表
  頁既有同名 class 亦是 `none`），維持與已合併頁面視覺一致。

- **`_ARTICLE_PAGE_STYLE`（`body { font-family: system-ui, ... }`、
  `padding` 等）本票不動，搜尋頁整體字體/間距不做全面 token 化**：
  AC1/AC2/AC3 字面範圍分別是「新增 `<link>`」「`.search-form__input` 間距」
  「`.article-list__item`／`__link` 新樣式」，並未像 SDLCAIP1-34/35 的
  AC1/AC2 那樣明文要求「色彩/字體改為 token」適用於整頁其餘既有元素；不
  比照 SDLCAIP1-34/35 全面套用色彩/字體 token 到 `_ARTICLE_PAGE_STYLE`，
  避免超出本票 spec 字面範圍、也避免此頁字體/色彩改動外溢到同樣共用
  `_ARTICLE_PAGE_STYLE` 的列表頁（範圍紀律，理由同 SDLCAIP1-35 設計文件
  對同一常數的既有判斷）。

- **`--color-error` 明確不套用在 `#search-empty`**：AC5 字面明文排除，
  直接依 spec 不新增任何色彩宣告到 `.search-empty` 選擇器（目前
  `_SEARCH_PAGE_STYLE`／`_ARTICLE_PAGE_STYLE` 皆無 `.search-empty` 規則，
  維持現狀不新增）。

- **e2e 測試新檔 `tests/e2e/test_search_page_design_tokens_e2e.py`
  （與既有 `tests/e2e/test_search_page_e2e.py`（SDLCAIP1-28/26/27 搜尋
  行為）刻意分檔，不修改既有檔案）**：沿用 SDLCAIP1-34/35 已驗證的
  `page.route` + `page.goto`（假 https origin）攔截模式，理由相同——
  `page.set_content` 的文件 origin 為 `about:blank`，`<link
  rel="stylesheet">` 不會實際發出可攔截的請求，`getComputedStyle` 讀到的
  token 值會恆為未定義。具體作法：
  1. 沿用 `test_search_page_e2e.py` 既有 `SEARCH_PAGE_URL =
     "https://e2e-search-page.example/search.html"` 常數與
     `_generated_html(monkeypatch)` 輔助函式（不重複定義，直接
     `from tests.e2e.test_search_page_e2e import ...` 或複製同等程式碼——
     交由 developer 依專案既有測試檔案間的 import 慣例決定，不在此限定
     模組層級呼叫方式，避免對測試檔案結構做本票 spec 未要求的架構決定）。
  2. 新增 `page.route("**/design-tokens.css", handler)`，`handler` 讀取
     `cms_aipilot.main._DESIGN_TOKENS_PATH` 檔案內容並
     `route.fulfill(content_type="text/css", body=...)`（讀真實檔案，非
     手抄字面值，理由同 SDLCAIP1-34/35：確保 token 數值變動時測試自動
     反映，不會與正式檔案悄悄失去同步）；`page.route(SEARCH_PAGE_URL,
     ...)` 沿用既有 `handle_page` 邏輯回填 `_generated_html` 產出的
     HTML；`page.goto(SEARCH_PAGE_URL)` 取代 `page.set_content`。
  3. 為了讓 `.article-list__item`／`.article-list__link` 有內容可斷言，
     測試需先透過 `page.fill("#search-input", ...)` 觸發一次比對出至少
     一筆結果（沿用既有 `SEARCH_INDEX`／`_load_with_index` 的資料
     fixture），而非只檢查空頁面上的靜態樣式。
  4. 斷言涵蓋：`.search-form__input` 的 `getComputedStyle(...).padding`／
     `marginBottom` 與套用前 px 值相同（AC2，驗證「數值不變、只是換 token
     寫法」而非只驗證選擇器存在）；填入關鍵字後 `.article-list__item` 的
     `borderBottomWidth === "0px"`、`boxShadow === "none"`、
     `backgroundColor === "rgba(0, 0, 0, 0)"`（AC3 對齊 §7）；
     `.article-list__link` 的 `color === "rgb(17, 17, 17)"`
     （`--color-text-primary`）與 `textAlign === "center"`（AC3）；
     `#search-empty` 顯示時 `getComputedStyle(...).color` **不是**
     `--color-error` 對應值（AC5，斷言其維持瀏覽器預設繼承色，而非任何
     紅色系數值——`design-tokens.css` 現況未定義 `--color-error` 這個
     自訂屬性，故只需確認顏色不是常見錯誤紅即可，不需要比對不存在的
     token）。

## 開放設計問題（定稿時必須為空）

無。
