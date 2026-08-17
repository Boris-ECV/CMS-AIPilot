# 設計文件 — SDLCAIP1-32 後台文章列表頁 + 刪除確認互動 UI 套用設計規範

## 對應需求規格

G1 通過版本：作為使用後台的管理者，我希望文章列表頁（`ArticlesList.tsx`）
視覺符合 `docs/design-system.md` 定義的規範，讓後台介面呈現一致、專業的
視覺風格。驗收條件（Gherkin，共 5 條）：

1. 色彩與字體套用 token：`ArticlesList.tsx`（目前零 CSS）——表格、按鈕
   計算後樣式皆來自 `design-tokens.css` 變數。
2. 列表項分隔不用邊框/陰影/色塊（§7 卡片/列表項規則）：每個表格列改用
   `--space-*` 間距 token 做分隔，不用 border/box-shadow/background-color；
   表格結構維持 `<table>`，不改為卡片式版面。
3. 一般按鈕套用 primary/secondary/danger 樣式（§7 按鈕規則）：「編輯」
   連結、「刪除」按鈕、「上一頁/下一頁」分頁按鈕。刪除按鈕套用 danger
   變體，其餘操作按鈕套用 secondary 變體，皆無/極小圓角。
4. 可鍵盤操作元素的 focus 樣式可見（§8）：Tab 到編輯連結/刪除按鈕/分頁
   按鈕須顯示可見的 focus 樣式（不可 `outline: none` 卻無替代樣式）。
5. 既有測試不受影響：`ArticlesList.test.tsx`（含 SDLCAIP1-14 刪除確認
   測試）須全數維持通過；不修改既有斷言行為，僅新增樣式相關測試。

範圍外（已定案，不重新討論，含 HUMAN-INPUT SDLCAIP1-37 決議的 2 項）：

- 不含列表資料邏輯、分頁邏輯、刪除 API 行為變更，僅視覺樣式。
- 不含共用 Button/Modal 元件抽象化，僅本頁面套用樣式規則。
- 不含將 `window.confirm()` 換成自訂 Modal 元件（依 HUMAN-INPUT
  SDLCAIP1-37 Q1 決議選項 A：原生確認對話框維持不套用樣式，若未來需要
  自訂樣式的確認互動，另開新 Story 評估）。
- 不含將 `<table>` 結構改為卡片式列表版面（依 SDLCAIP1-37 Q2 決議選項
  A：表格欄位內容維持靠左，不套用 §6 置中規則，僅移除既有結構的邊框/
  陰影/色塊分隔）。

依賴：`docs/design-system.md`（色彩/字體/間距/元件規則權威來源）；
SDLCAIP1-30（`frontend/src/styles/design-tokens.css` 已存在並提供
`--color-*`/`--font-*`/`--space-*` 變數，本票只消費，不重新定義基礎
token 數值）；SDLCAIP1-31、SDLCAIP1-33（同批次，已各自在設計文件中新增
`--color-error: #B00020` 至 `frontend/src/styles/design-tokens.css`，
用於錯誤訊息文字色——本票沿用同一份 token 檔案，但如下方關鍵決策所述，
本票用途與該 token 原始語意不同，需明確評估是否消費它）。

## 介面/API 契約

無。本票純屬前端 `ArticlesList.tsx` 的 JSX class 標記調整與新增
`ArticlesList.css` 樣式規則，不新增/變更任何對外 HTTP 端點。
`frontend/src/api/articles.ts`（`listArticles`/`deleteArticle`）的
request/response 型別、呼叫時機與既有 401/404/502/其他錯誤分支處理
（`GENERIC_ERROR_MESSAGE`、`DELETE_NOT_FOUND_NOTICE`、
`DELETE_STATIC_PAGE_WARNING`、`DELETE_GENERIC_ERROR_MESSAGE` 等常數與
文字）完全不動——本票只改變既有畫面元素「怎麼呈現」，不改變「呈現
什麼」或「何時呈現」。刪除確認互動維持呼叫原生 `window.confirm()`，
不套用任何樣式（依 HUMAN-INPUT SDLCAIP1-37 Q1 決議，範圍外）。

## 資料模型

無新增資料模型。不新增/變更 DynamoDB 欄位、資料表或索引；本票只觸碰
`frontend/src/pages/ArticlesList.tsx` 與新增的 `frontend/src/pages/
ArticlesList.css`，皆為前端原始碼檔案。

## 關鍵技術決策

