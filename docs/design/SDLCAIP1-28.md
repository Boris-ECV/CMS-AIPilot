# 設計文件 — SDLCAIP1-28 前台搜尋頁面（search.html）

## 對應需求規格

G1 通過版本：作為網站前台訪客，在一個獨立的搜尋頁面輸入關鍵字並看到符合標題或
全文的文章清單，以便快速找到感興趣的文章內容。驗收條件（Gherkin，共 8 條）：

1. 獨立搜尋頁存在且可從其他靜態頁面連結進入。
2. 輸入關鍵字後顯示標題相符的文章。
3. 輸入關鍵字後顯示內文相符的文章（全文搜尋）。
4. 關鍵字比對不分大小寫、為子字串比對。
5. 查無符合結果時顯示明確提示。
6. 結果不分頁，全部顯示。
7. 搜尋框為空時不顯示任何結果或錯誤。
8. 比對邏輯純前端執行，不呼叫後端 API（唯一資料來源是 `search/index.json`）。

範圍外：搜尋結果分頁/無限捲動、任何第三方 JS 函式庫或建置管線（純 vanilla
JS）、搜尋結果排序邏輯、內文摘要/highlight、分類/標籤篩選與進階搜尋語法、後台
管理 UI 搜尋、響應式版面細節設計（沿用既有共用樣式）。

架構決策依據：HUMAN-INPUT SDLCAIP1-25 已核准——獨立搜尋頁（非內嵌）、純
vanilla JS 比對、不分頁全部顯示、索引含全文 `content`、S3 路徑
`search/index.json`。

依賴：SDLCAIP1-26（新增文章觸發索引首次產生）、SDLCAIP1-27（更新/刪除觸發索引
同步重建）——兩者皆尚未實作/合併。本票依賴的 `search/index.json` schema 在
SDLCAIP1-26/27 的定稿需求規格中已定案（欄位：`id`/`title`/`content`/
`published_at`），本設計文件在「資料模型」章節將其列為**引用契約**，非新定案；
若 SDLCAIP1-26/27 最終設計文件對此 schema 有任何調整，須回頭核對本票是否受影響。
另依賴 SDLCAIP1-20（`_ARTICLE_PAGE_STYLE` 共用樣式）、SDLCAIP1-23
（`_render_list_page_html`/`_list_page_key` 等既有靜態頁渲染風格）。

## 介面/API 契約

無新增/變更對外 HTTP API。本票純粹是新增一個靜態 HTML 頁面（`search.html`）與
它內嵌的前端 JS，執行期唯一的網路請求是瀏覽器端 `fetch("/search/index.json")`
（GET 靜態檔案，非後端 API 呼叫，對應 AC8）。

### `search/index.json` 資料契約（引用 SDLCAIP1-26/27 定案，非本票新定案）

```json
[
  {
    "id": "string",
    "title": "string",
    "content": "string",
    "published_at": "ISO-8601 string"
  }
]
```

- 陣列，元素數與文章數一致；無文章時為 `[]`（SDLCAIP1-27 AC3 已定案）。
- 本票的前端 JS 只讀取 `id`、`title`、`content` 三個欄位（比對用
  `title`+`content`，連結用 `id`）；`published_at` 存在於 index 但本票不使用
  （不涉及排序，範圍外已明訂）。
- 若 fetch 失敗（404/網路錯誤/JSON parse 失敗），視為「目前沒有可搜尋的索引」
  ——不屬於任一條 Gherkin AC 明訂的情境（8 條 AC 皆未提及 index.json 本身
  缺失或格式錯誤時的行為），故本設計不假設任何特定錯誤訊息文案，開發者可用
  console 記錄並讓後續輸入關鍵字時視為「查無結果」（沿用 AC5 的既有 UI 元件、
  不新增一種「索引載入失敗」專屬提示），此為實作細節、非產品決策，不列入開放
  設計問題。

### `search.html` 輸出契約

```html
<!DOCTYPE html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>搜尋文章</title>
  <style>{_ARTICLE_PAGE_STYLE}{_SEARCH_PAGE_STYLE}</style>
</head>
<body>
  <form class="search-form" id="search-form" onsubmit="return false;">
    <input type="text" id="search-input" class="search-form__input"
           placeholder="輸入關鍵字搜尋文章" autocomplete="off">
  </form>
  <ul class="article-list" id="search-results"></ul>
  <p class="search-empty" id="search-empty" hidden>查無符合的文章</p>
  <script>{inline JS，見下方}</script>
</body>
</html>
```

