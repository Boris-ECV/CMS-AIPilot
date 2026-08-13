# 設計文件 — SDLCAIP1-20 前台文章詳細頁靜態輸出(含響應式版面)

## 對應需求規格

G1 通過版本:作為網站訪客,開啟文章詳細頁能看到完整標題、內容與發布時間,
且版面在手機/平板/桌機都正常顯示,以便在任何裝置上舒適閱讀文章內容。
驗收條件(Gherkin,共 5 條):

1. 完整內容顯示 → 標題、內容、發布時間三者皆呈現。
2. 手機寬度(<768px)→ 單欄版面,無水平捲軸。
3. 平板寬度(768–1024px)→ 版面調整,無水平捲軸。
4. 桌機寬度(>1024px)→ 有 max-width、置中版面,無水平捲軸。
5. HTML 特殊字元(`<`、`&`、`"`)在標題/內容中正確轉義,不產生標籤注入。

範圍外:首頁文章列表/分頁(SDLCAIP1-23/24)、搜尋(SDLCAIP1-16)、文章
被刪除時的「找不到」頁面設計(屬列表頁票)、後台管理介面、SEO meta 標籤。

依賴:SDLCAIP1-8(既有 generate/upload 觸發邏輯,已 Done)——本票僅變更
`_generate_and_upload_static_page` 產生的 HTML/CSS **內容**,不變更觸發
時機或呼叫方式(`create_article`/`update_article` 的呼叫序列、
`StaticPageGenerationError`/rollback 邏輯全部不動)。

## 現況(變更基準)

`src/cms_aipilot/main.py` 的 `_generate_and_upload_static_page`
(第 138–153 行)目前產生的 HTML:

- 無樣板引擎(無 Jinja2 依賴,`pyproject.toml` 未列),以 Python f-string
  直接組字串。
- 已對 `article.title`、`article.content` 呼叫 `html.escape()`
  (第 141–142 行)——AC5 的轉義機制**現況已存在**,本票延用、不重寫。
- **未輸出 `published_at`**(AC1 目前不成立)。
- **無 `<meta name="viewport">`**,無任何 CSS/`<style>`——AC2–4 目前完全
  不成立(無 viewport meta 標籤時,行動裝置瀏覽器會以預設虛擬版面寬度
  約 980px 渲染並縮放顯示,即使加上 CSS media query 也不會依實際裝置寬度
  觸發正確斷點)。
- 上傳方式(`s3.put_object(..., ContentType="text/html")`)、S3 key
  慣例(`articles/{id}.html`)、函式簽章 `(article: Article) -> None`
  全部不變。

## 介面/API 契約

無新增/變更對外 API 或端點。本票只變更 `_generate_and_upload_static_page`
內部組出的 HTML **字串內容**(即上傳到 S3、訪客瀏覽器直接讀取的靜態頁
本文),函式簽章、呼叫時機、上傳/失敗處理邏輯(`StaticPageGenerationError`、
`_publish_or_rollback`)完全不動,故無需定義 request/response 格式或狀態碼。

### 靜態頁 HTML 結構(輸出契約)

```html
<!DOCTYPE html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>{inline CSS,見下方}</style>
</head>
<body>
  <article class="article">
    <h1 class="article__title">{title}</h1>
    <time class="article__meta" datetime="{published_at_iso}">{published_at_display}</time>
    <div class="article__content">{content}</div>
  </article>
</body>
</html>
```

- `{title}`、`{content}`:沿用既有 `html.escape()` 處理後的字串,不改變
  轉義方式(對應 AC5)。
- `{published_at_iso}`:`article.published_at.isoformat()`,放在
  `<time datetime="...">` 屬性中作機器可讀值(標準 HTML5 語意,不影響
  視覺呈現)。`datetime` 型別本身非使用者輸入(由後端從 request body 解析
  出的 `datetime` 物件,非原始字串直接落地),不需 `html.escape()`。
- `{published_at_display}`:`article.published_at.strftime("%Y-%m-%d %H:%M")`
  ——顯示用格式,理由見下方「關鍵技術決策」。

### 內嵌 CSS(輸出契約)

CSS 以 `<style>` 內嵌於 `<head>`,不額外上傳/引用外部 `.css` 檔案(理由見
下方技術決策)。行動優先(mobile-first),斷點依 spec 明訂邊界:

