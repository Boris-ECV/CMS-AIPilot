# 設計文件 — SDLCAIP1-31 後台登入頁 UI 套用設計規範 design-tokens.css 完整套用

## 對應需求規格

G1 通過版本：作為使用後台的管理者，登入頁視覺符合 `docs/design-system.md`
定義的規範，以便後台介面呈現一致、專業的視覺風格。驗收條件（Gherkin，共
6 條）：

1. `LoginPage.tsx`/`LoginPage.css` 所有計算後樣式皆來自
   `design-tokens.css` 變數；submit 按鈕套用 §7 primary 樣式（黑底白字、
   無/極小圓角）。
2. 間距、字級階層、欄位版面依 `design-system.md` §3/§4 scale 套用；
   label 位於欄位上方、靠左對齊。
3. 必填欄位（帳號、密碼）以**文字**標示必填（非僅用顏色）。
4. 錯誤訊息（`role="alert"`）樣式為紅字 + 圖示，不能只靠邊框變色；
   確切紅色值為 §1 例外條款允許的例外色，由本文件（architect）決定並記錄。
5. 表單無障礙基本要求（§8）：label 齊全、focus 樣式可見（不可
   `outline: none` 卻無替代樣式）。
6. 既有測試 `LoginPage.test.tsx`、`tests/e2e/test_design_tokens_e2e.py`
   須維持通過。

範圍外（已定案，不重新討論）：表單驗證/登入行為邏輯變更；系統化 Button
元件抽象；secondary/danger 按鈕變體（本頁僅一顆 primary submit 按鈕）。

依賴：SDLCAIP1-30 已建立 `frontend/src/styles/design-tokens.css` 機制並
於 `LoginPage` 做最小套用（標題、表單 padding、按鈕 padding）；本票在此
基礎上把同一頁面的其餘元素（欄位、label、必填標示、錯誤訊息、focus
樣式、按鈕完整樣式）補齊到規範要求的完整程度。`docs/design-system.md`
仍是色彩/字體/間距數值的權威來源，本票不重新定義任何 token 數值。

## 介面/API 契約

無。本票純粹是 `frontend/src/pages/LoginPage.tsx` 的 JSX 標記調整與
`frontend/src/pages/LoginPage.css` 的樣式規則擴充，不新增/變更任何對外
HTTP API、不觸碰 `src/cms_aipilot` 後端任何 router 或 handler；登入
request/response 格式（`login()` API 呼叫、401/429/其他錯誤處理邏輯）
維持原樣，明確排除於本票範圍外。

## 資料模型

無新增資料模型。本票不涉及 DynamoDB 或任何後端儲存層。

## 關鍵技術決策

- **錯誤訊息紅色值定為 `#B00020`，新增為 `frontend/src/styles/
  design-tokens.css` 的 `--color-error` 變數（僅前端該份檔案，不同步至
  後端 `src/cms_aipilot/static/design-tokens.css`）**：codebase 目前無
  任何既有 danger/error 紅色 precedent（已 grep `frontend/src` 確認），
  需新選一個值。`#B00020` 是業界（Material Design）已驗證的 error 紅，
  對 `#FFFFFF` 背景實測對比度約 7.3:1，遠超 §8/§1 要求的 WCAG AA 4.5:1
  （一般文字），亦達 AAA 7:1 門檻，比隨意挑選的紅色更安全、且是有出處可查
  的既有業界慣例值，減少「architect 憑感覺挑色」的疑慮。`design-system.md`
  §1 明訂 `--color-accent` 為「無」是核心風格特徵，但同一節也明訂例外
  條款——「若未來某個 Story 真的需要功能色（例如表單錯誤提示），視為例外
  並在該 Story 的設計文件中明確說明，不要回頭改這份全域規範」；本票的
  錯誤訊息紅色正是該條款預期的例外情境，故在此設計文件中明確決定新增此
  token，不回頭修改 `docs/design-system.md` §1 的色彩表。**採用共用 CSS
  變數（而非寫死字面值）**：與 SDLCAIP1-33（同批次、同時 Designing 的
  「文章表單套用設計規範」story）各自獨立分析後得出完全相同的
  `#B00020` 數值，顯示這是同一份規範下的收斂結果而非巧合；orchestrator
  複核兩份設計文件後統一採用「新增共用 `--color-error` token」的作法
  （而非各自在元件 CSS 內寫死字面值），因為 `design-tokens.css` 存在的
  目的就是讓多個頁面共用同一組視覺數值來源——兩個頁面各自寫死同一個字面
  色碼，會重新製造 `design-tokens.css` 原本要消除的「數值重複、未來要
  改色時得改兩處」問題，與 SDLCAIP1-30 建立此機制的初衷相悖。故本票不
  重新定義變數，直接消費 SDLCAIP1-33 設計文件已決定新增的
  `--color-error` token；只限前端檔案（後端目前產生的靜態頁沒有表單/
  錯誤提示畫面，不需要此 token，故不同步至後端檔案，此點與 SDLCAIP1-30
  「兩檔案內容須逐位元組相同」的決策不衝突——該決策針對的是 §1-5 全域
  基礎 token 集合，本 token 屬於文件自身允許的「功能色例外」）。

