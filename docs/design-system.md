# UI / 設計規範（Design System）— CMS AI Pilot

<!--
本文件是視覺規範的權威來源。CONSTITUTION.md 的「視覺設計」段落只放一句
指標指向這裡，不重複內容——細節規格改這裡，CONSTITUTION.md 不用跟著動。
architect / developer / reviewer 在涉及畫面的 Story 中應讀取本文件。
-->

## 0. 風格定位

黑白極簡、編輯感（editorial）風格。參考基準：Squarespace 部落格範本
「Cassidy Harman」demo（置中排版、無強調色、大量留白、用字級大小做視覺
層次而非用顏色或邊框）。已依中文內容的實際限制做兩處調整：

1. **不用襯線體**——原參考大量使用西式高對比襯線字，中文沒有對應字重可
   用，改為全站統一無襯線體。
2. **內文靠左，標題／meta 維持置中**——原參考內文也置中，但中文長段落
   置中不利閱讀，只保留標題/日期/meta 這些短文字置中，段落內文改靠左。

## 1. 色彩系統

| Token | 值 | 用途 |
|---|---|---|
| `--color-bg` | `#FFFFFF` | 頁面背景 |
| `--color-text-primary` | `#111111` | 標題、內文主要文字 |
| `--color-text-secondary` | `#111111` | meta 資訊（日期等）；**不做灰階分層，層次靠字級大小，不靠顏色深淺** |
| `--color-border` | `#E5E5E5` | 僅用於底線（nav 當前項、連結底線），不用於卡片外框或色塊分隔 |
| `--color-accent` | 無 | 本風格核心特徵：不設強調色。若未來某個 Story 真的需要功能色（例如表單錯誤提示），視為例外並在該 Story 的設計文件中明確說明，不要回頭改這份全域規範 |

對比度要求：`--color-text-primary` on `--color-bg` 需符合 WCAG AA（4.5:1）——`#111111` on `#FFFFFF` 實測遠高於此標準。

## 2. 字體

全站標題與內文使用同一套無襯線字體堆疊，不額外載入 web font（前台是無建置流程的靜態頁，維持载入效能）：

```css
font-family: -apple-system, BlinkMacSystemFont, "PingFang TC", "Noto Sans TC", sans-serif;
```

## 3. 字級與字重階層

| 層級 | 用途 | font-size | line-height | font-weight |
|---|---|---|---|---|
| Display | 網站/頁面主標題（如首頁站名） | `2.5rem`（40px） | 1.3 | 400 |
| H1 | 文章標題、頁面標題 | `2rem`（32px） | 1.35 | 600 |
| H2 | 區塊標題 | `1.5rem`（24px） | 1.4 | 600 |
| Body | 內文段落 | `1rem`（16px） | 1.7（中文行高偏寬鬆） | 400 |
| Meta | 日期、輔助資訊 | `0.875rem`（14px） | 1.5 | 400 |
| Nav | 導覽列連結 | `0.9375rem`（15px） | 1.5 | 400 |

## 4. 間距 Scale

固定倍數，所有 padding/margin/gap 只能取用以下值，不寫魔術數字：

`4px / 8px / 12px / 16px / 24px / 32px / 48px / 64px`

大留白區塊（如標題上方留白）取 `48px` 或 `64px`，比照參考截圖的大量留白特徵。

## 5. RWD 斷點

沿用既有程式碼（`src/cms_aipilot/main.py` `_ARTICLE_PAGE_STYLE`）已經在用、且已被 list/search 頁共用的斷點，不重新發明：

| 範圍 | 行為 |
|---|---|
| `< 768px`（手機，隱含 base） | 預設樣式 |
| `768px – 1024px`（平板） | `padding: 24px`；標題字級縮小一階 |
| `≥ 1025px`（桌機） | `padding: 32px`；內容 `max-width: 800px` 置中 |

後台（`frontend/`）僅桌機版，不需要手機/平板斷點（Epic SDLCAIP1-3 描述已明訂）。

## 6. 對齊規則

- **置中**：頁面/文章標題、日期、meta 資訊、導覽列
- **靠左**：內文段落（含文章正文、表單說明文字）

## 7. 元件規則

| 元件 | 規則 |
|---|---|
| 連結 | 底線樣式（比照參考截圖 "Read More"、nav 當前項），不用色塊或按鈕感包裝一般文字連結 |
| 按鈕（後台表單操作用，前台目前無按鈕元件） | primary/secondary/danger 三種變體；黑底白字 / 白底黑框 / 紅色系分別對應，無圓角或極小圓角（比照整體方正極簡調性） |
| 表單欄位 | label 置於欄位上方靠左；必填以文字標示（非僅用顏色，避免色盲使用者看不出必填標示）；錯誤訊息文字紅色 + 圖示，不能只靠邊框變色 |
| 卡片/列表項（文章列表、搜尋結果） | **不用邊框、陰影、背景色塊**；用間距 scale 的留白本身分隔項目，比照參考截圖的三欄式列表 |
| 導覽列 | 極簡，文字連結為主，字級明顯小於標題，退居次要視覺角色 |

## 8. 無障礙基本要求

- 色彩對比 AA 等級（見 §1）
- 所有表單欄位有對應 `<label>`
- 可鍵盤操作的 focus 樣式必須可見（不可用 `outline: none` 卻不提供替代樣式）
- 必填欄位標示不能只靠顏色（見 §7 表單欄位規則）

## 9. 技術落地方式

單一 CSS 自訂屬性檔案 `design-tokens.css` 作為唯一事實來源，只放 `:root` 變數，不含元件樣式：

- 前台（`src/cms_aipilot/main.py` 目前用 Python 字串常數組 `<style>` 內嵌樣式，無共用檔案）：`design-tokens.css` 原樣複製上傳到 S3，靜態頁 `<link>` 引用，路徑慣例待 architect 在對應 Story 的 Designing 階段決定（比照現有 `articles/`、`search/` 前綴目錄慣例）。
- 後台（`frontend/`，Vite+React）：`design-tokens.css` 放入 `frontend/src/styles/`，由元件樣式 `import` 使用。

**注意：目前前台完全沒有共用 CSS 檔案的機制（現況是各頁各自的 Python 字串樣式常數）**，建立 `design-tokens.css` 本身必須是第一張基礎建設性質的 Story，其餘 UI 優化 Story 依賴它才能真正共用同一套視覺語言，而不是各自重新寫一份數值。

## 10. 套用範圍策略

不強制一次重構所有既有頁面。新規範套用在新 Story；既有頁面等各自被下一輪 Story 觸碰到時再套用，避免開一張規模過大、卡在拆分規則（docs/02 §6）的「重構全站 UI」巨型 Story。
