# 設計文件 — SDLCAIP1-35 前台首頁文章列表 UI 套用設計規範

## 對應需求規格

G1 通過版本：作為前台訪客，我希望首頁文章列表視覺符合 `docs/design-system.md`
定義的規範，讓前台網站呈現一致、有質感的編輯感風格。驗收條件（Gherkin，共 5 條）：

1. 色彩與字體改用 token：`_LIST_PAGE_STYLE`（與 `_ARTICLE_PAGE_STYLE` 串接組成
   同一個 `<style>`）新增 `<link>` 引用 `design-tokens.css`；色彩/字體改為
   `var(--color-*)`/`var(--font-family-base)`。
2. 列表項不用邊框/陰影/色塊：`.article-list__item` 移除 `border-bottom`，改以
   `--space-*` 間距 token 做項目分隔。
3. 標題與日期置中：`.article-list__link`／`.article-list__meta` 加上置中。
4. 既有分頁與響應式斷點行為不變：`tests/test_articles_list_pages.py` 既有子
   字串斷言全數通過。
5. 新增真實瀏覽器樣式驗證：比照 `tests/e2e/test_article_detail_page_e2e.py`
   模式，新增 e2e 測試涵蓋 token 色彩/字體、無 border/box-shadow/background、
   標題與日期置中。

範圍外（已定案，不重新討論）：分頁邏輯、資料來源變更；斷點值或版面結構重新
設計；新增文章摘要/內文片段至列表項（`_render_list_page_html` 目前未渲染此
欄位，屬新功能）。

依賴：`docs/design-system.md`（色彩/字體/間距/對齊規則權威來源）；
SDLCAIP1-30（`design-tokens.css` 已存在、已上傳至 S3 bucket 根目錄
`design-tokens.css`，本票只消費，不重新定義 token 數值）。

## 介面/API 契約

無新增/變更對外 HTTP API。本票只改動 `_render_list_page_html`（`src/cms_aipilot/
main.py`）產出的 HTML 字串本身的 `<head>`／`<style>` 內容，不改變 `_list_page_key`
的路徑規則、`_generate_and_upload_list_pages` 的 scan/排序/切頁/上傳邏輯、或
`POST /articles`／`PUT /articles/{id}`／`DELETE /articles/{id}` 既有的觸發與錯誤
回應格式。

`_render_list_page_html` 新增輸出的 `<head>` 內容（片段，緊接在既有
`<style>{_ARTICLE_PAGE_STYLE}{_LIST_PAGE_STYLE}</style>` 之後、`</head>` 之前）：

```html
<link rel="stylesheet" href="/design-tokens.css">
```

## 資料模型

無新增資料模型。不新增/變更 DynamoDB 欄位、資料表或索引；本票只觸碰
`src/cms_aipilot/main.py` 內既有的 `_LIST_PAGE_STYLE` 字串常數與
`_render_list_page_html` 的 head 組字串邏輯，皆為既有原始碼檔案內的既有函式/
常數。

## 關鍵技術決策

- **`<link>` 標籤：絕對路徑 `href="/design-tokens.css"`，插入在
  `_render_list_page_html` 現有 `<style>{_ARTICLE_PAGE_STYLE}{_LIST_PAGE_STYLE}
  </style>` 之後、`</head>` 之前，只加在 `_render_list_page_html` 這一個函式
  裡**：比照 `docs/design-system.md` §9／SDLCAIP1-30「S3 Key 為
  `design-tokens.css`（bucket 根目錄）」的既有決策，根目錄淺層路徑讓
  `index.html`／`page/{n}.html` 都能用同一個絕對路徑引用，不受頁面所在目錄
  深度影響。**與 SDLCAIP1-35 的關係／已知重疊**：截至本文件撰寫時
  `src/cms_aipilot/main.py` 尚無任何 `<link>` 標籤，也沒有共用的
  head-組字串輔助函式——`_generate_and_upload_static_page`（文章詳細頁，
  推測為 SDLCAIP1-34 範圍）、`_render_list_page_html`（本票）、
  `_generate_and_upload_search_page`（search.html）三處目前各自用獨立的
  Python 字串常數組 `<head>`，彼此不共用程式碼路徑。因此本票新增的這一行
  `<link>` 與 SDLCAIP1-34 未來會在文章詳細頁新增的等價 `<link>` **不會有
  程式碼衝突**（不同函式、不同字串常數），但兩者是重複的樣板文字——若後續
  有第三張頁面也要套用，值得考慮抽成共用 head-builder，惟該重構不在本票
  範圍內（範圍外聲明已排除版面結構重新設計），僅在此記錄供 orchestrator
  留意兩票會各自獨立新增同一行、未來可能需要收斂。

