# 01 — 框架架構與協調模型

## 1. 總體圖像

```
                        ┌─────────────────────────────┐
                        │        人類監督者            │
                        │  （放行 gate / 回答 HUMAN-  │
                        │    INPUT / 看報告）          │
                        └──────────┬──────────────────┘
                                   │ Jira UI / 報告
                                   ▼
   ┌───────────────────────────────────────────────────────┐
   │                    Jira（唯一事實來源）                 │
   │   Epic / Story / Sub-task ・ 狀態機 ・ 自訂欄位 ・ 留言  │
   └──────────┬────────────────────────────────────────────┘
              │ Atlassian Remote MCP
              ▼
   ┌──────────────────────────┐        ┌──────────────────┐
   │  Orchestrator（主代理）    │───────▶│  GitHub          │
   │  Claude Code main session │  PR/CI │  repo + Actions  │
   └───┬──────┬──────┬────┬───┘        └──────────────────┘
       ▼      ▼      ▼    ▼
   ┌──────┐┌──────┐┌─────┐┌────────┐┌─────────┐
   │需求分 ││開發  ││測試 ││Reviewer││Reporter │  ← 子代理
   │析代理 ││代理  ││代理 ││(唯讀)  ││(Haiku)  │
   └──────┘└──────┘└─────┘└────────┘└─────────┘
```

## 2. 三層資訊架構

| 層 | 載體 | 內容 | 存活期 |
|----|------|------|--------|
| **持久層** | Jira 工單 + Git repo | 需求、決策、程式碼、狀態、指標事件 | 永久 |
| **會話層** | Orchestrator context | 目前看板快照、本次 session 的計畫 | 單一 session |
| **任務層** | Subagent context | 單一工單的執行細節 | 單一委派 |

**規則：任何需要跨 session 存活的資訊，必須在產生的當下寫入持久層。** 這是整個框架容錯能力的來源——orchestrator 隨時可以死掉重來。

## 3. Agent 間協調：為什麼不讓 agent 直接對話

Agent 之間**只透過 Jira 工單協調**，理由：

1. **可恢復**：對話狀態存在 context 裡，context 會消失；工單不會。
2. **可稽核**：人類能在看板上看到完整決策鏈。
3. **降低對模型能力的要求**：Sonnet 級模型跟隨「讀工單→做事→寫工單」的機械流程，比維護多方對話狀態可靠得多。
4. **可插拔**：新模組的 agent 只要遵守工單協議就能加入，不需要認識其他 agent。

## 4. 工單鎖定協議（防止搶單）

未來若有多個 orchestrator session 並行（或 webhook 觸發的 agent），用以下協議防止兩個 agent 處理同一張工單：

```
CLAIM（認領）:
  1. 讀取工單，確認 Agent Lock 欄位為空（或鎖已過期 > 60 min）
  2. 寫入 Agent Lock = "<agent-id>"（格式：orch-<日期>-<隨機4碼>，session 啟動時自行生成）
     寫入 Lock Timestamp = 現在時刻（ISO 8601）
  3. 等 5 秒後重新讀取，確認 Agent Lock 仍是自己的 id
     （簡易樂觀鎖：若被別人覆寫，代表撞單，放棄並選下一張）
  4. 確認成功 → 將工單 assignee 設為自己，開始工作

HEARTBEAT（心跳）:
  - 長時間任務中，每完成一個子步驟就更新 Lock Timestamp

RELEASE（釋放）:
  - 完成或失敗時：清空 Agent Lock，留言記錄結果

RECLAIM（回收）:
  - 任何 orchestrator 發現 Lock Timestamp 超過 60 分鐘的鎖 → 視為死鎖，
    清除並留言 [RECOVERY]，工單狀態退回該階段起點
```

單一 orchestrator 情境下此協議依然要遵守（成本極低），確保未來擴展到多 session 時不需改流程。

## 5. 觸發模式

框架支援兩種啟動方式，v1 以 (a) 為主：

**(a) 人工啟動 session（v1 預設）**
人類開 Claude Code → `/sdlc:start` → orchestrator 跑 bootstrap → 進入主循環直到 token 預算用盡或無工作可做 → 產出 session 報告後乾淨結束。

**(b) Webhook 觸發（預留擴充）**
Jira Automation 規則偵測特定狀態變化（例如工單進入 `Ready`）→ 呼叫外部端點 → 以 headless 模式啟動 Claude Code（`claude -p "<觸發指令>"`）處理單一事件。模組介面已預留 `triggers` 欄位（見 docs/05）。**注意**：webhook 模式下每次啟動都是冷啟動，bootstrap 成本高，只適合單一、明確、小顆粒的事件處理（如：gate 自動驗證、報告生成），不適合開放式開發工作。

## 6. GitHub 整合模型

- **一張 Story = 一個分支 = 一個 PR**。分支命名：`story/<JIRA-KEY>-<slug>`。
- PR description 必含 Jira key(讓 Jira smart link 自動關聯）與驗收條件 checklist。
- CI（GitHub Actions）是 P2「判斷外化」的執行者：lint、測試、覆蓋率門檻都在 CI 定義，agent 不能繞過。
- CI 設定本身由實例化流程建立（docs/04），框架只規定「必須存在且 gate 依賴它」。
- **平行委派多個 developer/tester 時，每個委派必須各自跑在獨立的 git worktree**（Claude Code Agent 工具的
  `isolation: "worktree"`），不可共用同一份本機 checkout。原因：多個 subagent 各自在同一顆工作目錄
  `git checkout` 不同分支時會互相踩——A 尚未 commit 的變更可能被 B 的 checkout 直接覆蓋掉，即使兩者最終
  都能用 `git stash`／`cherry-pick` 自行搶救回來，也不該讓這種競態發生。單一委派（一次只處理一張票）不受影響，
  只有「同時」委派多張票的開發/測試工作時才需要 worktree 隔離。

## 7. 模型分層架構（成本控制）

詳細路由在 `config/models.yaml`，架構原則：

```
決策密度高、錯誤代價高  ──▶  高階模型（限量使用，逐次記錄用量）
  例：需求歧義裁決、架構級 trade-off、連續失敗 3 次的疑難排解

主流程                  ──▶  Sonnet
  例：orchestrator、開發、測試、review

例行、格式化、彙整       ──▶  Haiku
  例：狀態同步、報告彙整、指標聚合、工單格式檢查
```

Orchestrator 委派時依 models.yaml 的 routing 表選擇子代理（子代理定義檔已固定 model 欄位），**不得**自行升級模型層級；需要高階模型時走 escalation 流程（docs/02 §7）。

## 8. 安全邊界

- 子代理工具權限最小化：reviewer/analyst 類唯讀（Read/Grep/Glob），只有 developer/tester 有寫入與 Bash。
- 憑證（Jira token、GitHub token）由 Claude Code 的 MCP 設定與環境變數管理，**永不**寫入工單、留言、commit。
- `main` 分支受 GitHub branch protection 保護：必須經 PR + CI 綠燈 + gate 放行。Agent 沒有繞過權限——這是刻意的，防線在平台層而非模型自律。