```css
* { box-sizing: border-box; }
body {
  margin: 0;
  padding: 16px;
  font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
  line-height: 1.6;
  overflow-wrap: break-word;
}
.article { max-width: 100%; }
.article__title { font-size: 1.5rem; margin: 0 0 8px; }
.article__meta { display: block; color: #666; font-size: 0.875rem; margin-bottom: 16px; }
.article__content { white-space: pre-wrap; }
img, pre, table { max-width: 100%; }

/* 平板 768–1024px */
@media (min-width: 768px) and (max-width: 1024px) {
  body { padding: 24px; }
  .article__title { font-size: 1.75rem; }
}

/* 桌機 >1024px */
@media (min-width: 1025px) {
  body { padding: 32px; }
  .article { max-width: 800px; margin: 0 auto; }
  .article__title { font-size: 2rem; }
}
```

- 預設(無 media query)即為手機版單欄版面,`max-width: 100%` +
  `box-sizing: border-box` + `overflow-wrap: break-word` 三者組合確保任何
  寬度下都不會出現水平捲軸(對應 AC2/3/4 共通的「無水平捲軸」要求,而非
  只在特定斷點個別處理)。
- 平板/桌機斷點邊界對齊 spec 原文(平板 768–1024px、桌機 >1024px):
  平板用 `max-width: 1024px`(含 1024px 本身),桌機用
  `min-width: 1025px`(嚴格大於 1024px),避免 1024px 這個邊界寬度同時
  符合兩條 media query 造成不確定的層疊結果。

## 資料模型

無新增資料模型。`Article`/`ArticleCreate` pydantic model(`id`、`title`、
`content`、`published_at`)不變,DynamoDB `articles` 表結構不變。本票只是
把既有 `article.published_at` 欄位(呼叫端本來就已持有,現況函式只是沒
輸出它)加入 HTML 輸出,不涉及任何 schema 或欄位新增。

## 關鍵技術決策

- **CSS 內嵌於 `<style>` 標籤,不建立獨立 `.css` 檔案上傳 S3**:維持
  SDLCAIP1-8/9 已定案的「一篇文章對應一個 S3 object(`articles/{id}.html`)」
  模型,避免新增第二個 S3 key、額外的上傳失敗/rollback 分支、以及訪客
  瀏覽器多一次請求的複雜度——這些都是規格未要求、且會讓
  `_generate_and_upload_static_page` 的錯誤處理(單一 `put_object` 呼叫、
  單一失敗路徑)複雜化的額外設計面。

- **新增 `<meta name="viewport">`**:現況完全缺少,是 AC2–4(響應式版面)
  在技術上無法達成的根本原因,非規格明文要求但屬於「響應式版面」這個
  已核准驗收條件的必要技術前提,不是新的產品決策。

- **行動優先(mobile-first)CSS,而非為三個斷點分別寫死版面**:預設樣式
  即滿足手機版單欄需求,平板/桌機用 `min-width` media query 疊加調整,
  三個斷點共用同一套「無水平捲軸」保證(`box-sizing: border-box` +
  `max-width: 100%`),降低任兩個斷點行為不一致的風險。

- **`published_at` 顯示格式採 `strftime("%Y-%m-%d %H:%M")`**:spec 僅要求
  「顯示發布時間」,未指定格式/在地化/時區轉換規則。`published_at` 為
  request body 解析出的 naive `datetime`(無時區資訊,見 `ArticleCreate`
  model),故不做時區轉換(無資訊可轉);格式選擇不含歧義的
  ISO 風格年月日時分,是滿足「有顯示時間」這項已核准需求最小、無額外
  臆測的實作方式,不歸類為需要澄清的產品決策。

- **內文用 `white-space: pre-wrap` 保留換行,不改變既有 `html.escape()`
  轉義邏輯**:`article.content` 是純文字(非 HTML),原文若含換行,先前
  版本全部塞進單一 `<p>` 會讓換行消失。轉義後的字串本身不含格式資訊,
  換行需求靠 CSS 呈現、不需改寫任何跳脫/轉換邏輯,延續現有轉義機制
  (對 AC5 零影響,兩者正交)。

- **`<time datetime="...">` 使用 `.isoformat()` 而非跳脫後的顯示字串**:
  `datetime` 屬性值是機器可讀語意化標記(HTML5 標準用法),來源是
  `datetime` 物件的 `.isoformat()` 輸出而非使用者輸入,故不套用
  `html.escape()`——與 title/content(使用者輸入,必須轉義)在來源與
  風險性質上不同,沿用現況「只對使用者輸入欄位轉義」的既有邊界
  (title/content 已轉義,id/published_at 從未轉義,見現況程式碼)。

- **函式簽章與呼叫方式完全不變**:`_generate_and_upload_static_page(article:
  Article) -> None` 維持原樣,`_publish_or_rollback`、
  `StaticPageGenerationError`、S3 上傳失敗的 502 rollback 邏輯(SDLCAIP1-8
  定案內容)不受影響——本票是純粹的函式內部實作變更,不影響其呼叫者的
  行為契約。

## 開放設計問題(定稿時必須為空)

無。