- **錯誤圖示用 CSS `::before` 偽元素 + unicode 字符（`"⚠"`,
  U+26A0），不用 SVG 或圖示庫**：`frontend/package.json` 目前無任何圖示
  依賴（已確認），引入圖示庫（如 lucide-react）超出本票「僅套用既有
  design-tokens 機制」的範圍，也違反 CONSTITUTION 之外沒有既有前例；
  inline SVG 需要額外標記且會被 `toHaveTextContent` 的文字比對意外影響
  （SVG 若含 `<title>` 或文字節點可能污染 accessible text）。CSS
  生成內容（`::before { content: "⚠ "; }`）不進入 DOM
  `textContent`／React 測試庫的 `toHaveTextContent` 比對範圍，因此
  `LoginPage.test.tsx` 既有的
  `expect(screen.getByRole("alert")).toHaveTextContent("帳號或密碼錯誤")`
  等斷言不受影響（比對訊息文字本身，圖示是純視覺附加，不出現在
  比對字串中）——這是滿足 AC4 又不破壞 AC6 既有測試的關鍵理由。

- **必填標示以「欄位群組內、`<label>` 元素之外」的獨立文字節點呈現，
  透過 `aria-describedby` 與對應 `<input>` 關聯，不寫進 `<label>`
  本身的文字內容**：`LoginPage.test.tsx` 既有斷言使用
  `screen.getByLabelText("帳號")`／`getByLabelText("密碼")`
  （精確字串比對，見 `fillAndSubmit()`）。Testing Library 的
  `getByLabelText` 預設對 `<label>` 文字做**完全比對**；若把必填文字
  （如「（必填）」）直接附加進 `<label>` 內部（例如
  `<label>帳號（必填）</label>`），會讓 label 的文字內容變成
  `"帳號（必填）"`，導致 `getByLabelText("帳號")` 精確比對失敗、
  違反 AC6「既有測試不受影響」的硬性要求。因此必填標示改放在
  `<label>` 之後、`<input>` 之前的獨立 `<span>`（例如
  `<span id="username-required" className="login-page__required">必填</span>`），
  `<input>` 加上 `aria-describedby="username-required"`：
  - `<label>` 文字維持原樣 `"帳號"`/`"密碼"`，`getByLabelText` 精確比對
    不受影響（AC6 過關）。
  - 必填標示是可見的獨立文字（非僅顏色），滿足 AC3 與 §7「必填以文字
    標示,非僅用顏色」。
  - 透過 `aria-describedby` 讓螢幕報讀器在讀出欄位時一併讀出必填說明，
    滿足 §8 無障礙要求，比單純視覺文字更完整。

- **Focus 樣式：`:focus-visible { outline: 2px solid
  var(--color-text-primary); outline-offset: 2px; }`，套用於
  `input`、`.login-page__submit`，不使用 `outline: none`**：選
  `:focus-visible`（非 `:focus`）避免滑鼠點擊也顯示外框造成視覺雜訊，
  同時保證鍵盤導覽時外框一定可見，符合 §8「可鍵盤操作的 focus 樣式
  必須可見」的字面要求。顏色沿用既有 `--color-text-primary`
  （`#111111`，本站唯一的「黑」token）而非導入新顏色，維持全站黑白
  極簡調性（§0）、不新增例外色；`outline-offset: 2px` 避免外框與欄位
  邊框重疊難以辨識。

