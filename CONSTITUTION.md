# CONSTITUTION — CMS AI Pilot

<!--
Durable engineering principles for this project. Read by
requirements-analyst / architect / reviewer (see their agent docs'
step "0."). Purpose: narrow judgment calls that would otherwise be
re-decided from scratch on every story, so similar situations get
similar answers across the codebase. This does NOT remove the
disclosure requirement — a judgment call guided by a principle here
must still be stated explicitly in the spec/design/review output, not
silently applied.

Keep this short and stable. Add a principle only after it has come up
as a real judgment call more than once; don't pre-populate hypothetical
rules.
-->

## 失敗處理哲學（Failure handling）

- 對外部依賴（DynamoDB、S3、第三方 API）的呼叫，預設要有明確的錯誤處理，
  不可讓例外無聲穿透到 handler 外層變成未分類的 500。
- 寫入類操作（create/update/delete）失敗時，不可留下部分寫入的中間狀態；
  若底層儲存不支援原子性，要在設計文件中明確說明如何處理（例如冪等重試、
  補償動作），而不是留給實作者臨場判斷。
- 靜態頁面重新產生（publish 流程）失敗時，不可讓網站處於「部分頁面新、
  部分頁面舊」且無記錄的狀態——要嘛整批成功，要嘛明確記錄哪些頁面未更新。

## 安全預設（Security defaults）

- 所有需要登入才能存取的 API，預設拒絕（deny-by-default），而非預設允許
  再加例外清單。
- 涉及計數/限流的安全機制（例如登入失敗鎖定）必須是原子操作
  （atomic increment/compare-and-swap），不可用「讀取→判斷→寫入」的非原子
  組合，避免併發下被繞過。
- 使用者輸入一律視為不可信：進入資料庫查詢、檔案路徑、HTML 輸出前都要
  經過對應的驗證/逸出處理。
- 不在程式碼或設定檔中硬編機密資訊；機密一律透過環境變數或既有的秘密管理
  機制注入。

## 測試哲學（Testing philosophy）

- 測試斷言行為（behavior），不斷言實作細節；重構不應該需要改測試，除非
  行為真的變了。
- 每個 acceptance criterion 都要有對應的測試可追溯（AC → test 對照表），
  不允許「大致測過」但沒有對應關係的測試。
- e2e 測試若因環境限制無法執行，必須在測試報告中明確聲明
  needs-e2e/no-e2e-needed 與理由，不可讓其在 CI 中無聲地被跳過或出錯。

## 範圍紀律（Scope discipline）

- 只實作 spec 明確要求的範圍；看得到未來會需要、但目前故事沒要求的功能，
  一律不做，留給未來的故事。
- 需求不明確時，列為 open question 交由人類決策，不可用「合理猜測」補上，
  即使猜測看起來顯而易見。
- Design 文件承諾下游故事會依賴的東西（共用函式、命名慣例、設定鍵）必須
  真的存在，不可只是文件上的意圖。

## 程式碼風格（Code style）

- 遵循既有程式庫中已建立的慣例（命名、錯誤處理形狀、目錄結構），優先於
  個人偏好；新模式只在既有慣例明顯不適用時才引入，並在 PR 中說明原因。
- 避免不必要的抽象層：三段類似的程式碼優於一個只為了「將來可能會用到」而
  設計的通用抽象。

## 視覺設計（Visual design）

- 涉及畫面的 Story（前台頁面、後台介面）一律依 `docs/design-system.md` 的
  色彩／字體／間距／斷點／元件規則執行，不逐頁自行判斷視覺樣式。細節規格
  以該文件為準，此處不重複內容，只作為指標。