- **`_LIST_PAGE_STYLE` 逐項 token 替換內容如下，`_ARTICLE_PAGE_STYLE`（含其
  `body { font-family: ... }` 規則）本次不動**：

  ```css
  .article-list {
    list-style: none;
    padding: 0;
    margin: 0;
    font-family: var(--font-family-base);
  }
  .article-list__item {
    padding: var(--space-3) 0;
    text-align: center;
  }
  .article-list__link {
    font-size: 1.125rem;
    text-decoration: none;
    color: var(--color-text-primary);
  }
  .article-list__meta {
    display: block;
    color: var(--color-text-secondary);
    font-size: var(--font-size-meta);
    line-height: var(--line-height-meta);
    margin-top: var(--space-1);
  }
  .pagination {
    display: flex;
    gap: var(--space-3);
    align-items: center;
    margin-top: var(--space-5);
  }
  ```

  理由拆解：
  - `font-family: var(--font-family-base)` 加在 `.article-list`（新宣告，
    scoped 到列表容器），**不**改動 `_ARTICLE_PAGE_STYLE` 的 `body { font-family:
    system-ui, ... }`——後者與文章詳細頁共用（同一個 `<style>` 區塊被
    `_generate_and_upload_static_page` 與 `_render_list_page_html` 各自
    串接），Given 子句明確把本票範圍限定在 `_LIST_PAGE_STYLE`，改 `body`
    規則會連帶影響文章詳細頁的字體，超出本票範圍也可能與 SDLCAIP1-34 對
    同一段落的改動互相覆蓋踩踏。
  - `.article-list__item` 的 `border-bottom: 1px solid #eee` 整條移除
    （AC2 明文要求不用 border/box-shadow/background-color）；分隔改用既有
    `padding: var(--space-3) 0`（值恰為原本的 `12px`，數值不變、只是換成
    token 寫法）——相鄰兩個 `<li>` 之間因此有 `12px + 12px = 24px` 的視覺
    留白做分隔，不需要額外的 `margin`，維持最小改動。
  - `.article-list__meta` 的 `color: #666` 改 `var(--color-text-secondary)`
    （值為 `#111111`，design-system.md §1 明訂「不做灰階分層，層次靠字級
    大小」，故此處色彩實際上會變深，屬規範要求的預期行為，非誤植）；
    `font-size: 0.875rem` 改用 `var(--font-size-meta)`（數值同為
    `0.875rem`，一併補上 `var(--line-height-meta)` 讓 meta 文字的行高也
    納入 token 體系，AC1 字面只要求色彩/字體變數化，但字級剛好對應既有
    定義的 Meta 階層，一併套用比留一個孤立的字面量數值更符合本規範精神）。
  - `.article-list__link` 的 `font-size: 1.125rem` **維持字面量、不套用
    任何字級 token**：`docs/design-system.md` §3 字級階層表（Display/H1/
    H2/Body/Meta/Nav）沒有對應 `18px` 的既定層級，AC1 的驗收字面只要求
    「色彩/字體改為 `var(--color-*)`/`var(--font-family-base)`」，未要求
    字級改動；若擅自把列表標題升格套用 H2（`1.5rem`）或降格套用 Body
    （`1rem`）都是本票 spec 沒有交代的版面設計決定，且範圍外聲明已排除
    「版面結構重新設計」，故保留原字面量，只補上 `color: var(--color-
    text-primary)`。
  - `.pagination` 的 `gap: 12px`／`margin-top: 24px` 改為
    `var(--space-3)`／`var(--space-5)`（數值不變，token 化；`--space-5`
    為 24px，`--space-6`〔32px〕會改變版面，orchestrator 審查時已修正此
    處原稿的錯誤映射）。

- **標題與日期置中：`text-align: center` 加在 `.article-list__item`
  這一層，不分別加在 `.article-list__link`／`.article-list__meta`**：兩者
  都是 `.article-list__item` 底下的行內／區塊層級子元素，在父層設
  `text-align: center` 即可讓兩者的文字內容一併置中，符合 CSS 慣例
  （`text-align` 會被子孫繼承），比在兩個子選擇器各寫一次更精簡，且未來
  若在 `<li>` 內新增其他文字子元素（例如摘要，雖然本票範圍外）也會自動
  沿用同一置中基準，不需要逐一補規則。

