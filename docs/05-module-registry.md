# 05 — 可插拔模組規格（Module Registry）

> 核心流程刻意最小化。所有其他能力——調研、架構設計、深度拆解、部署、交付——以模組形式插拔。
> 本文件定義模組的**介面契約**：符合契約的模組可以獨立開發、獨立啟停，不動核心。

## 1. 模組是什麼

一個模組 = `modules/<module-name>/` 目錄，包含：

```
modules/<module-name>/
├── module.yaml          ← 模組宣告（必要，格式見 §2）
├── README.md            ← 模組說明：目的、流程、退出條件（繁中）
├── agents/              ← 模組帶入的 subagent 定義（啟用時複製/連結到 .claude/agents/）
├── templates/           ← 模組專用模板
└── config.template.yaml ← 模組設定模板（若有）
```

## 2. module.yaml 格式

```yaml
# Module manifest — all keys in English, values may be Chinese where noted
name: architecture              # unique, lowercase-hyphen
version: 1.0.0
framework_min_version: 1.0.0
summary: "Adds an architecture-design stage after G1"   # one line

# Where this module attaches to the core state machine (see docs/02 §8)
hooks:
  - hook: post_ready            # pre_refine | post_ready | post_done | on_blocked
    action: insert_stage        # insert_stage | run_task | notify
    stage:                      # required when action=insert_stage
      name: Designing
      agent: architect          # must exist in agents/
      exit_criteria:            # machine-checkable, same discipline as core stages
        - "Design doc exists on ticket following module template"
        - "All ADR items resolved or escalated to HUMAN-INPUT"
      gate:                     # optional: module may add its own gate
        id: G1b
        default_mode: manual

# Agents this module registers
agents:
  - file: agents/architect.md
    model_tier: sonnet          # must respect config/models.yaml tiers

# Jira additions (states, fields, labels) — instantiation script reads this
jira:
  states: [Designing]
  labels: [module-architecture]

# Optional: webhook triggers this module supports (framework v1: documented only)
triggers: []

# Metrics events this module emits (must follow docs/07 event schema)
metrics_events: [design_completed, adr_escalated]
```

## 3. 啟用 / 停用程序

**啟用**：
1. 人類決定啟用（模組變更一律是人類決策）
2. 依 module.yaml 的 `jira` 段更新 Jira 設定（新增狀態/標籤）
3. 複製 `agents/` 內容到專案 `.claude/agents/`
4. 若模組有 gate → 在 gates.yaml 加入該 gate 條目
5. 在專案根目錄 `modules-enabled.yaml` 登記模組名與版本
6. 跑該模組 README 中定義的冒煙驗證

**停用**：反向操作；**進行中的工單先跑完該模組階段**再停用（或人工移出該狀態）。

**Orchestrator 每次 bootstrap 讀 `modules-enabled.yaml`**，據此知道狀態機上多了哪些階段與 gate。

## 4. 模組設計紀律（與核心相同）

- 每個新階段必須有機器可判定的退出條件
- 模組 agent 遵守工單協議（鎖定、留言格式、指標事件）
- 模組不得修改核心文件與核心 agent；只能透過 hook 插入
- 模組間不得互相依賴（如需組合，建立一個 composite 模組明示宣告）

## 5. 模組狀態

| 模組 | Hook | 摘要 | 狀態 |
|------|------|------|------|
| **architecture（架構設計）** | post_ready | 每張過 G1 的 Story 先產出 SA/SD 設計文件（介面契約、資料模型、關鍵決策）才進 Ready，見 `modules/architecture/`。 | **已實作**（首個由人類使用情境驅動、實際完成的模組；原始規劃是「只有大型 Story」，此實作放寬為全部 Story，見模組 README 的差異說明） |
| **research（調研）** | pre_refine | Story 涉及未知領域時先產出調研報告（技術選型比較、可行性、風險），作為需求階段輸入。高階模型候選使用場景。 | 規劃中 |
| **deep-decomposition（關鍵模組深度拆解）** | post_ready | 對關鍵複雜模組做深度拆解：內部結構、依賴圖、實作順序、風險點。輸出成為多個子 Story。 | 規劃中 |
| **deployment（部署）** | post_done | G3 gate + 部署執行 + 部署後驗證（health check、rollback 條件）。 | 僅骨架（`modules/deployment-skeleton/`，範例用，不可啟用） |
| **delivery（交付）** | post_done | 交付文件生成：release notes、使用者文件、變更摘要（Haiku 為主）。 | 規劃中 |
| **notification（通知）** | on_blocked | Blocked / gate 待放行時通知人類（Slack/email）。 | 規劃中 |

每個模組未來由執行模型依本規格 + `modules/_registry/module-development-guide.md` 開發，人類驗收後啟用。

## 6. 模組開發流程（給未來的執行模型）

1. 人類建立「開發 X 模組」的 Epic
2. 框架自己吃自己的狗糧:模組開發本身走核心 SDLC 流程（需求→開發→測試→review）
3. 模組的「測試」= 在沙盒專案跑通其冒煙驗證
4. G2 過後由人類執行啟用程序
