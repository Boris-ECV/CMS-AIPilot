# 02 — 核心 SDLC 流程：狀態機與關卡

> 本文件定義 v1 核心流程：**需求 → 開發 → 測試 → Review**。
> 其他階段（架構設計、調研、部署、交付）以模組插入，插入點見 §8。

## 1. 工單類型與層級

| 類型 | 用途 | 由誰建立 |
|------|------|----------|
| **Epic** | 一個功能領域 / 里程碑 | 人類或需求分析代理（經人類確認） |
| **Story** | 一個可獨立交付的最小價值單位；**流程的主要載體** | 需求分析代理 |
| **Sub-task** | Story 內單一階段的工作項（可選，大 Story 才用） | Orchestrator |
| **HUMAN-INPUT** | Agent 卡住需要人類回答的問題 | 任何 agent |
| **BUG** | 測試或 review 發現、無法在原 Story 內修的缺陷 | 測試 / review 代理 |

## 2. Story 狀態機

```
 Backlog ──▶ Refining ──▶ [G1] ──▶ Ready ──▶ In Progress ──▶ Testing ──▶ In Review ──▶ [G2] ──▶ Done
    │            │                    │            │              │            │
    └────────────┴────────────────────┴────────────┴──────────────┴────────────┴───▶ Blocked（任何狀態可進入）
```

| 狀態 | 意義 | 負責 agent |
|------|------|-----------|
| Backlog | 原始想法，未細化 | — |
| Refining | 需求分析中 | requirements-analyst |
| Ready | 需求已定稿（過 G1），可開發 | — |
| In Progress | 開發中 | developer |
| Testing | 測試撰寫 / 執行中 | tester |
| In Review | 程式碼審查中 | reviewer |
| Done | 已合併（過 G2） | — |
| Blocked | 卡住，等待外部輸入 | orchestrator 追蹤 |

（Jira 端的具體 workflow 與欄位定義見 `config/jira-workflow.yaml`。）

## 3. 各階段規格

每個階段用同一結構定義：**進入條件 → 執行者與動作 → 產出 → 退出條件（機器可判定）**。
退出條件是本框架品質保證的核心——**全部通過才能轉換狀態，無例外**。

### 3.1 需求階段（Backlog → Refining → Ready）

- **進入條件**：Backlog 中有 Story（哪怕只有一句話）。
- **執行者**：requirements-analyst。
- **動作**：依 `templates/requirement-spec.md` 產出需求規格，寫入工單 description；含：使用者故事、驗收條件（Gherkin 格式 Given/When/Then）、範圍外事項、依賴、開放問題。
- **歧義處理**：需求有歧義且無法從 Epic 上下文推斷 → 開 HUMAN-INPUT 工單列出具體問題與建議選項，Story 轉 Blocked。**禁止自行假設補完需求。**
- **產出**：定稿的需求規格（在工單上）。
- **退出條件（→ G1 gate）**：
  - [ ] 需求規格含 ≥1 條 Gherkin 驗收條件
  - [ ] 「範圍外」章節非空（哪怕寫「無」也要明示）
  - [ ] 開放問題章節為空（全部已解決）
  - [ ] 預估規模 ≤ 1 個開發日；超過 → 必須先拆分（見 §6）

### 3.2 開發階段（Ready → In Progress → Testing）

- **進入條件**：過 G1、被 orchestrator 認領並鎖定。
- **執行者**：developer。
- **動作**：
  1. 從 main 建分支 `story/<KEY>-<slug>`
  2. 讀 project-profile.yaml 取得 build/test/lint 指令
  3. 實作，遵守 profile 中宣告的 conventions
  4. 本地跑 lint + 既有測試全綠才 commit；commit message 含 Jira key
  5. 在工單留言記錄：分支名、實作摘要、任何偏離需求的技術決策及理由
- **退出條件**：
  - [ ] 分支存在且含 commit
  - [ ] `profile.commands.lint` 執行通過
  - [ ] `profile.commands.test` 既有測試全綠
  - [ ] 工單留言含實作摘要

### 3.3 測試階段（Testing）

- **執行者**：tester（**與 developer 是不同的 subagent 委派，context 隔離**——tester 不知道 developer 的思路，只看需求規格與程式碼，這是刻意設計）。
- **動作**：
  1. 對照需求規格的每條 Gherkin 驗收條件撰寫自動化測試
  2. 執行全部測試；失敗 → 在工單留言記錄失敗細節，狀態退回 In Progress（developer 修復；此為一次「reopen」，記入指標）
  3. 檢查覆蓋率是否達 profile 門檻
  4. **明確宣告本張 Story 是否需要 e2e 覆蓋**：本 Story 是否新增/變更任何使用者可見的 UI 行為（頁面、表單、互動）？在留言中一句話寫明「需要 e2e」或「不需要 e2e」+ 理由（例如「純後端 API 變更，無 UI 介面」）。**需要時**：`tests/e2e/` 下必須有本 Story 新增/變更的 Playwright 測試，且**真的被執行、通過**，不可只是 `pytest.mark.skip` 佔位。
