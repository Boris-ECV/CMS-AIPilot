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

Scenario: 手機寬度版面正常顯示
  Given 文章詳細頁已產生
  When 以手機寬度（<768px）檢視頁面
  Then 內容單欄顯示、無橫向捲動、文字可讀不溢出

Scenario: 平板寬度版面正常顯示
  Given 文章詳細頁已產生
  When 以平板寬度（768px–1024px）檢視頁面
  Then 版面依平板寬度調整、無橫向捲動

Scenario: 桌機寬度版面正常顯示
  Given 文章詳細頁已產生
  When 以桌機寬度（>1024px）檢視頁面
  Then 版面套用桌機排版（如內容最大寬度限制、置中）、無橫向捲動

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

## SDLCAIP1-26 — 搜尋索引產生（新增文章觸發）

**使用者故事:** As a 網站前台訪客, I want 新發布的文章立即被收錄進搜尋索引（含標題與全文）, so that 我可以在文章發布後馬上透過關鍵字搜尋到它.

**驗收條件 (Gherkin):**

```gherkin
Scenario: 新增文章成功後索引即時包含該文章
  Given 系統目前已有 0 篇以上文章
  When 呼叫 create article（POST /articles）成功建立一篇新文章
  Then S3 上 search/index.json 被重新產生並覆蓋上傳，內容為一個 JSON 陣列，
    且包含一筆該新文章的項目，至少含 id、title、content 三個欄位，值與剛
    建立的文章相符

Scenario: 索引反映目前資料庫中的全部文章，不只新增的那一篇
  Given 資料庫中已存在至少一篇既有文章
  When 呼叫 create article 成功新增另一篇文章
  Then 重新產生的 search/index.json 陣列筆數等於資料庫目前全部文章數
    （既有 + 新增），既有文章的項目也存在於陣列中

Scenario: 索引產生/上傳失敗時，新增動作視為失敗並回滚
  Given create article 的 DynamoDB 寫入已成功
  When search/index.json 產生或上傳至 S3 失敗
  Then 呼叫端收到既有 502 錯誤回應（比照 SDLCAIP1-8/23 既有
    STATIC_PAGE_GENERATION_FAILED 慣例），且本次新增的 DynamoDB 項目被
    回滚刪除

Scenario: 第一篇文章建立時，索引檔案首次產生
  Given 系統目前沒有任何文章、S3 上尚無 search/index.json
  When 建立第一篇文章成功
  Then S3 上首次出現 search/index.json，內容為僅含該篇文章的 JSON 陣列
```

**範圍外:**
- 文章更新/刪除觸發的索引重新產生（SDLCAIP1-27）
- 前台搜尋頁面 UI、關鍵字比對邏輯、結果呈現（SDLCAIP1-28）
- 索引檔案除 id/title/content/published_at 以外的欄位（分類、標籤——Epic 未定義）
- 索引檔案的分頁/檔案分割（單一 JSON 檔案，不論文章數量多寡）
- 後台管理 UI 的搜尋/篩選功能（不同產出物）

**依賴:** 工單依賴：無附塞前置；參考 SDLCAIP1-8/9（既有 create 觸發與 S3 上傳/回滚慣例）、SDLCAIP1-23（「新增時同步重建全量靜態輸出」模式先例）; 外部依賴：AWS S3（既有 ARTICLES_STATIC_BUCKET_NAME）、DynamoDB（既有 articles table）。架構決策依據：HUMAN-INPUT SDLCAIP1-25。本工單為 SDLCAIP1-16（前台靜態搜尋索引產生 + 搜尋 UI）依 docs/02 §6 拆分規則拆分後的子工單之一。

## SDLCAIP1-27 — 搜尋索引重新產生（更新／刪除文章觸發）

**使用者故事:** As a 網站前台訪客, I want 文章被更新或刪除後搜尋索引同步反映該異動, so that 我搜尋到的結果不會是已刪除或已過期的內容。