- **不消費既有 `--color-error` token 作為文字色；本頁不需要任何「錯誤
  文字」樣式**：本票驗收條件不含錯誤訊息文字紅字化的 AC（比對
  SDLCAIP1-31/33 皆有明確的「錯誤訊息紅字 + 圖示」AC，本票沒有）。
  `ArticlesList.tsx` 現有 `error`/`deleteError`（`role="alert"`）與
  `notice`（`role="status"`）維持既有純文字呈現，不在本票範圍內套用
  紅字/圖示樣式——這若要做，屬於未在 spec 中要求的產品外觀決策（例如
  「刪除失敗訊息是否也要紅字」spec 未提及），不在此自行擴大範圍。因此
  本頁完全不需要 `--color-error` 用於文字色的既有用途。

- **danger 按鈕變體重用既有 `--color-error: #B00020` token 作為
  border/文字色（非新增 `--color-danger` token），視覺結構為「白底 +
  紅框 + 紅字」（與 secondary 變體同構，只是強調色從黑換成紅），不做
  紅色實心背景**：
  - 重用理由：`--color-error` 已由 SDLCAIP1-31/33 建立為本站唯一的
    「功能色例外」token，語意就是「危險/錯誤」；`docs/design-system.md`
    §7 按鈕規則寫「danger……紅色系」，沒有規定要另開新色號，且新增
    `--color-danger` 只會製造第二個紅色 token、與第一個視覺上難以
    分辨，違反 SDLCAIP1-33 設計文件已明訂的「後續其他頁面 Story 若也
    需要錯誤色，應消費此既有 token，不重新定義」原則。
  - 不做實心紅底（不同於 primary 的黑底白字結構）：§0 風格定位強調
    全站「無強調色、大量留白」的極簡調性，§7 對按鈕的例外只到「danger
    紅色系」為止，沒有要求做成搶眼色塊；用細框線 + 紅字（而非大面積紅
    背景）維持與 secondary（白底黑框）視覺結構一致、只替換強調色，
    避免刪除按鈕在畫面上過度突兀，同時仍清楚可辨識為「危險操作」。
  - 對比度：`#B00020` 文字 on `#FFFFFF` 背景已由 SDLCAIP1-31/33 驗證約
    7.3:1，遠超 WCAG AA 4.5:1；本頁沿用相同前景/背景組合，對比度結論
    直接成立，不需重新計算。

- **列表列分隔改用 `<table>` 的 `border-spacing`（配合
  `border-collapse: separate`）達成純間距分隔，不改變 `<table>` 結構
  或欄位數**：
  ```css
  .articles-list__table {
    border-collapse: separate;
    border-spacing: 0 var(--space-3); /* 水平 0、列間垂直間距 12px */
    width: 100%;
  }
  .articles-list__table th,
  .articles-list__table td {
    text-align: left; /* 依 SDLCAIP1-37 Q2 決議，維持靠左，不套用 §6 置中 */
    padding: var(--space-2) var(--space-3);
    font-family: var(--font-family-base);
    font-size: var(--font-size-body);
    color: var(--color-text-primary);
  }
  .articles-list__table th {
    font-weight: var(--font-weight-h2);
  }
  ```
  §7「卡片/列表項……不用邊框、陰影、背景色塊；用間距 scale 的留白本身
  分隔項目」明確指名用留白而非邊框分隔，但 `<tr>` 元素不支援
  `margin`（CSS 表格排版模型下 margin 對 table-row 無效），無法比照
  SDLCAIP1-31 欄位間距那樣直接在列元素上加 `margin-bottom`。
  `border-spacing`（搭配 `border-collapse: separate`，此為 `<table>`
  預設值，此處顯式宣告以避免被其他樣式意外覆寫為 `collapse`）是
  CSS 表格排版模型下讓「列與列之間留白」但不產生任何 border/box-shadow
  的正規機制，效果等同於「列間距 12px、不畫線」，精確對應 AC2 的字面
  要求，且不需要放棄 `<table>` 語意結構（HUMAN-INPUT 已定案不改卡片
  式）。垂直間距選 `--space-3`（12px）而非更大的 `--space-4`
  （16px）：列表項目本身資訊密度低（僅標題/日期/操作三欄），12px 已
  提供清楚的視覺分隔，貼近 §7 參考截圖「三欄式列表」的緊湊留白感，
  16px 留給版面區塊之間（沿用 SDLCAIP1-31/33 用 `--space-4` 做欄位群組
  間距的既有語彙），避免同一頁面內間距層級混淆。

