# CMS AI Pilot — 產品需求文件(PRD)

> 本文件由 reporter agent 隨開發過程自動維護,不是預先寫好的規格——每張 Story
> 的 G1(需求核准)通過後,orchestrator 會委派 reporter 把該 Story 定稿的需求
> 規格加進本文件。內容必須逐字可追溯到 G1 通過當下的規格,不做摘要或改寫。
> 章節標記「(implemented)」代表對應 Story 已到 Done;沒有標記代表需求已核准、
> 尚未實作完成。

## Epic 概述

一套具備前後台的 CMS。後台為單一管理者使用的表單式介面,可新增/編輯/刪除文章
(標題、純文字內文、發布時間,無分類、無草稿狀態);每次異動發布後,系統產生對應的
全靜態 HTML 並上傳覆蓋 AWS S3。前台是純靜態網站,不查資料庫,包含首頁文章列表
(靜態分頁)、文章詳細頁、前端靜態索引搜尋,響應式適配手機/平板/桌機。後台僅需
桌機版,採單一帳號密碼登入(存 Secrets Manager 或 SSM SecureString),簽發
JWT/session token,具登入失敗次數限制。

對應 Jira Epic:SDLCAIP1-3

## SDLCAIP1-9 — 文章刪除後移除對應靜態頁

**使用者故事:** 身為 CMS 使用者,刪除文章後應移除其對應的 S3 靜態詳細頁。

**關鍵行為:**
- 當 DELETE /articles/{id} 成功執行(per SDLCAIP1-7),S3 物件 `articles/{id}.html` 同步刪除
- S3 刪除失敗時僅記錄日誌,不改變 API 回應(204/404)(同 SDLCAIP1-8 錯誤處理策略)

**重要範圍說明:**
- 本票原標題提及「更新列表頁靜態輸出」,但該部分已明確 scope out,因無票建立首頁列表靜態生成機制(另有 SDLCAIP1-15 追蹤,仍需精細化)
- 本票僅交付詳細頁 S3 物件移除,首頁列表更新為後續票據,待 SDLCAIP1-15 完成後處理

**不在此範圍:**
- 首頁列表頁面更新
- S3 失敗重試/回滾機制
- 超出 SDLCAIP1-7 既有 404 行為的冪等性變更
- CDN 快取失效

## SDLCAIP1-10 — 後台登入(帳密、JWT、登入失敗次數限制)

**使用者故事:** 身為單一後台管理者,以使用者名稱/密碼登入並取得 JWT 令牌,用於存取受保護的文章管理 API。

**關鍵行為與決策:**
- **JWT 簽發:** POST /login 端點簽發 JWT (演算法 HS256,過期時間 8 小時,payload 包含 sub/iat/exp)
- **認證儲存:** 認證資訊存於 AWS SSM Parameter Store SecureString(相比 Secrets Manager,單一認證集無需輪換,成本更低)
- **登入鎖定:** 連續 5 次登入失敗鎖定帳戶 15 分鐘,期間回傳 429 回應
- **上游消費:** 提供令牌驗證函式供 SDLCAIP1-11 使用

**不在此範圍:**
- 實際保護 /articles 端點(SDLCAIP1-11 的職責)
- 登出/令牌撤銷
- 多使用者/角色型存取控制(RBAC)
- 密碼重設
- 刷新令牌
- 速率限制/WAF 基礎設施

## SDLCAIP1-11 — 後台文章 API 掛上認證保護

**使用者故事:** 身為系統,所有後台文章 API 端點(列表、詳細、新增、編輯、刪除)均需有效 JWT 方可存取,確保僅管理者可使用。

**關鍵行為與決策:**
- **保護範圍:** 將 SDLCAIP1-10 的 JWT 驗證作為 FastAPI 依賴應用於全 5 個現存文章端點(POST/PUT/DELETE/GET list/GET detail)
- **包含 GET 端點:** 因無合法的匿名/前端呼叫者(前台為純靜態網站,不查詢資料庫)
- **失效回應:** 缺失/無效/逾期令牌回傳 401
- **業務邏輯保持不變:** 現有端點成功路徑的回應結構和商業邏輯保持原樣

**不在此範圍:**
- 修改 SDLCAIP1-10 的登入/令牌簽發邏輯
- 前端/UI 變更
- 刷新令牌
- 登出機制
- 角色型存取控制(RBAC)
- 速率限制

## SDLCAIP1-13 — 後台新增/編輯文章表單

**使用者故事:** As the sole CMS admin, I want a form where I can create a new article or edit an existing one (title, plain-text content, publish date/time), so that I can publish and update content on the site without calling the API manually.