**驗收條件 (Gherkin):**
1. 更新文章後索引反映最新標題/內容
2. 刪除文章後索引不再包含該文章
3. 刪除最後一篇文章後索引成為空陣列 []
4. 更新觸發的索引上傳失敗 → 502 STATIC_PAGE_GENERATION_FAILED + DynamoDB 回滾
5. 刪除觸發的索引上傳失敗 → 502（同類命名風格如 STATIC_LIST_PAGE_REGENERATION_FAILED），無回滾

**不在此範圍:**
- 新增文章觸發的索引首次產生（SDLCAIP1-26）
- 前台搜尋頁面 UI（SDLCAIP1-28）
- update「回滾其實是整筆刪除」既有語意落差的修正（沿用 SDLCAIP1-24 已定案）
- 舊索引項目的版本歷史/還原機制

**依賴:** is blocked by SDLCAIP1-26；參考 SDLCAIP1-24（update/delete 觸發同步重建模式先例）；架構決策依據：HUMAN-INPUT SDLCAIP1-25（人類已核准：索引含全文 content、S3 路徑 search/index.json）。

## SDLCAIP1-28 — 前台搜尋頁面（search.html）

**使用者故事:** As a 網站前台訪客, I want 在一個獨立的搜尋頁面輸入關鍵字並看到符合標題或全文的文章清單, so that 我可以快速找到我感興趣的文章內容。

**驗收條件 (Gherkin):**
1. 獨立搜尋頁存在且可從其他靜態頁面連結進入
2. 輸入關鍵字後顯示標題相符的文章
3. 輸入關鍵字後顯示內文相符的文章（全文搜尋）
4. 關鍵字比對不分大小寫、為子字串比對
5. 查無符合結果時顯示明確提示
6. 結果不分頁，全部顯示
7. 搜尋框為空時不顯示任何結果或錯誤
8. 比對邏輯純前端執行，不呼叫後端 API（唯一資料來源是 search/index.json）

**不在此範圍:**
- 搜尋結果分頁/無限捲動
- 任何第三方 JS 函式庫或建置管線（純 vanilla JS）
- 搜尋結果排序邏輯
- 內文摘要/highlight
- 分類/標籤篩選與進階搜尋語法
- 後台管理 UI 搜尋
- 響應式版面細節設計（沿用既有共用樣式）

**依賴:** is blocked by SDLCAIP1-26、SDLCAIP1-27；也需修改既有列表頁/詳細頁加入連結；架構決策依據：HUMAN-INPUT SDLCAIP1-25（人類已核准：獨立搜尋頁、vanilla JS 比對、不分頁全部顯示）。

## SDLCAIP1-30 — 建立共用視覺樣式 Token 機制（design-tokens.css）

**使用者故事:** As a 維護 CMS AI Pilot 的開發者, I want 前台靜態頁與後台管理介面共用同一份視覺樣式 token（色彩、字級、間距、斷點）, so that 之後每一張 UI 優化 Story 不用各自重新定義樣式數值，視覺風格能保持全站一致。

**驗收條件 (Gherkin):**

```gherkin
Scenario: design-tokens.css 內容符合設計規範
  Given docs/design-system.md 第 1-5 節定義的色彩/字體/間距/斷點 token
  When 讀取新建立的 design-tokens.css
  Then 檔案內容包含該文件定義的全部 CSS 自訂屬性，數值完全一致

Scenario: 前台靜態頁發布流程包含此檔案
  Given 後台觸發文章新增/編輯/刪除的靜態頁重新產生流程（沿用現有 search.html 等全域靜態資源的作法：於同一個發布/rollback 流程中一併上傳，見 src/cms_aipilot/main.py 的 _generate_and_upload_* 系列函式）
  When 靜態頁上傳至 S3
  Then design-tokens.css 也同步上傳至 S3 對應路徑，且路徑在本 Story 的設計文件中明確定義

Scenario: 後台管理介面實際引用此檔案
  Given frontend/（Vite+React 後台）建置流程
  When 執行 npm run build
  Then design-tokens.css 被至少一個既有元件 import 並生效（用瀏覽器開發工具可驗證變數值已套用），不是只有檔案存在但沒被引用
```

