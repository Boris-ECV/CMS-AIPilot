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

## 待補(reporter 下次執行時處理)

以下 Story 在本文件建立前就已通過 G1,尚未補進本文件——下次 session 的 reporter
應補上對應章節(內容取自各工單當時定稿的 description):

- SDLCAIP1-2:加入 /health 端點回傳 200(冒煙測試用,非產品需求,可省略或註明性質)
- SDLCAIP1-4:新增文章 API
- SDLCAIP1-5:文章查詢/列表 API
- SDLCAIP1-6:文章編輯 API
- SDLCAIP1-7:文章刪除 API(若已通過 G1)

之後每張新 Story 通過 G1,由 orchestrator 委派 reporter 即時補上,不用再手動追。
