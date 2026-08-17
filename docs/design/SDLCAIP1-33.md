# 設計文件 — SDLCAIP1-33 後台新增/編輯文章表單 UI 套用設計規範

## 對應需求規格

G1 通過版本：作為使用後台的管理者，我希望新增/編輯文章表單（`ArticleForm.tsx`）
視覺符合 `docs/design-system.md` 定義的規範，讓後台介面呈現一致、專業的視覺風格。
驗收條件（Gherkin，共 6 條）：

1. 色彩與字體套用 token：`ArticleForm.tsx` 計算後樣式（標題／欄位／按鈕）皆來自
   `design-tokens.css` 變數。
2. 表單欄位規則套用：標題／內容／發布時間三個欄位——label 置於欄位上方靠左；
   必填以文字標示（非僅用顏色）；錯誤訊息紅色文字 + 圖示，不能只靠邊框變色。
3. 無障礙基本要求（§8）：所有欄位有 label，可見的 focus 樣式。
4. 按鈕變體套用：「儲存」（submit）套用 primary 樣式（黑底白字）；「取消」
   （`type="button"`）套用 secondary 樣式（白底黑框）；皆無圓角或極小圓角。
5. 標題與版面對齊規則套用（§6）：表單 `<h1>` 置中；label／欄位維持靠左。
6. 既有測試不受影響：`ArticleForm.test.tsx` 全部維持通過。

範圍外（已定案，不重新討論）：表單驗證/送出行為改動；系統化 Button/Input
元件抽象化。

依賴：`docs/design-system.md`（色彩/字體/間距/斷點/元件規則權威來源）；
SDLCAIP1-30（`frontend/src/styles/design-tokens.css` 已存在並提供
`--color-*`/`--font-*`/`--space-*` 變數，本票只消費，不重新定義基礎 token 數值）。

## 介面/API 契約

無。本票純屬前端 `ArticleForm.tsx` 的樣式與 markup 調整，不新增/變更任何對外
HTTP 端點。`frontend/src/api/articles.ts`（`createArticle`/`updateArticle`/
`getArticle`）的 request/response 型別與呼叫方式完全不動；文章載入失敗、
401、422、502 等既有錯誤分支與對應訊息文字（`NOT_FOUND_MESSAGE` 等常數）皆
不變——本票只改變這些既有訊息「怎麼呈現」（紅色文字 + 圖示），不改變「呈現
什麼」或「何時呈現」。

## 資料模型

無新增資料模型。不新增/變更 DynamoDB 欄位、資料表或索引；本票只觸碰
`frontend/src/pages/ArticleForm.tsx` 與新增的 `frontend/src/pages/
ArticleForm.css`，皆為前端原始碼檔案。

## 關鍵技術決策

- **新增 `--color-error: #B00020` 至 `frontend/src/styles/design-tokens.css`
  （僅前端該份檔案，不同步至 `src/cms_aipilot/static/design-tokens.css`）**：
  `docs/design-system.md` §1 明訂 `--color-accent` 為「無」是核心風格特徵，但
  同一節也明訂例外條款——「若未來某個 Story 真的需要功能色（例如表單錯誤
  提示），視為例外並在該 Story 的設計文件中明確說明，不要回頭改這份全域
  規範」。本票的錯誤訊息紅色正是該條款預期的例外情境，因此在此設計文件中
  明確決定新增此 token，且不回頭修改 `docs/design-system.md` §1 的色彩表。
  數值選 `#B00020`：對比 `--color-bg`（`#FFFFFF`）計算對比度約 7.3:1，遠高於
  WCAG AA 一般文字 4.5:1 門檻（符合 §8 對比要求）；色相偏暗紅而非鮮紅，與
  整體黑白極簡、低飽和的編輯感風格較為協調。只加到前端檔案、不加到後端
  `src/cms_aipilot/static/design-tokens.css`：後端目前產生的靜態頁（文章
  頁/列表頁/搜尋頁）沒有表單或任何需要錯誤提示色的畫面，加入未使用的 token
  只會製造死重量；SDLCAIP1-30 設計文件中「兩份檔案須逐位元組相同」的決策
  針對的是「§1-5 全域基礎 token 集合」，本票新增的是該文件自身允許的
  「功能色例外」，兩者不衝突，但仍在此明確記錄這個已知的刻意分歧，避免
  未來讀者誤以為是遺漏同步。

- **必填標示：於 `<label>` 元素「外部」（同層 sibling `<span>`），而非
  `<label>` 內部巢狀，插入「（必填）」文字**：`ArticleForm.test.tsx`
  現有大量 `screen.getByLabelText("標題")`／`"內容"`／`"發布時間"`
  斷言（AC6 要求不得破壞）。`@testing-library/dom` 的 `getByLabelText`
  比對 `<label>` 元素時是取該元素完整 `textContent`（不感知
  `aria-hidden`），若把「（必填）」文字放進 `<label>` 內（即使加
  `aria-hidden="true"`），比對字串會變成 `"標題（必填）"`，與既有測試的
  精確字串比對不符，導致既有測試全數失敗。因此三個欄位統一改成
  `<div className="article-form__label-row"><label htmlFor="...">標題
  </label><span className="article-form__required-marker">（必填）
  </span></div>` 的 sibling 結構——視覺上仍緊鄰 label、符合 §7「label
  置於欄位上方靠左」與「必填以文字標示（非僅用顏色）」的規則，同時
  `<label>` 本身的 `textContent` 維持原字串不變。三個欄位（標題、內容、
  發布時間）一律套用同一結構，不因為目前只有「發布時間」在 HTML 上有
  `required` 屬性、標題/內容是 JS 端驗證，而有不同標示方式——三者在業務
  邏輯上都是必填欄位（`handleSubmit` 對標題/內容有必填檢查，`published_at`
  有 HTML `required`），視覺標示規則不應因驗證機制不同而不一致。不新增
  `required`/`aria-required` 屬性到標題/內容欄位：新增原生 `required`
  屬性會讓瀏覽器在 `submit` 前攔截表單（原生 constraint validation），
  可能使既有依賴 `handleSubmit` JS 邏輯觸發 `TITLE_REQUIRED_MESSAGE`/
  `CONTENT_REQUIRED_MESSAGE` 的測試行為改變，屬於「表單驗證/送出行為
  改動」，明確列在本 Story 範圍外，故不動。