**範圍外:**
- 將既有前台靜態頁（文章列表、文章詳細頁、首頁列表、搜尋頁）的既有 inline `<style>` 改為引用此檔案——留給各自後續的 UI 優化 Story（依 `docs/design-system.md` §10 套用範圍策略）
- 後台（`frontend/`）元件層級的樣式規則系統化實作（按鈕/表單/卡片樣式等，見 `docs/design-system.md` §7）——本票允許為單一既有元件（建議：LoginPage）新增最小限度的元件 CSS 檔案以套用少數 token 變數作為驗證，但不含完整樣式規則實作

**依賴:**
- 工單依賴：無
- 外部依賴：無

## SDLCAIP1-31 — 後台登入頁 UI 套用設計規範（design-tokens.css 完整套用）

**使用者故事:** As a 使用後台的管理者, I want 登入頁視覺符合 docs/design-system.md 定義的規範, so that 後台介面呈現一致、專業的視覺風格。

**驗收條件 (Gherkin):**

```gherkin
Scenario: 色彩與字體套用 token
  Given LoginPage.tsx 與 LoginPage.css（SDLCAIP1-30 已建立最小整合）
  When 檢查頁面上標題、標籤、輸入框、按鈕的 computed style
  Then 背景色/文字色/字體皆來自 design-tokens.css 的 --color-*/--font-family-base 變數，無寫死的色碼或字型；submit 按鈕套用 design-system.md §7 primary 按鈕規則（黑底白字，無圓角或極小圓角）

Scenario: 間距、字級階層與欄位版面套用
  Given docs/design-system.md §3 字級階層、§4 間距 scale、§7 表單欄位規則
  When 檢查標題、表單欄位、按鈕的 font-size 與 padding/margin，以及 label 與 input 的相對位置
  Then 數值皆取自該規範定義的階層/scale，無自訂魔術數字；label 位於對應欄位上方並靠左對齊

Scenario: 必填欄位以文字標示
  Given docs/design-system.md §7 表單欄位規則（必填不可僅靠顏色標示）
  When 檢查帳號/密碼欄位的 label
  Then 皆有可見文字（如「（必填）」或等效文字）標示必填，非僅依賴顏色或瀏覽器預設星號

Scenario: 錯誤訊息樣式
  Given docs/design-system.md §7（錯誤訊息文字紅色 + 圖示，不能只靠邊框變色）；紅色具體色值屬 §1 定義的例外情形，由本工單 Designing 階段的設計文件明確記錄
  When 登入失敗顯示 role="alert" 錯誤訊息
  Then 錯誤文字使用設計文件記錄的例外紅色並搭配圖示，不僅靠邊框變色

Scenario: 表單無障礙基本要求
  Given docs/design-system.md §8
  When 檢查帳號/密碼欄位
  Then 皆有對應 <label>，focus 狀態有可見樣式（非 outline: none 且無替代）

Scenario: 既有測試不受影響
  Given 既有 LoginPage.test.tsx 與 tests/e2e/test_design_tokens_e2e.py
  When 套用完整樣式後執行測試
  Then 全數通過，不因新增 className/CSS 導致既有選取器失效
```

**範圍外:**
- 不含表單驗證邏輯或登入行為變更，僅視覺樣式
- 不含按鈕元件系統化抽象（如共用 Button 元件），僅本頁面套用樣式規則
- 不含 secondary/danger 按鈕變體套用（登入頁僅有一個 primary 送出按鈕）

**依賴:**
- 工單依賴：blocked by SDLCAIP1-30（已 DONE）
- 外部依賴：無
- 設計依賴：錯誤訊息紅色具體色值由 architect 於 Designing 階段依 design-system.md §1 例外條款決定並記錄於設計文件

## SDLCAIP1-33 — 後台新增/編輯文章表單 UI 套用設計規範

**使用者故事:** As a 使用後台的管理者, I want 新增/編輯文章表單視覺符合 docs/design-system.md 定義的規範, so that 後台介面呈現一致、專業的視覺風格。

**驗收條件 (Gherkin):**

