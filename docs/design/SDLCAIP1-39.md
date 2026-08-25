# 設計文件 — SDLCAIP1-39 後台文章列表頁缺少「新增文章」入口

## 對應需求規格

G1 通過版本：作為後台唯一管理者，我希望在文章列表頁（`ArticlesList.tsx`）
上看到「新增文章」的按鈕或連結，不需手動輸入 `/articles/new` 網址即可開始
新增文章。驗收條件（Gherkin，共 4 條）：

1. 列表頁渲染完成後，畫面上有一個文字清楚可辨識（如「新增文章」）的
   按鈕或連結。
2. 點擊該入口導向 `/articles/new`，顯示空白的新增文章表單。
3. 空列表狀態（顯示「尚無文章」）下，入口依然可見可點擊，不因空列表
   分支而消失。
4. 既有 `ArticlesList` 相關測試於新增此入口後執行 `npm run test` 仍全數
   通過。

範圍外（已定案）：不含新增文章表單本身的欄位/驗證/送出行為變更；不含
按鈕樣式的系統化元件抽象化（沿用既有 `.articles-list__button` class）；
不含列表頁其餘版面重新設計。

依賴：無。

## 介面/API 契約

無。本票純屬前端 `ArticlesList.tsx` 新增一個導向既有路由的 `<Link>`，
不新增/變更任何對外 HTTP 端點，也不呼叫任何新的 API 函式。`/articles/new`
路由與 `ArticleForm.tsx` 表單既已存在（見 spec 情境說明），此連結只是
補上畫面入口。

## 資料模型

無新增資料模型。本票只觸碰 `frontend/src/pages/ArticlesList.tsx`
（JSX 新增一個連結）與 `frontend/src/pages/ArticlesList.css`（新增一條
版面間距規則），皆為前端原始碼檔案，不涉及任何後端資料表/欄位/索引。

## 關鍵技術決策

- **在 `error` 判斷之後、`articles.length === 0`（空狀態）判斷之前插入
  共用的「新增文章」`<Link>`，讓空狀態分支與正常列表分支共用同一段
  JSX，而非在兩個 return 分支各自複製一次**：目前 `ArticlesList.tsx`
  有三個提早 return 的分支（`error` → `<p role="alert">`；
  `articles.length === 0` → 空狀態 `<div>`；否則 → 表格）。AC3 要求空
  列表狀態下入口仍需可見。若把入口寫在表格版面的 `<div>` 內，空狀態分支
  不會渲染到它。因此把「新增文章」`<Link>` 提升到 `error` 檢查之後、
  空狀態判斷之前，包成一個共用區塊，兩個分支都會渲染到同一個
  `<Link>` 元素，不需複製 JSX 兩份，也避免未來兩份的視覺一致性漂移。
  （`error` 分支本身仍維持提早 return 不含入口——spec 未要求錯誤畫面
  也要有新增入口，且錯誤時列表尚未確定載入成功，不擴大範圍。）

- **重用既有 `to={ARTICLE_NEW_PATH}` 常數與
  `articles-list__button articles-list__button--secondary` class，
  不新增新 CSS class 或新按鈕變體**：`frontend/src/routes.ts` 已定義
  `ARTICLE_NEW_PATH = "/articles/new"`（目前未被任何檔案消費），直接
  import 使用，避免路徑字串重複硬編碼。樣式比照既有「編輯」連結
  （同樣是 `<Link>` 而非 `<button>`，功能上是操作按鈕）套用
  `articles-list__button--secondary`（SDLCAIP1-32 已定義：白底黑框，
  `text-decoration: none`），不是 `--danger`（非破壞性操作）也不需要
  新增 `--primary` 變體（spec 範圍外聲明已排除元件抽象化，且頁面上
  目前沒有其他 primary 按鈕可比照，不預先設計未被要求的變體）。

- **新增一個外層 `<div className="articles-list__toolbar">` 包住此
  `<Link>`，置於列表/空狀態內容之上**：目的只是讓連結與下方表格/空狀態
  文字之間有基本間距（沿用 `--space-3`，與 SDLCAIP1-32 表格列間距同一
  量級），不是新增版面元件系統；沒有這層 wrapper，連結會直接貼著表格
  或空狀態文字，觀感上不像獨立可點擊的入口。CSS 僅一條規則：
  ```css
  .articles-list__toolbar {
    margin-bottom: var(--space-3);
  }
  ```

## 開放設計問題（定稿時必須為空）

無。