- **退出條件**：
  - [ ] 每條驗收條件至少對應一個自動化測試（在留言中列出對照表）
  - [ ] 全部測試通過
  - [ ] 覆蓋率 ≥ `profile.quality.coverage_threshold`
  - [ ] e2e 宣告存在（需要/不需要 + 理由）；若宣告「需要」，對應的非 skip Playwright 測試已存在且通過

### 3.4 Review 階段（In Review）

- **執行者**：reviewer（唯讀權限，不能改 code——發現問題只能回報）。
- **動作**：
  1. developer（由 orchestrator 指示）先開 PR，description 用 `templates/pr-description.md`
  2. reviewer 依 `templates/review-checklist.md` 逐項檢查，結論寫在工單留言：`APPROVE` 或 `REQUEST_CHANGES` + 具體項目
  3. REQUEST_CHANGES → 退回 In Progress（記一次 reopen），修復後重走測試 → review
- **退出條件（→ G2 gate）**：
  - [ ] PR 存在且 CI 全綠
  - [ ] reviewer 留言結論為 APPROVE
  - [ ] review checklist 每項都有明確勾選記錄

## 4. Gate（關卡）機制

Gate 是狀態轉換上的可切換閘門。定義於 `config/gates.yaml`。

| Gate | 位置 | 守護什麼 |
|------|------|----------|
| **G1** | Refining → Ready | 需求定稿 |
| **G2** | In Review → Done（merge） | 合併到 main |
| G3 | （模組：deployment）Done → Deployed | 部署到環境 |

**每個 gate 兩種模式**：

- **`manual`**：orchestrator 驗證完自動條件後，將工單置於 `Awaiting Gate`，用 `templates/gate-report.md` 產出審查報告貼在工單留言，並@人類。人類在工單留言 `GATE APPROVED` 或 `GATE REJECTED: <理由>` 放行/駁回。
- **`auto`**：自動條件全數通過即放行，orchestrator 留言記錄放行依據（逐項條件的驗證結果）。

**切換方式**：人類修改 gates.yaml 並 commit。Agent 無權修改此檔。從全 manual 漸進到全 auto 的建議路徑見 docs/06 §5。

**駁回處理**：GATE REJECTED → 工單退回該階段起點，駁回理由成為該階段的新輸入。

## 5. Blocked 協議

- 進入 Blocked 必須同時：留言寫明阻塞原因 + 需要什麼才能解除 + 關聯的 HUMAN-INPUT 工單（若因缺人類輸入）。
- Orchestrator 每個 session 檢視所有 Blocked 工單：可解除就解除；Blocked 超過 3 天的工單必須出現在 session 報告的醒目位置。

## 6. 拆分規則（Story 過大時）

規模預估 > 1 開發日的 Story：
1. requirements-analyst 將其拆成多個子 Story（各自獨立可交付、各自完整需求規格），原 Story 轉為 Epic 或保留為追蹤用父單。
2. 拆分後的依賴關係用 Jira link（`blocks` / `is blocked by`）表達；orchestrator 排程時遵守依賴序。
3. **寧可拆太細，不可太粗**——小工單是 Sonnet 級執行可靠性的最大保障。

## 7. Escalation（升級到高階模型）

同一工單在同一階段**連續失敗 3 次**（測試修不好、review 反覆退回同類問題）：
1. Orchestrator 停止重試，整理失敗史（3 次各自的嘗試與失敗原因）寫入工單留言。
2. 依 models.yaml 的 `escalation` 設定委派高階模型子代理做一次診斷（產出診斷報告與修復方向，不直接大改）。
3. 高階模型使用一次即記錄一筆指標事件（`escalation_used`）。
4. 診斷後仍失敗 → 轉 Blocked + HUMAN-INPUT。**絕不無限重試。**

## 8. 模組插入點

核心狀態機預留以下 hook，模組藉此插入（規格見 docs/05）：

| Hook | 時機 | 範例模組 |
|------|------|----------|
| `pre_refine` | Story 進入 Refining 前 | research（調研） |
| `post_ready` | 過 G1 之後、開發之前 | architecture（架構設計）、deep-decomposition（深度拆解） |
| `post_done` | 過 G2 之後 | deployment（部署）、delivery（交付文件） |
| `on_blocked` | 進入 Blocked 時 | 通知整合 |