```gherkin
Scenario: 色彩與字體套用 token
  Given ArticleForm.tsx（目前完全無 CSS）
  When 檢查表單標題、欄位、按鈕的 computed style
  Then 皆來自 design-tokens.css 的 --color-*/--font-family-base 變數

Scenario: 表單欄位規則套用
  Given docs/design-system.md §7 表單欄位規則
  When 檢查標題/內文/發布時間欄位
  Then label 置於欄位上方靠左；必填以文字標示（非僅顏色）；錯誤訊息為紅色文字+圖示，不僅靠邊框變色

Scenario: 無障礙基本要求
  Given docs/design-system.md §8
  When 檢查所有表單欄位
  Then 皆有對應 <label>，focus 狀態有可見樣式

Scenario: 按鈕變體套用
  Given ArticleForm.tsx 的「儲存」(submit) 與「取消」(type="button") 按鈕
  When 檢查兩按鈕的 computed style
  Then 「儲存」套用 primary 樣式（黑底白字）；「取消」套用 secondary 樣式（白底黑框）；皆無圓角或僅極小圓角

Scenario: 標題與版面對齊規則套用
  Given docs/design-system.md §6 對齊規則
  When 檢查表單 <h1>（「新增文章」/「編輯文章」）與各欄位 label
  Then <h1> 置中；label 與欄位維持靠左

Scenario: 既有測試不受影響
  Given 既有 ArticleForm 相關測試（若無則本 Story 需補上基本 render/驗證測試）
  When 套用樣式後執行 npm run test
  Then 全數通過
```

**範圍外:**
- 不含表單驗證邏輯或送出行為變更，僅視覺樣式
- 不含共用 Button/Input 元件抽象化，僅本頁面套用樣式規則

**依賴:**
- 工單依賴：blocked by SDLCAIP1-30（已 DONE）
- 外部依賴：無

## SDLCAIP1-34 — 前台文章詳細頁 UI 套用設計規範

**使用者故事:** As a 前台訪客, I want 文章詳細頁視覺符合 docs/design-system.md 定義的規範, so that 前台網站呈現一致、有質感的編輯感風格。

**驗收條件 (Gherkin):**

```gherkin
Scenario: 頁面引用 design-tokens.css
  Given main.py 的 _generate_and_upload_static_page 函式
  When 產生文章詳細頁靜態 HTML
  Then <head> 包含 <link rel="stylesheet" href="/design-tokens.css">（絕對路徑，比照既有 href="/search.html" 慣例）

Scenario: 色彩與字體改用 token
  Given _ARTICLE_PAGE_STYLE 的既有色彩與字體定義
  When 檢查產生的靜態頁面樣式
  Then 色彩改為 var(--color-text-primary)（標題/內文）、var(--color-text-secondary)（meta，取代寫死的 #666）；字體改為 var(--font-family-base)

Scenario: 標題/meta 置中、內文靠左
  Given _ARTICLE_PAGE_STYLE 的既有版面規則
  When 檢查產生的靜態頁面
  Then .article__title 與 .article__meta 置中（text-align: center），.article__content 維持靠左

Scenario: 既有響應式斷點行為不變
  Given SDLCAIP1-20 已實作的 768px/1025px 斷點邏輯
  When 檢查套用設計 token 後的頁面在各斷點的版面
  Then 斷點觸發邏輯與版面行為與套用前一致，僅換色彩/字體/間距數值

Scenario: 既有 e2e 測試更新為攔截模式
  Given tests/e2e/test_article_detail_page_e2e.py 現行使用 page.set_content 載入頁面
  When 執行 e2e 測試
  Then 測試改用 page.route+page.goto 攔截模式載入頁面與 design-tokens.css（因外部樣式表在 about:blank origin 下不會實際載入）
```

**不在此範圍:**
- 文章內容渲染邏輯變更
- 斷點值或版面結構重新設計
- design-tokens.css 本身內容變更（已由 SDLCAIP1-30 定案）

**依賴:**
- 工單依賴：blocked by SDLCAIP1-30（已 DONE）
- 外部依賴：無

## SDLCAIP1-35 — 前台首頁文章列表 UI 套用設計規範

