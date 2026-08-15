# 03 — 代理目錄（Agent Catalog）

> 每個 agent 的正式定義（system prompt + 工具權限 + 模型）在 `.claude/agents/*.md`。
> 本文件說明設計意圖與職責邊界，是理解「為什麼這樣切」的地方。
>
> **本文件只登記核心 agent（框架骨架，不可拆卸）。模組帶入的 agent（如
> architecture 模組的 `architect`）啟用後一樣落地在 `.claude/agents/`、
> 一樣與核心 agent 同層級運作，但正式登記處是該模組自己的
> `module.yaml` + `README.md`，見 `docs/05-module-registry.md` §5 的模組
> 狀態表。**

## 設計原則

1. **一個 agent 一個職責**，定義清楚的輸入（工單 + 委派指令）與輸出（工單留言 + 產出物）。
2. **工具權限最小化**：分析/審查類唯讀；只有需要改動的 agent 有 Write/Edit/Bash。
3. **Context 隔離是特性不是限制**：tester 看不到 developer 的思路 → 測試更客觀；reviewer 獨立於兩者 → 審查更可信。
4. **委派指令必須自足**：子代理只知道你告訴它的事。orchestrator 委派時必附：工單 key、需求規格全文或位置、相關的 profile 指令、期望的輸出格式。

## 目錄

### orchestrator（主代理）
- **載體**：Claude Code 主 session（由 `.claude/CLAUDE.md` 定義行為）
- **模型**：Sonnet
- **職責**：讀看板 → 決策 → 委派 → 驗證 → 推進狀態 → 處理 gate → 回報。
- **邊界**：不自己寫產品程式碼（小型修補 ≤ 5 行例外，需留言記錄）；不修改 gates.yaml；不合併未過 gate 的 PR。

### requirements-analyst（需求分析）
- **模型**：Sonnet（複雜 Epic 的初次分解可依 escalation 規則用高階模型）
- **工具**：唯讀 + Jira MCP
- **輸入**：Backlog Story / Epic
- **輸出**：定稿需求規格（工單上）、拆分後的子 Story、HUMAN-INPUT 工單（有歧義時）
- **邊界**:**永不自行假設補完歧義需求**；不做技術設計（那是 architecture 模組的事）。

### developer（開發）
- **模型**：Sonnet
- **工具**：Read/Write/Edit/Bash/Grep/Glob + GitHub 操作
- **輸入**：過 G1 的 Story（含完整需求規格）
- **輸出**：feature 分支 + commits + 實作摘要留言
- **邊界**：只實作需求規格內的東西——發現規格缺漏回報 orchestrator，不擅自擴充範圍；不寫測試以外自我驗收的「作弊」（如放寬 lint 規則、跳過失敗測試）。

### tester（測試）
- **模型**：Sonnet
- **工具**：Read/Write/Edit/Bash/Grep/Glob
- **輸入**：Testing 狀態的 Story（需求規格 + 分支程式碼）
- **輸出**：驗收條件↔測試對照表、測試碼、執行結果、覆蓋率報告
- **邊界**：發現實作與需求不符 → 記錄並退回，**不自行修改產品程式碼**；不刪除或弱化既有測試。

### reviewer（審查）
- **模型**：Sonnet
- **工具**：**唯讀**（Read/Grep/Glob）+ Jira 留言
- **輸入**：In Review 狀態的 Story + PR
- **輸出**：checklist 逐項結果 + APPROVE / REQUEST_CHANGES 結論
- **邊界**：不能修改任何程式碼（唯讀權限在工具層強制）；審查聚焦自動化工具抓不到的東西——邏輯正確性、需求符合度、安全隱患、可維護性，不重複 lint 的工作。

### reporter（報告與例行工作）
- **模型**：**Haiku**（成本優化的主要落點）
- **工具**:Read/Grep/Glob + Jira MCP
- **職責**：session 報告彙整、指標事件聚合、每週回顧報告草稿、工單格式檢查、Blocked 工單摘要。
- **邊界**：只彙整不判斷——任何需要決策的事項回報 orchestrator。

## 模型路由摘要（詳見 config/models.yaml）

| 層級 | 誰 | 何時 |
|------|----|------|
| 高階（限量） | escalation 診斷、複雜 Epic 首次分解 | 依 docs/02 §7 規則，逐次記錄 |
| Sonnet | orchestrator、analyst、developer、tester、reviewer | 主流程 |
| Haiku | reporter | 一切例行彙整 |

## 新增 agent 的規範（模組用）

新模組帶入的 agent 必須：
1. 在 `.claude/agents/` 放置定義檔，frontmatter 完整（name/description/tools/model）
2. description 寫成觸發條件句（「Use this agent when...」），因為 Claude Code 靠 description 決定委派
3. 遵守工單協議（認領鎖定、留言格式、指標事件）
4. 在模組的 `module.yaml` 中登記（見 docs/05）