- **e2e 測試新檔 `tests/e2e/test_articles_list_page_styling_e2e.py`
  （與既有 `tests/e2e/test_articles_list_styling_e2e.py`（SDLCAIP1-32，
  後台管理介面文章表格）刻意區分檔名——後者測的是 `frontend/` 的
  React 後台頁面，前者測的是本票的前台公開靜態首頁列表頁，兩者是完全不同
  的頁面/技術棧，`_list_page` vs `_list` 的檔名差異刻意避免混淆）**：

  - 直接呼叫 `_render_list_page_html(page_items, page, total_pages)`
    取得 HTML 字串，**不**透過 `_generate_and_upload_list_pages(table)`
    + mock DynamoDB `table.scan()` 的路徑取得。理由：既有
    `test_article_detail_page_e2e.py` 之所以透過 mock S3 呼叫
    `_generate_and_upload_static_page(article)` 取得 Body，是因為該函式
    本身就是「組字串 + 上傳」一體的唯一入口，沒有更底層的純函式可用；而
    列表頁的組字串邏輯已經是獨立的純函式 `_render_list_page_html`（無 S3/
    DynamoDB 依賴），直接呼叫可取得與上傳版本位元組相同的字串，且不需要
    額外 mock `table.scan()`，是更直接、更不脆弱的等價作法。

  - **`design-tokens.css` 內容以 `page.route()` 攔截並回填真實檔案內容
    （讀取 `cms_aipilot.main._DESIGN_TOKENS_PATH`，與
    `_generate_and_upload_design_tokens()` 上傳的內容同一份檔案來源），
    先 `page.route("https://sdlcaip1-35.e2e.test/**", handler)` 攔截，
    再 `page.goto("https://sdlcaip1-35.e2e.test/index.html")` 導覽
    （`handler` 依請求路徑分流：`/index.html` 回填 `_render_list_page_html`
    產出的 HTML body；`/design-tokens.css` 回填讀出的 CSS 內容；其餘一律
    `route.abort()`），不使用 `page.set_content()`**：這是與
    `test_article_detail_page_e2e.py` 既有模式的唯一刻意分歧，原因是
    AC1 要求驗證「computed CSS 已套用 token 色彩/字體」，而本票新增了一個
    既有文章詳細頁測試沒有的外部資源依賴——`<link rel="stylesheet"
    href="/design-tokens.css">`。`page.set_content()` 不會改變 page 目前
    的 URL（新分頁預設 `about:blank`），瀏覽器對 `about:blank` 沒有可用的
    origin 可解析 `/design-tokens.css` 這類路徑絕對 URL，該次資源請求無法
    可靠地被觸發或攔截，樣式將不會實際載入，導致 computed style 斷言恆為
    瀏覽器預設值而非 token 值（測試會呈現偽陽性或直接失敗，且失敗原因與
    程式碼實際行為無關）。改用「攔截 + `goto` 到一個固定的假 origin」讓
    `<link>` 的相對／絕對路徑有真實 origin 可解析，请求會確實發出並被
    `page.route()` 攔截回填，同時全程不接觸真實網路（等同於原模式的
    「mock S3」精神——原模式 mock 的是「取得 Body 的手段」，此處 mock 的
    是「Body 之外，瀏覽器渲染該 Body 時會額外發出的資源請求」，兩者都不
    接觸真正的 AWS/網路）。讀取真實檔案（而非在測試裡手抄一份色碼字面值）
    確保測試驗證的是「這份會被實際上傳到 S3 的檔案」，數值改動時測試會
    自動反映，不會出現測試裡的複製值與正式檔案悄悄失去同步而不自知。

  - 斷言涵蓋：`.article-list__link` 的 `color` 為 `rgb(17, 17, 17)`
    （`--color-text-primary`）、`.article-list` 的 `fontFamily` 含
    `"PingFang TC"`（`--font-family-base`）；`.article-list__item` 的
    `borderBottomWidth` 為 `"0px"`、`boxShadow` 為 `"none"`、
    `backgroundColor` 為 `"rgba(0, 0, 0, 0)"`；`.article-list__link`
    與 `.article-list__meta` 的 `textAlign` 皆為 `"center"`。

## 開放設計問題（定稿時必須為空）

無。