**使用者故事:** As a 前台訪客, I want 首頁文章列表視覺符合 docs/design-system.md 定義的規範, so that 前台網站呈現一致、有質感的編輯感風格。

**驗收條件 (Gherkin):**

```gherkin
Scenario: 色彩與字體改用 token
  Given main.py 的 _LIST_PAGE_STYLE 與 _ARTICLE_PAGE_STYLE 串接組成單一 <style>
  When 檢查產生的首頁列表頁靜態 HTML
  Then 色彩/字體改為 var(--color-*)/var(--font-family-base)；頁面 <head> 新增 <link> 引用 design-tokens.css（路徑慣例由 architect 於 Designing 階段決定）

Scenario: 列表項不用邊框/陰影/色塊
  Given 既有 _LIST_PAGE_STYLE 中 .article-list__item 的 border-bottom: 1px solid #eee 定義
  When 檢查套用設計 token 後的列表頁
  Then .article-list__item 移除邊框，改以 --space-* 間距 token 做分隔

Scenario: 標題與日期置中
  Given _render_list_page_html 的既有版面規則
  When 檢查列表項的標題與日期
  Then .article-list__link（標題）與 .article-list__meta（日期）文字置中（注意：現行未渲染文章摘要/內文欄位，故不含「摘要靠左」）

Scenario: 既有分頁與響應式斷點行為不變
  Given SDLCAIP1-23/24 已實作的分頁（_list_page_key、上一頁/下一頁 nav）與 768px/1025px 斷點行為
  When 檢查套用設計 token 後的頁面
  Then 分頁邏輯與響應式斷點行為與套用前一致

Scenario: 新增真實瀏覽器樣式驗證
  Given 現行無任何涵蓋首頁列表頁的真實瀏覽器 e2e 測試（僅有 TestClient 子字串測試，無法驗證 computed CSS）
  When 比照 tests/e2e/test_article_detail_page_e2e.py 的既有模式（mock S3 擷取產出的 Body、page.set_content() 載入；本頁無 client-side script/fetch，不需 page.route() 攔截）新增 e2e 測試檔
  Then 新測試驗證 token 色彩/字體、無 border/box-shadow/background、標題與日期置中，全數通過
```

**不在此範圍:**
- 分頁邏輯、資料來源變更
- 斷點值或版面結構重新設計
- 新增文章摘要/內文片段至列表項（現行未渲染此欄位，屬新功能）

**依賴:**
- 工單依賴：blocked by SDLCAIP1-30（已 DONE）
- 外部依賴：無

## SDLCAIP1-36 — 前台搜尋頁 UI 套用設計規範

**使用者故事:** As a 前台訪客, I want 搜尋頁視覺符合 docs/design-system.md 定義的規範, so that 前台網站呈現一致、有質感的編輯感風格。

**驗收條件 (Gherkin):**

