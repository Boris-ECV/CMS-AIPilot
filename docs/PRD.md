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

## 待補(reporter 下次執行時處理)

以下 Story 在本文件建立前就已通過 G1,尚未補進本文件——下次 session 的 reporter
應補上對應章節(內容取自各工單當時定稿的 description):

- SDLCAIP1-2:加入 /health 端點回傳 200(冒煙測試用,非產品需求,可省略或註明性質)
- SDLCAIP1-4:新增文章 API
- SDLCAIP1-5:文章查詢/列表 API
- SDLCAIP1-6:文章編輯 API
- SDLCAIP1-7:文章刪除 API(若已通過 G1)

之後每張新 Story 通過 G1,由 orchestrator 委派 reporter 即時補上,不用再手動追。