- 結果列表沿用 SDLCAIP1-23 既有 `.article-list`/`.article-list__item` CSS
  class 與 DOM 結構（`<a href="/articles/{id}.html">{title}</a>` +
  `<time>` 為選用，本票不強制輸出 `published_at` 顯示，因 spec 未要求列出發布
  時間，只要求標題/內文比對），保持與列表頁視覺一致（範圍外已明訂「響應式版面
  細節沿用既有共用樣式」）。
- `#search-empty` 預設 `hidden`，只有「已輸入非空關鍵字且比對結果為 0 筆」時
  才移除 `hidden`（對應 AC5、AC7 的分界）。
- 標題以 `textContent` 賦值（非 `innerHTML`），避免索引中的 `title`/`content`
  字串（雖然已在產生 `search/index.json` 時由 SDLCAIP1-26/27 做過
  `html.escape()`，見下方技術決策）在瀏覽器端被當成 HTML 解析，双重防護、與
  SDLCAIP1-20 對使用者輸入一律轉義的既有邊界一致。

### 內嵌 JS 比對邏輯（輸出契約）

```javascript
(function () {
  var input = document.getElementById("search-input");
  var resultsEl = document.getElementById("search-results");
  var emptyEl = document.getElementById("search-empty");
  var indexData = null;

  fetch("/search/index.json")
    .then(function (res) { return res.json(); })
    .then(function (data) { indexData = data; })
    .catch(function () { indexData = []; });

  input.addEventListener("input", function () {
    var keyword = input.value.trim();
    resultsEl.innerHTML = "";
    emptyEl.hidden = true;

    if (keyword === "") {
      return; // AC7：空搜尋框不顯示任何結果或錯誤
    }

    var lowerKeyword = keyword.toLowerCase();
    var matches = (indexData || []).filter(function (item) {
      return item.title.toLowerCase().indexOf(lowerKeyword) !== -1 ||
             item.content.toLowerCase().indexOf(lowerKeyword) !== -1;
    });

    if (matches.length === 0) {
      emptyEl.hidden = false; // AC5
      return;
    }

    matches.forEach(function (item) {
      var li = document.createElement("li");
      li.className = "article-list__item";
      var a = document.createElement("a");
      a.className = "article-list__link";
      a.href = "/articles/" + item.id + ".html";
      a.textContent = item.title;
      li.appendChild(a);
      resultsEl.appendChild(li);
    });
  });
})();
```

- `input` 事件（非 `submit`）即時比對，無「送出」按鈕；`onsubmit="return
  false;"` 只是防止 Enter 鍵觸發表單預設的整頁重新載入導致索引重新 fetch
  ——與規格無關的純技術防護，不改變任何 AC 行為。
- `String.prototype.toLowerCase()` + `indexOf()` 實作「不分大小寫、子字串比對」
  （AC4），不使用正規表示式（避免使用者輸入被當成 regex 特殊字元解析導致
  非預期比對行為或例外）。
- fetch 尚未完成時使用者已輸入關鍵字：`indexData` 為 `null`，
  `(indexData || [])` 保底為空陣列，此時符合 AC5（查無結果）語意而非拋出例外
  ——索引載入時序與比對邏輯解耦，不需要額外的「載入中」狀態（規格未要求）。

## 資料模型

無新增資料模型。本票不改變 `search/index.json` 的 schema（由 SDLCAIP1-26/27
定案並產生/維護），本票的前端 JS 僅為該檔案的**唯讀消費者**。DynamoDB
`articles` 表結構不變。

## 關鍵技術決策

- **S3 key 為 `search.html`（bucket 根目錄），而非 `search/search.html` 或
  `search/index.html`**：`search/` 目錄本身已被 SDLCAIP1-26/27 定案用作索引
  資料檔（`search/index.json`）的命名空間；若頁面也放進同一目錄，
  `search/index.html`（S3 靜態網站託管對子目錄的 index document 慣例）容易與
  `search/index.json` 混淆、且訪客常見的直覺網址是 `/search.html`（比照
  `/articles/{id}.html` 平面結構、SDLCAIP1-23 的 `/index.html` 根目錄慣例）。
  用根目錄 `search.html` 讓「頁面」與「資料索引」在路徑上明確分離，同時延續
  既有靜態頁面（`index.html`、`articles/{id}.html`）多半置於淺層路徑的命名
  風格。

