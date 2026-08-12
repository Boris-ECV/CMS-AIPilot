# 設計文件 — SDLCAIP1-9 文章刪除後移除對應靜態頁（REVISED, Reopen #1）

## 對應需求規格
對應 SDLCAIP1-9 於 G1 重審（Reopen #1）通過之定稿規格：DELETE /articles/{id}（SDLCAIP1-7 既有端點，已 Done）在成功刪除 DynamoDB 記錄後，額外刪除 S3 上對應的靜態頁物件 `articles/{article_id}.html`。**S3 刪除失敗時阻斷 API 的成功回應**（比照 SDLCAIP1-8 新政策的錯誤語氣，但不套用其 DynamoDB 回滾邏輯——DELETE 為 SDLCAIP1-7 已鎖定的 hard-delete 契約，成功後不可逆，本設計不發明復原能力）。404 情境（文章不存在）完全不觸發 S3 呼叫。首頁列表頁更新不在此 Story 範圍內（依賴尚未建置的 SDLCAIP1-15）。

## 介面/API 契約
沿用既有 `DELETE /articles/{article_id}`（定義於 `src/cms_aipilot/main.py`）：

- 成功刪除且 S3 清理也成功：`204 No Content`，回應本文為空。行為不變。
- 成功刪除但 S3 物件刪除**失敗**：`502 Bad Gateway`，回應本文：
  ```json
  {
    "error_code": "STATIC_PAGE_DELETION_FAILED",
    "detail": "Article deleted but its static page could not be removed from S3.",
    "article_id": "<article_id>"
  }
  ```
  DynamoDB 記錄仍維持已刪除狀態（不可逆，不嘗試復原）；此為 SDLCAIP1-9 專屬的新增行為。
- 文章不存在：`404 Not Found`，`detail="Article not found"`（與現行行為一致）。此路徑**不呼叫**S3 刪除。
- 不新增任何 request 欄位、不新增端點。

## 資料模型
無新增資料模型。DynamoDB 資料表結構不變（SDLCAIP1-7 既有邏輯：`get_item` 檢查存在性 → `delete_item`）。S3 物件非結構化資料，不涉及 schema 變更；物件 key 慣例 `articles/{article_id}.html` 沿用 SDLCAIP1-8 已定案的命名規則，原樣重用。

## 關鍵技術決策

1. **S3 刪除呼叫的插入點**：在 `delete_article()` 中，確認文章存在（`existing.get("Item") is not None`）且 `table.delete_item(...)` 執行**之後**，呼叫新的私有函式 `_delete_static_page(article_id: str) -> None`。理由：必須先確保 DynamoDB 記錄確實存在且已刪除，才代表這是一次「成功刪除」，S3 清理是否成功才決定最終 API 回應（204 或 502）。

2. **`_delete_static_page` 失敗處理方式（本次修正重點）**：不再吞下例外只記 log，改為**向上傳遞失敗**——`_delete_static_page` 捕捉 `BotoCoreError`/`ClientError` 後改為 raise 一個內部例外 `StaticPageDeletionError(article_id, cause)`（新增於同一模組），而非回傳 `None` 靜默處理。理由：呼叫端（`delete_article`）需要知道失敗才能決定回傳 502，而非像先前設計一樣讓失敗對呼叫端不可見。

   ```python
   class StaticPageDeletionError(Exception):
       def __init__(self, article_id: str, cause: Exception) -> None:
           self.article_id = article_id
           self.cause = cause
           super().__init__(f"Failed to delete static page for article_id={article_id}: {cause}")


   def _delete_static_page(article_id: str) -> None:
       bucket = os.environ["ARTICLES_STATIC_BUCKET_NAME"]
       key = f"articles/{article_id}.html"
       s3 = get_s3_client()
       try:
           s3.delete_object(Bucket=bucket, Key=key)
       except (BotoCoreError, ClientError) as exc:
           logger.error(
               "Failed to delete static page for article_id=%s: %s",
               article_id,
               exc,
           )
           raise StaticPageDeletionError(article_id, exc) from exc
   ```

3. **`delete_article()` 呼叫端邏輯**：

   ```python
   table.delete_item(Key={"id": article_id})
   try:
       _delete_static_page(article_id)
   except StaticPageDeletionError as exc:
       return JSONResponse(
           status_code=502,
           content={
               "error_code": "STATIC_PAGE_DELETION_FAILED",
               "detail": "Article deleted but its static page could not be removed from S3.",
               "article_id": article_id,
           },
       )
   return Response(status_code=204)
   ```
   DynamoDB `delete_item` 呼叫本身不受影響、不回滾——一旦執行就視為既定事實，這是刻意決定（見對應需求規格）。

4. **S3 client 取得方式**：沿用 `get_s3_client()`（比照 `get_articles_table()` 的 lazy-construction 模式），與先前版本設計不變。

5. **Bucket 名稱來源與物件 key 組成**：不變，`os.environ["ARTICLES_STATIC_BUCKET_NAME"]` 與 `f"articles/{article_id}.html"`。

6. **Logger 設定**：不變，`logging.getLogger(__name__)`。

## 開放設計問題(定稿時必須為空)
無。