**驗收條件 (Gherkin, 12 scenarios):**
- 開啟新增表單欄位為空
- 開啟編輯表單欄位預先填入既有文章資料（GET /articles/{id} 200）
- 開啟編輯表單但文章已不存在（GET /articles/{id} 404，顯示找不到文章、不顯示表單）
- 成功建立新文章（POST /articles，201 後導向列表頁）
- 成功編輯既有文章（PUT /articles/{id}，200 後導向列表頁）
- 驗證錯誤—標題為空（前端擋，不導向，保留其他欄位）
- 驗證錯誤—內容為空（同上）
- 驗證錯誤—後端回傳422（顯示通用錯誤訊息，不導向）
- 儲存失敗—靜態頁上傳失敗502（既有後端行為：PUT 情境下該文章已被後端整筆刪除作為回滾；前端須顯示明確失敗訊息，不得宣稱已儲存成功，不導向）
- 送出表單時token已失效401（前端清除token並導向登入頁）
- 取消編輯返回列表頁（不呼叫API）

**範圍外:** 分類/標籤/草稿狀態欄位（Epic 明定無）; 富文本編輯器（content為純文字）; 圖片/附件上傳; 表單自動儲存草稿/離開頁面二次確認彈窗; 文章列表頁本身（SDLCAIP1-19）、刪除確認互動（SDLCAIP1-14）、搜尋/篩選（SDLCAIP1-16）; 後端API契約變更（不重新設計，純消費既有API）; 手機/平板響應式版面; 401全域攔截器的實作位置（技術決策，留給developer）。

**依賴:** SDLCAIP1-18（前端骨架/API client/認證慣例，已Done）; SDLCAIP1-19（文章列表頁提供新增/編輯入口，目前Designing階段，路由尚未定稿，本票表單本身可獨立開發測試）; 外部依賴既有後端API POST/PUT /articles、GET /articles/{id}（SDLCAIP1-4/6/8，已Done）。

## SDLCAIP1-18 — 後台前端骨架與登入頁

**使用者故事:** As the sole CMS admin, I want a login form where I enter my username/password to obtain a session, so that I can subsequently access protected backend pages without manually calling the API.

**關鍵行為與決策:**
- 這是專案第一個涉及後台 UI 的 Story，需從零建立 React+Vite 前端骨架（project-profile.yaml 註記骨架尚未建立）
- 登入表單呼叫既有 POST /login（SDLCAIP1-10）取得 JWT，成功後儲存 token 並導向文章列表頁
- 帳密錯誤（401）顯示錯誤訊息、不儲存 token；帳戶鎖定（429）顯示鎖定提示
- 受保護路由機制：未偵測到已儲存 token 時導向登入頁，不發出該頁面的 API 請求
- 已登入的 API 呼叫一律帶上 `Authorization: Bearer <token>` header
- Token 儲存機制（localStorage vs sessionStorage）留給 developer 技術判斷，非需求歧義

**不在此範圍:**
- 文章列表頁本身內容（另立工單 SDLCAIP1-19）
- 新增/編輯文章表單（SDLCAIP1-13）
- 刪除確認互動（SDLCAIP1-14）
- 搜尋/篩選（SDLCAIP1-16）
- 登出、Token 刷新、記住我
- 密碼重設 UI
- 手機/平板響應式版面（Epic 明定後台僅需桌機版）

## SDLCAIP1-19 — 後台文章列表頁(桌機版)

**使用者故事:** As the sole CMS admin, I want to see a desktop list of my articles (title, published date) with pagination, so that I can review existing content and reach the edit/delete actions for a specific article.

**驗收條件 (Gherkin, 5 scenarios):**
- 有資料時列表正常呈現（依 API 順序顯示標題與 published_at）
- 空列表狀態（total=0 顯示「尚無文章」空狀態訊息，不顯示表格列）
- 未帶有效 token 導向登入頁（401 時依 RequireAuth 機制導向登入頁，不顯示文章資料）
- 分頁行為與 API 回傳一致（page/page_size=10，點擊下一頁改用 page=2 呼叫 GET /articles）
- 每列提供編輯/刪除入口（實際導覽與行為由 SDLCAIP1-13、SDLCAIP1-14 實作，本故事僅需入口存在）

**範圍外:** 登入頁與前端骨架本身（SDLCAIP1-18）; 新增/編輯文章表單內容與送出邏輯（SDLCAIP1-13）; 刪除確認互動與實際刪除呼叫（SDLCAIP1-14）; 搜尋/篩選（SDLCAIP1-16）; 手機/平板響應式版面; 內文摘要/snippet 顯示（GET /articles 僅回傳 ArticleSummary，不含 content）; 依欄位排序、批量操作、即時更新。