- **Submit 按鈕完整樣式（§7 primary 按鈕規則的具體數值）**：

  ```css
  .login-page__submit {
    background-color: var(--color-text-primary); /* 視為本站「黑」 */
    color: var(--color-bg); /* 白字 */
    border: none;
    border-radius: 2px; /* 極小圓角，符合「無/極小圓角」方正調性 */
    font-family: var(--font-family-base);
    font-size: var(--font-size-body);
    padding: var(--space-2) var(--space-4); /* 沿用 SDLCAIP1-30 既有值，e2e 已鎖定 8px 16px */
    cursor: pointer;
  }
  .login-page__submit:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
  ```

  `--color-text-primary`（`#111111`）而非硬寫 `#000000`：本站 tokens
  未定義純黑，`#111111` 已是全站唯一代表「黑」的 token（標題已用同一
  變數），沿用它比新增一個 `#000000` 常數更一致，視覺上與 AC1 要求的
  「black bg」在人眼判讀上無可感知差異。`padding` 維持 SDLCAIP1-30
  既有值不變，因 `tests/e2e/test_design_tokens_e2e.py` 的
  `test_login_submit_button_uses_design_token_spacing` 已鎖定
  `"8px 16px"`，變更會直接破壞 AC6。

- **欄位版面與間距（AC2 具體套用）**：

  ```css
  .login-page__field {
    display: flex;
    flex-direction: column;
    align-items: flex-start; /* label/input 左對齊 */
    gap: var(--space-1);
    margin-bottom: var(--space-4);
  }
  .login-page__field label {
    font-family: var(--font-family-base);
    font-size: var(--font-size-body);
    font-weight: var(--font-weight-body);
    color: var(--color-text-primary);
  }
  .login-page__field input {
    font-family: var(--font-family-base);
    font-size: var(--font-size-body);
    padding: var(--space-2);
    border: 1px solid var(--color-border);
    border-radius: 2px;
    width: 100%;
    box-sizing: border-box;
  }
  .login-page__required {
    font-size: var(--font-size-meta);
    color: var(--color-text-secondary);
  }
  ```

  `LoginPage.tsx` 現有欄位包裹用無語意的 `<div>`（見既有程式碼第
  50、61 行），改為 `<div className="login-page__field">`——只加
  `className`，不動既有 `id`/`htmlFor`/欄位結構，符合 SDLCAIP1-30
  已定案「不改變既有測試選取器」的原則延續。`gap: var(--space-1)`
  （4px）用於 label 與 input 之間的小間距、`margin-bottom:
  var(--space-4)`（16px）用於欄位群組之間的間距——依 §4 間距 scale
  取值，不寫魔術數字，欄位內小間距用 scale 最小值、欄位間大間距用
  已在 `.login-page__form` 沿用的 `--space-4`，保持同一頁面間距語彙
  一致。

- **錯誤訊息樣式（AC4 完整套用）**：

  ```css
  .login-page__error {
    color: var(--color-error);
    font-family: var(--font-family-base);
    font-size: var(--font-size-body);
    margin-top: var(--space-2);
  }
  .login-page__error::before {
    content: "⚠ ";
  }
  ```

  `<p role="alert" className="login-page__error">{error}</p>`——僅加
  `className`，`role="alert"` 與既有文字內容不變，`getByRole("alert")`
  與 `toHaveTextContent` 既有斷言不受影響。

- **`design-tokens.css` import 與元件結構不變**：`LoginPage.tsx` 已在
  SDLCAIP1-30 引入 `import "../styles/design-tokens.css"` 與
  `import "./LoginPage.css"`，本票沿用同一機制，僅擴充 `LoginPage.css`
  規則與 `LoginPage.tsx` 內的 `className`/`aria-describedby` 標記，
  不新增第二個 CSS 檔案、不改變既有 import 結構。

## 開放設計問題（定稿時必須為空）

無。
