# 設計文件 — SDLCAIP1-8 文章新增/編輯後產生靜態 HTML 並上傳 S3(覆蓋)

## 對應需求規格
對應 G1 已核准之最終版需求規格(Reopen Count: 1,人工駁回後修正版)：

- `POST /articles`(SDLCAIP1-4,Done)與 `PUT /articles/{id}`(SDLCAIP1-6,Done)須擴充：
  DynamoDB 寫入成功後，產生靜態 HTML 並上傳至 S3 key `articles/{id}.html`
  (bucket 名稱取自環境變數 `ARTICLES_STATIC_BUCKET_NAME`)。
- S3 上傳成功 → 回傳既有成功回應不變（POST 201 / PUT 200）。
- S3 上傳失敗 → 回滾：刪除剛寫入/更新的 DynamoDB item（PUT 情境為整筆刪除，
  不還原舊版本，因未保留 snapshot），並回傳 502，body 為
  `{"error": "STATIC_PAGE_GENERATION_FAILED", "message": "Article could not be published: static page upload failed."}`。
- 若回滾用的 DynamoDB delete 也失敗（雙重失敗）→ 以 ERROR 等級記錄
  （article id + 兩個失敗原因），仍回傳 502，不做同步重試。
- Out of scope（已定案，不重新討論）：S3 upload 重試/backoff、非同步/佇列化
  republish、CDN cache invalidation、DELETE endpoint 行為（SDLCAIP1-9 範圍）、
  PUT 回滾時還原舊版本。

## 介面/API 契約

沿用既有端點簽章與成功路徑回應，僅新增失敗路徑：

### POST /articles
- 成功（DynamoDB 寫入 + S3 上傳皆成功）：`201 Created`，body 為既有 `Article` 模型，不變。
- 失敗（DynamoDB 寫入成功，S3 上傳失敗，DynamoDB rollback 刪除成功或失敗皆同一回應）：
  `502 Bad Gateway`
  ```json
  {
    "error": "STATIC_PAGE_GENERATION_FAILED",
    "message": "Article could not be published: static page upload failed."
  }
  ```

### PUT /articles/{article_id}
- 成功：`200 OK`，body 為既有 `Article` 模型，不變。
- 失敗（同上情境，rollback 為整筆刪除該 article）：同一 502 body 格式如上。
- 既有 `404 Not Found`（article 不存在）行為不變，此 story 不影響。

錯誤欄位命名沿用 spec 指定的 `error`/`message`（注意：這與 SDLCAIP1-9 既有的
`_delete_static_page` 錯誤回應所用的 `error_code`/`detail`/`article_id` 欄位命名
不同——此為 spec 明文指定的格式，不可自行統一成 SDLCAIP1-9 的形狀，見下方「關鍵技術決策」）。

## 資料模型

無新增資料模型。不新增欄位、不新增資料表、不新增索引。DynamoDB `articles` 表結構
（`id` 為 partition key）維持不變；本 story 僅新增「寫入後上傳 S3、失敗則刪除該筆
item」的流程，不改變既有欄位或型別。

## 關鍵技術決策

- **重用 `get_s3_client()`**：`get_s3_client()` 已由 SDLCAIP1-9 在
  `src/cms_aipilot/main.py` 新增（回傳 lazily-created `boto3.client("s3")`，
  以利測試 mock），本 story 直接呼叫既有函式，不得重新定義或建立第二個
  S3 client 工廠函式。
- **新增 `_generate_and_upload_static_page(article: Article) -> None`**：對稱於
  既有 `_delete_static_page(article_id)` 的命名與結構（底線前綴 = 內部輔助函式，
  接受 domain 物件、內部組 bucket/key、丟出自訂例外），維持與 SDLCAIP1-9 一致的
  程式碼慣例，降低未來讀者的認知負擔。
- **新增例外類別 `StaticPageGenerationError`**：比照既有 `StaticPageDeletionError`
  的形狀（`article_id` + `cause`），供 route handler 用 `try/except` 攔截、
  觸發 502 分支，而非用回傳值判斷成功/失敗——與現有 delete 端點的錯誤處理風格一致。
- **成功路徑放在 `try` 之外、失敗才進 rollback 分支**：POST/PUT handler 先照舊
  完成 `table.put_item(...)`，接著在獨立的 `try/except` 中呼叫上傳函式；
  上傳成功直接回傳既有 Article 物件（不變更任何已通過驗收的行為），失敗才觸發
  DynamoDB rollback delete + 502。此順序（先寫 DB 再上傳 S3，失敗則刪 DB）是
  spec 明文指定的流程，非設計者臆測。
- **Rollback delete 失敗時的處理**：用巢狀 `try/except` 包住
  `table.delete_item(...)`，失敗時以 `logger.error(...)` 記錄
  `article_id`、S3 上傳失敗原因、DynamoDB delete 失敗原因三項，但**不**重新
  拋出例外中斷 request——仍照 spec 回傳同一個 502 body（spec 明文：
  「仍回傳 502，不做同步重試」），對前端行為與單一失敗情境完全一致，
  差異只在 log 內容更完整，避免因二次例外導致回應變成未預期的 500。
- **PUT rollback 使用整筆刪除、不做「回復舊版本」**：spec 已明確排除此選項
  （未保留 snapshot），故 PUT 上傳失敗與 POST 上傳失敗的 rollback 動作相同
  （皆為 `table.delete_item`），不需為 PUT 額外設計還原邏輯。
- **500 vs 502 語意選擇不重新討論**：spec 已明文指定 502，本設計不對此語意
  （上游依賴 S3 失敗視為 Bad Gateway）做額外論證，直接依規格採用。

## 開放設計問題(定稿時必須為空)

無。