**依賴:** blocked by SDLCAIP1-18（已 Done）; 外部依賴 GET /articles（SDLCAIP1-5，已 Done，含 JWT 保護 SDLCAIP1-11）。

## SDLCAIP1-14 — 後台刪除確認互動

**使用者故事:** As a 後台唯一管理者, I want 在文章列表點擊「刪除」後先看到明確的確認步驟才真正送出刪除, so that 我不會因誤觸而意外刪除已發布的文章。

**驗收條件 (Gherkin, 6 scenarios):**
- 確認後成功刪除文章 — 點擊刪除→確認刪除→呼叫 DELETE /articles/{id}→204→文章自列表移除，其餘不變
- 取消確認不會刪除文章 — 點擊刪除→取消→不呼叫 API，文章仍在列表
- 刪除已不存在的文章（404）— 確認刪除→404→視為已不存在，從列表移除，顯示非阻斷提示
- 刪除時未登入或憑證過期（401）— 確認刪除→401→呼叫既有 useHandleUnauthorized 清除 token→導向登入頁
- 資料庫刪除成功但靜態頁清除失敗（502, error_code=STATIC_PAGE_DELETION_FAILED）— 視為已刪除，從列表移除，顯示非阻斷警示
- 非預期錯誤（其他 5xx/網路例外）— 不移除文章，顯示通用錯誤訊息，可重試

**範圍外:** 確認 UI 元件形式（原生 confirm() vs 自訂 Modal，留給開發階段決定）; 批量刪除; 刪除復原(undo); 訊息文案樣式設計; 刪除造成分頁狀態調整; ArticlesList.tsx 以外頁面的刪除入口; 編輯功能(SDLCAIP1-13); 後端 DELETE 端點行為變更(已完成)。

**依賴:** blocked by SDLCAIP1-19（已 Done，合併至 main，提供 data-testid="delete-article-{id}" 按鈕與 useHandleUnauthorized hook）; blocked by SDLCAIP1-7、SDLCAIP1-9（皆已 Done）。

## SDLCAIP1-20 — 前台文章詳細頁靜態輸出(含響應式版面)

**使用者故事:** As a 網站訪客, I want 開啟文章詳細頁能看到完整標題、內容與發布時間，且版面在手機/平板/桌機都正常顯示, so that 我能在任何裝置上舒適閱讀文章內容。

**驗收條件 (Gherkin):**

```gherkin
Scenario: 文章詳細頁顯示完整內容
  Given 一篇已發布的文章（標題、純文字內文、發布時間）
  When 靜態頁面產生後於瀏覽器開啟該文章的靜態頁
  Then 頁面顯示文章標題、內文全文、發布時間
```

```gherkin
Scenario: 手機寬度版面正常顯示
  Given 文章詳細頁已產生
  When 以手機寬度（<768px）檢視頁面
  Then 內容單欄顯示、無橫向捲動、文字可讀不溢出
```

```gherkin
Scenario: 平板寬度版面正常顯示
  Given 文章詳細頁已產生
  When 以平板寬度（768px–1024px）檢視頁面
  Then 版面依平板寬度調整、無橫向捲動
```

```gherkin
Scenario: 桌機寬度版面正常顯示
  Given 文章詳細頁已產生
  When 以桌機寬度（>1024px）檢視頁面
  Then 版面套用桌機排版（如內容最大寬度限制、置中）、無橫向捲動
```

```gherkin
Scenario: 文章內容含特殊字元時正確逸出
  Given 文章標題或內文含 HTML 特殊字元（如 <, &, "）
  When 靜態頁面產生
  Then 輸出的 HTML 已正確逸出，不造成標籤注入
```

**不在此範圍:**
- 首頁文章列表與分頁（另立工單處理）
- 前端搜尋功能（SDLCAIP1-16，獨立工單）
- 已刪除/不存在文章的「找不到」自訂頁面設計（屬列表頁工單範圍；本工單僅負責「存在文章」的正常渲染）
- 後台管理 UI（frontend/ SPA，屬 SDLCAIP1-13/14/18/19 範圍）
- SEO meta（OG tag、sitemap 等）未在 Epic 中提及，不做

**依賴:** 工單依賴：SDLCAIP1-8（既有的產生/上傳觸發邏輯，本工單只改動 `_generate_and_upload_static_page` 產出的 HTML 內容與樣式，不改動觸發時機）; 外部依賴：AWS S3（既有 bucket，`ARTICLES_STATIC_BUCKET_NAME`）。

