# 04 — 專案實例化指引

> 本框架是技術棧無關的**元框架**。本文件定義把它套用到一個具體專案的完整程序。
> 實例化可由人類執行，也可由 orchestrator 在人類監督下執行（每步產出讓人類確認）。

## 核心機制：project-profile.yaml

技術棧無關的關鍵：**框架文件與 agent 永不寫死任何具體指令**（如 `npm test`、`pytest`）。
所有專案特定資訊集中在專案 repo 根目錄的 `project-profile.yaml`（模板：`config/project-profile.template.yaml`）。
Agent 執行任何 build/test/lint 動作前，一律先讀 profile 取得指令。

Profile 涵蓋：技術棧宣告、指令集（build/test/lint/coverage）、品質門檻、程式碼慣例、目錄結構說明、部署資訊（模組用）。

## 實例化程序

### Phase A — 基礎設施（人類執行或確認，一次性）

```
A1. 建立 GitHub repo
    - 初始化 main 分支
    - 設定 branch protection：main 需 PR + status checks 通過才可合併
    - 準備 repo 權限的 token（供 Claude Code 的 gh CLI / MCP 使用）

A2. 建立 Jira 專案
    - 依 config/jira-workflow.yaml 設定：
      * 工單類型：Epic / Story / Sub-task / HUMAN-INPUT(可用 Task+label 代替) / BUG
      * 狀態機：Backlog / Refining / Awaiting Gate / Ready / In Progress /
                Testing / In Review / Done / Blocked
      * 自訂欄位：Agent Lock (text)、Lock Timestamp (datetime)、
                  Reopen Count (number)、Human Touch Count (number)、
                  Stage Entered At (datetime)
    - 若无法建自訂欄位（權限/方案限制），降級方案：以固定格式留言代替
      （格式：`[FIELD] AgentLock=orch-0708-a3f2`），agent 讀留言解析。
    - 連接 Atlassian 官方 Remote MCP server 到 Claude Code

A3. 建立 CI（GitHub Actions）
    - 依 profile 的指令建 workflow：lint → test → coverage 門檻檢查
    - CI 綠燈是 G2 的硬條件

A4. 複製框架到專案 repo
    - 將本框架 repo 的 .claude/、config/、templates/、docs/ 複製進專案 repo
      （或以 git submodule / subtree 引用框架 repo，便於框架升級）
    - 複製 config/project-profile.template.yaml → 專案根目錄 project-profile.yaml
```

### Phase B — Profile 填寫（orchestrator 可協助草擬，人類確認）

```
B1. 填寫 project-profile.yaml 全部必填欄位
B2. 驗證每條指令可實際執行（在空專案骨架上跑通 build/test/lint）
B3. 人類確認 profile → commit
```

### Phase C — 冒煙驗證（正式啟用前必做）

```
C1. 在 Jira Backlog 建一張刻意簡單的 Story（例如「加入 /health 端點回傳 200」）
C2. gates.yaml 全部設 manual
C3. /sdlc:start，讓框架完整走一遍：需求 → G1 → 開發 → 測試 → review → G2 → 合併
C4. 檢查驗證清單：
    [ ] 需求規格格式正確、G1 報告有產出
    [ ] 分支/commit/PR 命名符合規範、PR 關聯到 Jira
    [ ] 測試對照表存在、CI 綠燈
    [ ] review checklist 完整、G2 報告有產出
    [ ] 指標事件檔有記錄（metrics/events.jsonl）
    [ ] 合併後工單自動到 Done
C5. 冒煙通過 → 專案正式啟用；未通過 → 修正後重跑 C1-C4
```

## 多專案共用

- 框架 repo 作為上游；各專案 repo 引用之（submodule/subtree/複製）。
- 專案差異**只允許**存在於:project-profile.yaml、gates.yaml（各專案可有不同關卡策略）、模組啟用清單。
- 框架本體文件與 agent 定義若需專案特化 → 那是框架的缺陷，應回饋修改上游框架而非分叉。

## 既有專案（非綠地）套用補充

1. Phase B 額外產出「現況盤點」：既有測試狀態、lint 基線、目錄結構 → 寫入 profile 的 `conventions` 與 `notes`。
2. 若既有測試不綠：先開一個「基線修復」Epic 把測試修綠，再啟用框架（框架假設 main 永遠是綠的）。
3. 覆蓋率門檻從現況值起步，於 profile 註記逐步提高的計畫。
