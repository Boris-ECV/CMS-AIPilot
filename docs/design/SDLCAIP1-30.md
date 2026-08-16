# 設計文件 — SDLCAIP1-30 建立共用視覺樣式 Token 機制（design-tokens.css）

## 對應需求規格

G1 通過版本：作為維護 CMS AI Pilot 的開發者，前台靜態頁與後台管理介面共用同一份
視覺樣式 token（色彩、字級、間距、斷點），以便之後每一張 UI 優化 Story 不用各自
重新定義樣式數值，視覺風格能保持全站一致。驗收條件（Gherkin，共 3 條）：

1. `design-tokens.css` 內容包含 `docs/design-system.md` 第 1-5 節定義的全部色彩/
   字體/間距/斷點 token，數值完全一致。
2. 後台觸發的靜態頁發布/rollback 流程（沿用 `search.html` 的既有作法）將
   `design-tokens.css` 同步上傳至 S3 對應路徑。
3. 後台管理介面（`frontend/`）`npm run build` 後，至少一個既有元件實際
   `import` 並套用此檔案（非僅存在未被引用）。

範圍外（已定案，不重新討論）：既有前台靜態頁（文章列表/詳細頁/首頁列表/搜尋頁）
既有 inline `<style>` 改為引用此檔案；後台元件層級樣式規則系統化實作（按鈕/表單/
卡片樣式等，`design-tokens.css` 之外的部分）；`frontend/` 除單一驗證用元件
（本文件選定 LoginPage）以外的其他元件套用 CSS。

依賴：`docs/design-system.md`（本文件視為色彩/字體/間距/斷點數值的權威來源，
本票不重新定義任何數值，只負責把它轉成 CSS 自訂屬性並落地到前後台）；
SDLCAIP1-28（`_generate_and_upload_search_page()` 的固定骨架靜態資源上傳模式，
本票沿用同一模式）；SDLCAIP1-18（`frontend/` 專案骨架，Vite+React+TS）。

## 介面/API 契約

無新增/變更對外 HTTP API。本票不觸碰 `articles_router` 任何端點的 request/
response 格式；`create_article`/`update_article`/`delete_article` 的既有回應
格式（成功 body、502 錯誤 body）不變，只新增這三個端點成功路徑中的一個 S3
上傳副作用（見「關鍵技術決策」）。

`design-tokens.css` 本身的「契約」是它對外暴露的 CSS 自訂屬性集合——developer
需原樣輸出以下變數，數值抄自 `docs/design-system.md` 第 1-5 節，不得自行調整：

```css
:root {
  /* 色彩（design-system.md §1）*/
  --color-bg: #FFFFFF;
  --color-text-primary: #111111;
  --color-text-secondary: #111111;
  --color-border: #E5E5E5;
  /* 注意：--color-accent 不定義，見下方關鍵技術決策 */

  /* 字體家族（design-system.md §2）*/
  --font-family-base: -apple-system, BlinkMacSystemFont, "PingFang TC",
    "Noto Sans TC", sans-serif;

  /* 字級階層（design-system.md §3）：font-size / line-height / font-weight */
  --font-size-display: 2.5rem;
  --line-height-display: 1.3;
  --font-weight-display: 400;

  --font-size-h1: 2rem;
  --line-height-h1: 1.35;
  --font-weight-h1: 600;

  --font-size-h2: 1.5rem;
  --line-height-h2: 1.4;
  --font-weight-h2: 600;

  --font-size-body: 1rem;
  --line-height-body: 1.7;
  --font-weight-body: 400;

  --font-size-meta: 0.875rem;
  --line-height-meta: 1.5;
  --font-weight-meta: 400;

  --font-size-nav: 0.9375rem;
  --line-height-nav: 1.5;
  --font-weight-nav: 400;

  /* 間距 Scale（design-system.md §4）*/
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 24px;
  --space-6: 32px;
  --space-7: 48px;
  --space-8: 64px;

  /* RWD 斷點（design-system.md §5）——僅供文件/JS 讀取參考，
     不可用於 @media 條件式，見下方關鍵技術決策 */
  --breakpoint-tablet-min: 768px;
  --breakpoint-tablet-max: 1024px;
  --breakpoint-desktop-min: 1025px;
}
```