```gherkin
Scenario: 頁面引入 design-tokens.css
  Given _generate_and_upload_search_page() 產生的 search.html 目前 <head> 未引用 design-tokens.css
  When 套用本 Story
  Then <head> 新增 <link rel="stylesheet" href="/design-tokens.css">（絕對路徑，比照 SDLCAIP1-34/35 慣例）

Scenario: 搜尋輸入框樣式改用 token
  Given _SEARCH_PAGE_STYLE 目前 .search-form__input 的 padding/font-size/margin 為寫死數值（8px/12px、1rem、16px），無色彩/邊框宣告
  When 套用本 Story
  Then 寫死的間距數值改為對應 var(--space-*)（數值不變）；若新增任何色彩/邊框宣告需改用 var(--color-*)

Scenario: 搜尋結果列表項目套用設計規範樣式
  Given search.html 目前完全沒有針對 .article-list__item / .article-list__link（搜尋結果 JS 動態產生時重用的既有 class 名稱）的樣式宣告——這兩個 class 定義於 _LIST_PAGE_STYLE，但該常數目前未被組進 search.html 的 <style> 標籤，故搜尋結果目前呈現瀏覽器預設樣式（無設計規範套用，也無邊框可言）
  When 套用本 Story，為 .article-list__item / .article-list__link 在 search.html 情境下新增樣式（實作方式——新增專屬常數或 scoped 選擇器——由 Designing 階段決定，不得依賴 SDLCAIP1-35 對 _LIST_PAGE_STYLE 的改動，本票須可獨立完成與部署）
  Then 色彩改用 var(--color-text-primary)，字體改用 var(--font-family-base)；不使用 border/box-shadow/background-color；項目間距靠 var(--space-*) 留白分隔；標題（.article-list__link）置中（比照 SDLCAIP1-35 對同一 class 的置中決策）

Scenario: 搜尋結果不渲染摘要／內文片段（釐清舊草稿的錯誤假設）
  Given _SEARCH_PAGE_SCRIPT 目前只將 item.content 用於比對，從未渲染到 DOM；每筆結果只有一個 <a> 標題連結
  When 套用本 Story
  Then 不新增摘要/內文片段渲染（屬新功能，範圍外，比照 SDLCAIP1-35 同一排除項）；驗收僅涵蓋標題連結本身的樣式

Scenario: 既有 vanilla JS 比對邏輯與無結果狀態不受影響
  Given SDLCAIP1-26/27/28 已實作的前端子字串比對邏輯與 #search-empty 無結果訊息
  When 套用樣式後執行搜尋（含有結果與無結果情境）
  Then 比對邏輯與 DOM 結構（element id/既有 class 名稱）不變，僅樣式變更；#search-empty 訊息不套用 --color-error（非表單驗證錯誤，維持一般文字樣式）

Scenario: 既有測試通過 + 新增 token 驗證 e2e 測試
  Given 既有 tests/test_search_page.py、tests/e2e/test_search_page_e2e.py
  When 套用樣式後執行
  Then 既有測試全數通過；另需新增一個 e2e 測試檔（比照 tests/e2e/test_article_detail_page_e2e.py 於 SDLCAIP1-34 的 page.route + page.goto 攔截模式，因 page.set_content 無法讓 <link> 實際生效），斷言 .search-form__input／.article-list__link 的 computed color/font-family 為 token 值、.article-list__item 的 border/box-shadow/background 為 none/0px/transparent、.article-list__link 的 text-align 為 center
```

**不在此範圍:**
- 不含搜尋比對邏輯、索引產生邏輯變更，僅視覺樣式
- 不含斷點值或版面結構重新設計
- 不新增摘要/內文片段渲染到搜尋結果（目前只渲染標題，新增屬新功能——比照 SDLCAIP1-35 同一排除項）
- 不修改共用的 `_LIST_PAGE_STYLE`（SDLCAIP1-35 範圍）或 `_ARTICLE_PAGE_STYLE` 本體；本票對 `.article-list__item`/`.article-list__link` 的樣式套用範圍限定在 search.html 這一個頁面
- 不套用 `--color-error` 於 #search-empty 無結果訊息（該訊息非表單驗證錯誤情境）

**依賴:**
- 工單依賴：blocked by SDLCAIP1-30（已 DONE，提供 design-tokens.css）
- **不** blocked by SDLCAIP1-35（前台首頁列表頁）——雖然搜尋結果重用 `.article-list__item`/`.article-list__link` class 名稱，但 search.html 目前未組入 `_LIST_PAGE_STYLE`，兩票技術上互不影響，可獨立完成
- 外部依賴：無

## 待補(reporter 下次執行時處理)

以下 Story 在本文件建立前就已通過 G1,尚未補進本文件——下次 session 的 reporter
應補上對應章節(內容取自各工單當時定稿的 description):

- SDLCAIP1-2:加入 /health 端點回傳 200(冒煙測試用,非產品需求,可省略或註明性質)
- SDLCAIP1-4:新增文章 API
- SDLCAIP1-5:文章查詢/列表 API
- SDLCAIP1-6:文章編輯 API
- SDLCAIP1-7:文章刪除 API(若已通過 G1)

之後每張新 Story 通過 G1,由 orchestrator 委派 reporter 即時補上,不用再手動追。