- **錯誤訊息圖示：inline SVG（無新增圖示庫依賴），`aria-hidden="true"
  focusable="false"`，置於既有 `<p role="alert">` 內、錯誤文字之前，
  顏色以 `currentColor` 繼承外層 `.article-form__error` 的
  `var(--color-error)`**：`frontend/package.json` 目前無任何圖示庫
  依賴（無 lucide-react/heroicons 等），新增依賴超出本票「不做系統化
  元件抽象化」的範圍外聲明；inline SVG 不需要額外套件、bundle
  size 可忽略。SVG 純裝飾（訊息文字本身已透過 `role="alert"` 傳達語意），
  故 `aria-hidden="true"`，不影響螢幕報讀器行為，也不影響
  `toHaveTextContent(...)` 系列既有測試斷言（SVG 不產生文字節點，
  `toHaveTextContent` 預設為子字串比對，訊息文字本身不變）。三處錯誤
  訊息（標題必填、內容必填、`submitError` 各分支）統一套用同一
  `article-form__error` 結構與同一顆 SVG，不用各自決定圖示。

- **按鈕樣式以 class 區分變體（`article-form__button--primary` /
  `--secondary`），不新增獨立 Button 元件**：spec 範圍外聲明已明確排除
  「系統化 Button/Input 元件抽象化」，本票只需讓這兩顆既有 `<button>`
  在視覺上分別套用 primary/secondary 樣式，用 CSS class 是最小改動；
  未來若有第三張表單需要同樣的按鈕變體，才是「系統化抽象」該發生的
  時機（不在本票預先設計）。

- **`--color-error` 為本批次（SDLCAIP1-31/32/33 同時 Designing）共用的
  token，非本票獨佔**：同批次的 SDLCAIP1-31（後台登入頁）設計文件獨立
  分析後得出相同的 `#B00020` 數值，orchestrator 複核後統一兩份文件皆
  消費本票在此新增的同一個 `--color-error` 變數（而非各自寫死字面值），
  避免在 `design-tokens.css` 之外重新製造色碼重複。後續其他頁面 Story
  若也需要錯誤色，應消費此既有 token，不重新定義。

- **`border-radius: 0`（無圓角，非「極小圓角」的模糊選項）**：
  `docs/design-system.md` §7 按鈕規則寫「無圓角或極小圓角」，本票選定
  `0` 這個具體值而非某個曖昧的極小 px 數，理由是同節整體風格描述
  「比照整體方正極簡調性」——`0` 是最直接、最不需要臨場判斷「多小算極
  小」的落地值，也與本站其餘元件（表單欄位邊框、既有卡片/列表規則
  §7）目前皆無圓角的既有慣例一致。

- **focus-visible 樣式（非 `:focus`）套用 `outline: 2px solid
  var(--color-text-primary); outline-offset: 2px;` 於表單內所有
  `input`/`textarea`/`button`**：用 `:focus-visible` 而非 `:focus`，
  避免滑鼠點擊時也顯示 outline（多數瀏覽器 `:focus-visible` 只在鍵盤
  導覽時觸發），符合鍵盤可操作性需求同時不犧牲滑鼠使用者的視覺乾淨度；
  顏色用既有 `--color-text-primary`（`#111111`）而非新色，因為
  `docs/design-system.md` 全站本就無強調色，focus 指示用主文字色已經
  對比 `--color-bg` 達 AA 等級（§1 已驗證），不需要另外定義 focus 專屬
  色彩 token。`outline-offset: 2px` 讓 outline 與欄位邊框（`--color-
  border`）之間留出間距，避免兩條線黏在一起難以辨識。

- **§6 置中範圍：僅 `<h1>`（`article-form__title`）套用
  `text-align: center`；label、欄位、必填標示、錯誤訊息、按鈕列全部
  維持靠左（不額外置中）**：`docs/design-system.md` §6 明確列出「置中」
  的對象是「頁面/文章標題、日期、meta 資訊、導覽列」，「靠左」是「內文
  段落（含文章正文、表單說明文字）」。本表單裡唯一符合「標題」定義的
  元素是 `<h1>`；按鈕列不屬於標題/日期/meta/導覽列任何一類，也不是內文
  段落，但 §7 表單欄位規則已明確要求 label 靠左，本票將按鈕列視為表單
  操作區的延伸，維持與欄位同一垂直對齊基準（靠左，預設 block 排列，不
  加 `text-align: center`），避免表單內視覺對齊基準不一致（標題置中、
  欄位靠左、按鈕又置中會顯得凌亂）。

## 開放設計問題（定稿時必須為空）

無。