檔案只含單一 `:root` 選擇器與上述變數，不含任何元件層級樣式規則（比照
`docs/design-system.md` §9 的既有決定）。

## 資料模型

無新增資料模型。不新增/變更 DynamoDB 欄位、資料表或索引；`design-tokens.css`
是 S3 靜態物件與前端原始碼檔案，不是資料庫層資料。

## 關鍵技術決策

- **兩份實體檔案（後台 `src/cms_aipilot/static/design-tokens.css` 與前端
  `frontend/src/styles/design-tokens.css`），內容須逐位元組相同，不做跨目錄
  讀取共用同一份檔案**：`project-profile.yaml` 明確記載「frontend/
  ...independent of the backend Lambda deploy unit」——後端部署單元未來封裝
  時很可能只打包 `src/cms_aipilot/`，若後端上傳函式改在執行期讀取
  `frontend/src/styles/` 底下的檔案，一旦部署封裝落地會直接讀不到檔案而失敗。
  因此後端維護自己的一份、放在會隨後端部署單元一起打包的
  `src/cms_aipilot/static/` 底下；前端維護 `docs/design-system.md` §9 已明訂
  的 `frontend/src/styles/` 路徑。本票不建立自動同步機制（不在 spec 範圍內、
  也無現成建置管線可掛載此步驟）——兩份檔案由 developer 手動保持一致，AC1
  的驗收基準是「內容比對 `docs/design-system.md`」而非「兩檔案互相比對」，
  故此手動維護風險不影響本票驗收，但列為已知維運負擔供未來參考。

- **S3 Key 為 `design-tokens.css`（bucket 根目錄），比照 `search.html` 而非
  `articles/`、`page/`、`search/` 前綴目錄慣例**：這些前綴目錄用於區分「內容
  類型」（文章頁/列表頁/搜尋索引），而 `design-tokens.css` 與 `search.html`
  同屬「全站共用、與特定文章資料無關的固定資源」，放根目錄讓所有現有與未來的
  靜態頁面都能用同一個淺層相對路徑 `<link rel="stylesheet" href="/design-
  tokens.css">` 引用，不用因頁面所在目錄深度不同而調整相對路徑。

- **新增獨立函式 `_generate_and_upload_design_tokens()`，讀取
  `src/cms_aipilot/static/design-tokens.css` 檔案內容並以
  `ContentType="text/css"` 上傳至上述 S3 key；讀檔或上傳任一步驟失敗皆拋出
  `StaticPageGenerationError("design-tokens", exc)`（沿用既有例外類別，不新增
  錯誤碼/例外類別）**：比照 SDLCAIP1-28 `_generate_and_upload_search_page()`
  的既有模式——內容固定不依賴文章資料，函式本身無參數。讀檔失敗（例如部署時
  該檔案遺漏）與 S3 上傳失敗，對呼叫端而言都是「這次發布沒有完整上線」的同一
  類失敗，用同一個既有例外類別與既有 502/rollback 路徑處理，符合
  `CONSTITUTION.md` 失敗處理哲學「不可讓例外無聲穿透」與「不可讓部分頁面新、
  部分頁面舊且無記錄」的要求，也不需要開發者臨場決定新的錯誤處理形狀。

