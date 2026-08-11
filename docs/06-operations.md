# 06 — 監督者手冊（給人類）

> 你是這套系統唯一的人類。本文件是你的日常操作指南。

## 1. 首次啟動

1. 依 docs/04 完成實例化（Phase A/B/C，含冒煙驗證）
2. 確認 gates.yaml 全部 `manual`（初期建議）
3. 在專案 repo 開 Claude Code，輸入 `/sdlc:start`
4. Orchestrator 會跑 bootstrap → 報告看板現況 → 開始工作
5. Session 結束時你會收到 session 報告（工單進度、gate 待放行、Blocked、token 用量估計）

## 2. 你的日常介面

你只需要三個介面：

| 介面 | 用途 |
|------|------|
| **Jira 看板** | 看整體進度；放行 gate（留言 `GATE APPROVED` / `GATE REJECTED: 理由`）；回答 HUMAN-INPUT 工單（直接在工單留言回答，狀態改回原階段） |
| **Claude Code session** | 啟動工作循環（`/sdlc:start`）；下達新方向；即時介入 |
| **報告** | session 報告（每次 session 結束）＋週回顧報告（metrics/ 目錄） |

### 常用指令

| 指令 | 功能 |
|------|------|
| `/sdlc:start` | Bootstrap + 進入主循環 |
| `/sdlc:status` | 只看現況報告，不做事 |
| `/sdlc:gate` | 只處理待放行 gate（驗證 auto gate、整理 manual gate 報告） |
| `/sdlc:recover` | 只跑恢復程序（清殘鎖、盤點半成品分支） |
| `/sdlc:report` | 產出 session 報告 / 觸發週回顧 |

## 3. 放行一個 gate（manual 模式）

1. 工單進入 `Awaiting Gate`，留言區有 gate 報告（自動條件逐項結果 + 產出摘要 + agent 的風險提示）
2. 你檢視報告（G1 看需求規格；G2 看 PR diff + review 結論）
3. 留言 `GATE APPROVED` → 下個 session orchestrator 會推進
   或 `GATE REJECTED: <具體理由>` → 工單退回，你的理由成為修正輸入
4. 想加速：放行後直接在 Claude Code 說「處理剛放行的 gate」

## 4. 介入的時機與方式

| 情境 | 動作 |
|------|------|
| HUMAN-INPUT 工單 | 盡快回答——這是 agent 唯一主動求助的管道，回應速度決定吞吐量 |
| 工單 Blocked > 3 天 | Session 報告會標紅;檢視原因，通常是需求問題或環境問題 |
| 同一工單 reopen ≥ 3 | Escalation 已自動觸發；若高階模型診斷仍失敗，考慮親自看或把 Story 拆更小 |
| Agent 行為偏離 | 直接在 session 中糾正，並且**把糾正沉淀為文件修改**（改 CLAUDE.md / agent 定義 / 模板），否則下個 session 會重犯 |
| 想改需求方向 | 改 Jira 工單（Backlog 增刪、Epic 描述），不要只口頭告訴 agent——P1 原則 |

## 5. 從 manual 漸進到 auto 的建議路徑

```
階段 0（啟用初期）   ：G1 manual、G2 manual
階段 1（G1 連續 10 次放行無駁回）：G1 → auto，G2 manual
階段 2（G2 連續 20 次放行無駁回，且 CI 覆蓋率門檻已達標穩定）：G2 → auto
                     此時 = 「全自動跑 SDLC，人只看報告」
任何階段出現嚴重誤放 → 立即退回 manual，檢討 auto 條件是否要加嚴（改 gates.yaml 的 criteria）
```

切換方式：改 `config/gates.yaml` 的 `mode` 欄位，commit。只有你能改這個檔。

## 6. 成本控管

- `config/limits.yaml` 定義每 session 的工作量上限與收尾門檻——先從保守值開始，觀察幾個 session 的實際消耗再調。
- Session 報告含 token 用量估計與高階模型使用次數；週回顧含趨勢。
- 成本異常的常見原因：Story 太大（拆！）、reopen 循環（看 escalation 是否正常觸發）、bootstrap 讀了太多非必要文件（檢查 CLAUDE.md 的 bootstrap 清單）。
- Rate limit 撞頂：limits.yaml 的 `pacing` 段有退避策略；長期撞頂 → 降低 WIP 上限。

## 7. 排錯速查

| 症狀 | 檢查 |
|------|------|
| Agent 找不到工單 | Jira MCP 連線？JQL 中的專案 key 正確？ |
| 工單卡在 Awaiting Gate | manual gate 等你放行；auto gate 看留言中哪條條件未過 |
| 兩個 agent 改同一工單 | 鎖協議被跳過——檢查 agent 是否照 docs/01 §4 執行，通常是委派指令漏了鎖定步驟 |
| PR 開了但 CI 沒跑 | GitHub Actions workflow 檔在 main 上嗎？branch protection 的 status check 名稱對嗎？ |
| Session 中途死掉 | 直接重開 `/sdlc:start`——恢復程序會處理殘局，這是設計保證 |
| Jira MCP 整個掛掉 | 降級方案：用 Jira REST API + curl（token 放環境變數 `JIRA_API_TOKEN`）。指示 orchestrator「Jira MCP 不可用，改用 REST API 降級模式」，它應以相同協議操作 |
| Story 卡在 In Review 前、orchestrator 回報缺 GitHub 憑證 | 新環境第一次 `/sdlc:start` 前，先確認 `gh auth status` 已登入正確帳號（或 `GITHUB_TOKEN` 已設）；沒裝就先 `gh auth login`，省一次 Blocked 循環 |
| 平行委派的 developer/tester 回報工作目錄被覆蓋、未 commit 變更消失 | 檢查委派時是否漏了 `isolation: "worktree"`（見 docs/01 §6）——平行委派多張票時每個都要獨立 worktree，共用同一份 checkout 會互踩 |
| Bash 指令一直卡在確認提示、且選單沒有「always allow」選項 | 通常是內容安全啟發式（例如 JSON 內文的大括號+引號組合、或 `source` 讀檔執行）觸發，不是 `permissions.allow` 能關掉的。改寫指令避開觸發模式，不要硬闖：本機跑 Python venv 指令**不要用** `source .venv/Scripts/activate && <cmd>`，改直接呼叫 `.venv/Scripts/python.exe -m <cmd>`（例如 `.venv/Scripts/python.exe -m pytest -q`），效果相同且不會觸發此檢查（僅本機開發環境會遇到，CI 全域安裝不受影響） |

## 8. 框架本身的維護

- 框架文件的任何修改走 git（框架 repo 或專案內副本），commit message 說明動機。
- 每次週回顧的「流程改善建議」由你裁決是否採納；採納 = 修改對應文件。
- 框架升級（上游有新版）：看 CHANGELOG → 在冒煙專案驗證 → 再套用到正式專案。