- **按鈕變體以 class 區分（`articles-list__button--secondary` /
  `--danger`），套用於「編輯」`<Link>`、「刪除」`<button>`、
  「上一頁/下一頁」`<button>`，不新增獨立 Button 元件**：
  ```css
  .articles-list__button {
    display: inline-block;
    font-family: var(--font-family-base);
    font-size: var(--font-size-body);
    padding: var(--space-1) var(--space-3);
    border-radius: 0; /* 無圓角，理由同 SDLCAIP1-33：比照方正極簡調性，避免曖昧的「極小」判斷 */
    text-decoration: none;
    cursor: pointer;
    background-color: var(--color-bg);
  }
  .articles-list__button--secondary {
    border: 1px solid var(--color-text-primary);
    color: var(--color-text-primary);
  }
  .articles-list__button--danger {
    border: 1px solid var(--color-error);
    color: var(--color-error);
  }
  .articles-list__button:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
  ```
  「編輯」是 `<Link>`（`<a>`），非 `<button>`：套用
  `articles-list__button--secondary` 讓它在視覺上與其他操作按鈕一致
  （AC3 字面要求「編輯」也套用樣式），`text-decoration: none` 覆蓋
  §7 一般文字連結「底線樣式」的預設規則——因為此連結在此情境下功能上
  是一顆「操作按鈕」（與刪除按鈕並列、外觀對稱），不是一般文字內連結，
  比照 AC3 明確把它與「刪除」「上一頁/下一頁」歸為同一類「一般按鈕」
  處理，不套用純文字連結規則，避免視覺上一個底線一個框線的不一致。
  不新增獨立 Button 元件：spec 範圍外聲明已明確排除「共用 Button/Modal
  元件抽象化」，用 CSS class 是本票要求的最小改動；與 SDLCAIP1-33
  「按鈕樣式以 class 區分變體，不新增獨立 Button 元件」決策一致，維持
  同批次做法統一。本頁不需要 primary 變體：AC3 明確只要求「編輯」
  「上一頁/下一頁」套 secondary、「刪除」套 danger，頁面上沒有任何
  按鈕落在 primary（黑底白字）情境，不預先設計未被要求的變體。

- **focus-visible 樣式沿用 SDLCAIP1-31/33 同一組值，套用於
  `.articles-list__button`（含 Link 與 button）**：
  ```css
  .articles-list__button:focus-visible {
    outline: 2px solid var(--color-text-primary);
    outline-offset: 2px;
  }
  ```
  與同批次兩張設計文件一致選用 `:focus-visible`（非 `:focus`）避免
  滑鼠點擊也顯示外框、`--color-text-primary` 黑色而非新色（全站無強調
  色，focus 用主文字色對比 `--color-bg` 已達 AA）、`outline-offset: 2px`
  避免外框與按鈕邊框黏在一起。danger 按鈕的 focus 外框仍用黑色而非紅色：
  focus 樣式的功能是「標示鍵盤焦點位置」，與按鈕本身的語意色（紅=危險）
  是兩件事，統一用同一顆黑色 outline 讓「目前焦點在哪」在全頁面（含
  secondary/danger 按鈕）視覺語彙一致，不需要為每種按鈕變體各自定義
  一種 focus 顏色。

- **表格結構、欄位數與既有 `data-testid`/`role` 屬性完全不變，僅新增
  `className`**：`<table>`/`<thead>`/`<tbody>`/`<tr>`/`<th>`/`<td>` 標籤
  與既有 3 欄（標題、發布日期、操作）結構不動；`Link to={editPath(...)}`
  的 `href` 產出邏輯、`data-testid={`delete-article-${article.id}`}`、
  `getByRole("row")`/`getByRole("link", { name: "編輯" })`/
  `getByRole("button", { name: "下一頁" })` 等既有測試依賴的可存取名稱
  與屬性皆不動，只在對應元素加上本文件定義的 `className`。確認
  `ArticlesList.test.tsx` 現有斷言（含 SDLCAIP1-14 六條刪除確認測試）
  皆基於文字內容/role/testid，不依賴目前不存在的 class 或 inline
  style，加上樣式不影響既有斷言（AC5 過關）。

- **`design-tokens.css` 匯入方式沿用既有機制，新增
  `frontend/src/pages/ArticlesList.css` 承載本頁樣式規則**：
  `ArticlesList.tsx` 目前完全無 CSS import（AC1 描述「目前零 CSS」），
  比照 SDLCAIP1-30/31 在 `LoginPage.tsx` 建立的模式，於
  `ArticlesList.tsx` 頂部加入 `import "../styles/design-tokens.css";`
  與 `import "./ArticlesList.css";`，新規則寫在新的
  `ArticlesList.css`（而非塞進既有共用檔案），維持「一個頁面一份樣式
  檔」的既有慣例，與 SDLCAIP1-31（`LoginPage.css`）、SDLCAIP1-33
  （`ArticleForm.css`）並列一致。

## 開放設計問題（定稿時必須為空）

無。