- **呼叫點：`_publish_article_and_lists_or_rollback`（create）、
  `_publish_or_rollback`（update）內，緊接在既有
  `_generate_and_upload_search_page()` 呼叫之後追加一行
  `_generate_and_upload_design_tokens()`；`delete_article` 內，緊接在既有
  「`_generate_and_upload_search_page()` 失敗回傳
  `STATIC_SEARCH_PAGE_REGENERATION_FAILED`」的 try/except 區塊之後，追加一組
  結構相同的 try/except，成功時繼續往下（回傳既有 204），失敗時回傳
  `502 {"error_code": "STATIC_DESIGN_TOKENS_REGENERATION_FAILED", "detail":
  "Article deleted but the design tokens stylesheet could not be
  regenerated.", "article_id": article_id}`**：三個掛載點與現有
  `_generate_and_upload_search_page()` 完全對稱，符合 AC2「沿用現有
  `search.html` 等全域靜態資源的作法」的字面要求，也維持
  `_publish_article_and_lists_or_rollback`/`_publish_or_rollback` 內既有的
  「依序執行、任一失敗即用同一個 502 回應與 rollback」共用 except 結構
  （create/update 路徑），`delete_article` 則維持其既有的「每個靜態資源各自
  獨立 try/except、各自獨立 error_code」既有風格（該函式對 list pages/search
  index/search page 已是此風格，本票新增項目沿用，不引入新結構）。

- **前端消費方式：`frontend/src/styles/design-tokens.css` 只含
  `:root` 變數（無 build-time 特殊處理，Vite 原生支援 CSS 靜態 import），由
  `frontend/src/pages/LoginPage.tsx` 直接 `import "../styles/design-tokens.css"`
  載入至頁面；同時新增 `frontend/src/pages/LoginPage.css`（`import
  "./LoginPage.css"`）套用少數 `var(--color-text-primary)`、
  `var(--font-family-base)`、`var(--space-4)` 等變數於既有的 `<h1>`/`<form>`/
  `<button>` 元素（對應元素新增 `className`，不改變既有欄位結構、`id`、
  `htmlFor`、既有測試選取器）**：AC3 要求「至少一個既有元件 import 並生效
  （瀏覽器開發工具可驗證變數值已套用）」——只 import token 檔本身（純變數
  宣告，無選擇器作用於任何元素）不會產生「套用」的可觀察效果，需搭配套用
  這些變數的元件層級 CSS 才能在瀏覽器 DevTools 看到計算後樣式值改變，因此
  兩個檔案都需要新增。選 `LoginPage` 是延續需求規格「範圍外」段落建議、且
  `LoginPage.tsx` 目前無任何 CSS，改動面積最小、不影響其表單驗證/提交邏輯與
  既有測試（`LoginPage.test.tsx` 走 `getByLabelText`/`getByRole`，不依賴
  class name）。

- **`--color-accent` 不定義為 CSS 自訂屬性（即使留空字串或
  `initial` 佔位）**：`docs/design-system.md` §1 明確記載其值為「無」，是本
  視覺風格的核心特徵（不設強調色），定義一個空值變數只會誘使未來開發者誤用
  `var(--color-accent, someFallback)` 或疑惑該變數為何永遠是空的；不存在此
  變數本身就是最直接的「本站無強調色」表達方式，未來真的需要功能色時依
  design-system.md §1 的既有指引在該 Story 個別新增，不動本票範圍。

- **RWD 斷點以 CSS 自訂屬性形式暴露（`--breakpoint-*`），但僅供文件/未來
  JS 讀取參考用，不能也不會被用於 `@media` 條件式**：CSS 規格目前（含所有
  目標瀏覽器的穩定版本）不支援在 `@media` 條件式中使用 `var()`
  （Custom Media Queries 屬 CSS 草案，未達穩定可用），因此 AC1 要求的「斷點
  token」只能以自訂屬性形式滿足「內容包含該 token」的字面驗收，實際套用斷點
  行為的既有程式碼（`src/cms_aipilot/main.py` 的 `_ARTICLE_PAGE_STYLE`
  `@media` 規則）與後台若未來新增響應式樣式時，媒體查詢條件仍必須寫死數值字
  面量，不能引用這些變數；此為 CSS 語言限制而非本票設計缺陷，明確記錄避免
  未來開發者誤以為可以 `@media (min-width: var(--breakpoint-tablet-min))`。

## 開放設計問題（定稿時必須為空）

無。