- **新增獨立函式 `_generate_and_upload_search_page()`，不併入
  `_generate_and_upload_list_pages`**：`search.html` 的內容是靜態不變的
  頁面骨架（HTML + CSS + JS），不依賴任何文章資料（比對邏輯在瀏覽器端讀取
  `search/index.json` 執行），與 `_generate_and_upload_list_pages` 每次都要
  重新 `scan()` DynamoDB 並依當前文章資料組出頁面內容的性質完全不同；混在
  同一函式會讓「查資料庫產生內容頁」與「產生固定骨架頁」的職責邊界模糊。

- **`search.html` 上傳時機：與既有 `create_article`/`update_article`/
  `delete_article` 的靜態頁重新產生時機同步覆蓋上傳**（沿用需求規格開放問題
  章節已揭露之推斷，非本文件新定案）：由於 `search.html` 內容本身固定不變
  （不含文章資料），此設計等同於「每次文章異動觸發現有 rollback 流程時，
  也一併呼叫 `_generate_and_upload_search_page()`」。具體整合點：在
  `_publish_article_and_lists_or_rollback`（create）與 `_publish_or_rollback`
  （update）內，`_generate_and_upload_list_pages(table)` 呼叫之後、成功路徑
  返回 `None` 之前，追加呼叫 `_generate_and_upload_search_page()`；
  `delete_article` 則在既有 `_generate_and_upload_list_pages(table)` 呼叫
  之後追加同一呼叫。若上傳失敗，比照同函式內既有其他靜態頁上傳失敗的錯誤
  處理路徑（拋出 `StaticPageGenerationError("search-page", exc)`，走既有
  rollback／502 邏輯），不新增獨立錯誤碼。**此決策不屬於本票 AC 明文要求
  （8 條 AC 皆聚焦頁面本身行為），是為了避免 `search.html` 在 SDLCAIP1-26/27
  尚未合併前無人上傳導致頁面 404 的整合缺口**，開發者實作時仍以
  `search/index.json` 的實際存在與否（由 SDLCAIP1-26/27 保證）作為 AC5「查無
  結果」以外的容錯輸入，兩者為獨立的靜態物件，各自的上傳失敗互不阻擋對方。

- **不重新設計整頁 CSS，重用 `_ARTICLE_PAGE_STYLE` + 新增最小
  `_SEARCH_PAGE_STYLE`（僅搜尋框樣式）**：比照 SDLCAIP1-23 對
  `_LIST_PAGE_STYLE` 的處理方式——響應式基礎版面（viewport meta、斷點）已由
  `_ARTICLE_PAGE_STYLE` 提供，搜尋頁只需疊加搜尋框與結果列表的最小樣式，結果
  列表直接沿用 SDLCAIP1-23 的 `.article-list`/`.article-list__item` class，
  不重新定義，維持視覺一致（範圍外已明訂沿用既有共用樣式）。

- **其他頁面加入 `/search.html` 連結的具體改動點**：
  - `_render_list_page_html`（`src/cms_aipilot/main.py`）：在 `<nav
    class="pagination">` 區塊外（例如頁首或頁尾固定位置）新增一個
    `<a href="/search.html">搜尋文章</a>` 連結，套用到 `index.html` 與
    `page/{n}.html`（同一函式產生所有分頁，改動一處即涵蓋全部）。
  - `_generate_and_upload_static_page`（文章詳細頁）：在
    `<article class="article">` 區塊外新增同樣的 `/search.html` 連結。
  - 兩處連結皆用絕對根路徑 `/search.html`，理由與 SDLCAIP1-23 既有連結風格
    一致（列表頁位於 `page/` 子目錄，相對路徑深度不一致，統一用絕對路徑
    消除歧義）。
  - `search.html` 自身不需要連回自己，但比照其他頁面的導覽一致性，可選擇性
    加入回首頁連結（`/index.html`）；此為既有頁面共通的導覽慣例延伸，非本票
    AC 要求的必要項目，開發者可自由決定是否加入，不影響任何驗收條件。

## 開放設計問題（定稿時必須為空）

無。