## SDLCAIP1-23 — 首頁文章列表靜態頁產生（新增文章觸發）

**使用者故事:** As a 網站訪客, I want 在有人發布新文章後，首頁文章列表（含分頁）能反映最新內容, so that 我能瀏覽到最新發布的文章。

**驗收條件 (Gherkin):**
1. 新增文章後，第一頁列表以 published_at 由新到舊排序（呼叫 create_article 後，首頁第一頁靜態 HTML 重新產生上傳至 S3，新文章出現在最前面）
2. 文章總數超過一頁篇數時，產生對應頁數的靜態頁面（每頁只含屬於該頁範圍的文章）
3. 新增第一篇文章時，由空狀態轉為有內容的列表頁
4. 靜態列表頁上傳失敗時，比照現有 rollback 慣例回報錯誤（API 回傳既有 502 STATIC_PAGE_GENERATION_FAILED 類型錯誤，DynamoDB 寫入依現有 rollback 邏輯處理）

**不在此範圍:**
- 文章更新（update_article）與刪除（delete_article）觸發的列表頁重新產生 —— 另立子工單（SDLCAIP1-24）處理
- 文章詳細頁本身的渲染與響應式 —— SDLCAIP1-20
- 前端靜態索引搜尋 —— SDLCAIP1-16
- 分類/標籤功能
- 後台管理 UI
- 分頁連結的具體 URL / 檔名命名規則 —— 交由 G1b 設計階段決定
- 舊分頁數量因文章減少而需清理的邏輯 —— 不適用於本 story
- 列表頁視覺樣式細節 —— 沿用 SDLCAIP1-20 既有共用版型慣例

**依賴:** SDLCAIP1-8、SDLCAIP1-9（既有模式參考）、SDLCAIP1-20（共用版型）；為姊妹工單 SDLCAIP1-24 提供共用分頁產生邏輯的基礎。架構決策依據：HUMAN-INPUT SDLCAIP1-22，人類已核准選項 A（異動時於後端觸發點重新產生）。

## SDLCAIP1-24 — 首頁文章列表靜態頁重新產生（更新／刪除文章觸發）

**使用者故事:** As a 網站訪客, I want 文章被更新或刪除後，首頁文章列表（含分頁）能同步反映異動, so that 我看到的列表內容與後台實際文章狀態一致。

**驗收條件 (Gherkin):**
1. 更新文章的 published_at 後，列表排序即時反映新順序（受影響分頁重新產生並上傳）
2. 刪除文章後，列表頁不再顯示該文章（對應分頁重新產生）
3. 刪除最後一篇文章後，列表頁回到空狀態
4. 更新或刪除觸發的列表頁上傳失敗時，比照現有錯誤處理慣例回報（與 SDLCAIP1-9 一致的 502/STATIC_PAGE_*_FAILED 類型錯誤）

**不在此範圍:**
- 文章新增（create_article）觸發的列表頁產生與核心分頁產生邏輯本身 —— 已由姊妹工單 SDLCAIP1-23 提供，本 story 僅重用
- 文章詳細頁渲染與響應式 —— SDLCAIP1-20
- 前端靜態索引搜尋 —— SDLCAIP1-16
- 分類/標籤功能
- 後台管理 UI
- 因文章總數減少導致「多餘舊分頁」的清理策略 —— 留給 G1b 設計階段決定
- 列表頁視覺樣式細節 —— 沿用 SDLCAIP1-20 既有共用版型慣例

**依賴:** blocked by SDLCAIP1-23（需其提供的共用分頁產生函式，需 SDLCAIP1-23 先 Done 並合併，本票才能開始開發；G1/G1b 審查可與 SDLCAIP1-23 並行）、SDLCAIP1-9（既有 update/delete 觸發慣例）、SDLCAIP1-20（共用版型）。架構決策依據：HUMAN-INPUT SDLCAIP1-22，人類已核准選項 A。

## 待補(reporter 下次執行時處理)

以下 Story 在本文件建立前就已通過 G1,尚未補進本文件——下次 session 的 reporter
應補上對應章節(內容取自各工單當時定稿的 description):

- SDLCAIP1-2:加入 /health 端點回傳 200(冒煙測試用,非產品需求,可省略或註明性質)
- SDLCAIP1-4:新增文章 API
- SDLCAIP1-5:文章查詢/列表 API
- SDLCAIP1-6:文章編輯 API
- SDLCAIP1-7:文章刪除 API(若已通過 G1)

之後每張新 Story 通過 G1,由 orchestrator 委派 reporter 即時補上,不用再手動追。
