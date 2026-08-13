# 07 — 指標與回顧機制

> 目的：讓「框架運作得好不好」變成可觀測的事實，而非感覺；並提供漸進開放 auto gate 的數據依據。

## 1. 指標事件（event sourcing）

所有 agent 在關鍵動作發生時，向專案 repo 的 `metrics/events.jsonl` **追加**一行 JSON 事件（appendonly，不修改歷史）。事件同時也是稽核軌跡。

### 事件 schema

```json
{
  "ts": "2026-07-08T10:23:45Z",        // ISO 8601 UTC
  "event": "stage_transition",          // event type, see below
  "ticket": "PROJ-42",
  "agent": "orch-0708-a3f2",
  "data": { }                           // event-specific payload
}
```

### 核心事件類型

| event | data 內容 | 由誰發 |
|-------|-----------|--------|
| `session_start` / `session_end` | tokens_estimate, tickets_touched | orchestrator |
| `stage_transition` | from, to | orchestrator |
| `gate_review` | gate, mode(auto/manual), result(approved/rejected), criteria_results | orchestrator |
| `reopen` | stage, reason_summary | orchestrator |
| `human_intervention` | kind(gate_reject/human_input_answer/manual_fix), ticket | orchestrator |
| `escalation_used` | reason, outcome | orchestrator |
| `blocked` / `unblocked` | reason | orchestrator |
| `error` | summary | 任何 agent |

模組可依 module.yaml 宣告新增事件類型，schema 必須相容。

### 如何寫入（避免觸發 Bash 安全啟發式）

**不要**用 `cat >> metrics/events.jsonl << 'EOF' ... EOF` 這種把整段 JSON 直接寫進 Bash
指令文字的方式——JSON 本身的 `{`+引號組合會被 Claude Code 的指令安全檢查誤判為
「expansion obfuscation」，每次都跳出確認提示，且這不是 `permissions.allow` 能關掉的
（那是不同層的檢查）。

正確做法：**先用 Write 工具**把單行事件 JSON 寫進暫存檔**固定路徑
`.tmp/event.jsonl`**（每次覆蓋寫入同一個檔名，不要每次換一個新檔名——
檔名固定，`permissions.allow` 才能用一條字首比對規則長期涵蓋，不會每次
因為檔名不同又要重新累積），**再用 Bash 執行純淨的
`cat .tmp/event.jsonl >> metrics/events.jsonl`**——這樣 Bash 指令文字本身
不含任何大括號/引號組合，從源頭避開誤判，不需要每次跟安全檢查交涉。

⚠️ 兩個容易讓 `permissions.allow` 規則對不上的坑，都是這次冒煙測試實測
踩出來的，不是憑空推測：

1. **Bash 指令實際執行時，Claude Code 常會自動補上 `cd "<專案根目錄的絕對
   路徑>" && ` 前綴**（例如 `cd "D:\Programming\Projects\CMS-AIPilot" &&
   cat .tmp/event.jsonl >> metrics/events.jsonl`），不是你在委派指令裡打的
   單純 `cat ...`。寫 `permissions.allow` 規則時，**要用實際跳出來的確認
   提示裡逐字顯示的完整指令去對**，不要只憑自己以為的指令去猜——這是
   前幾輪一直對不上的真正原因，不是萬用字元語意的問題。
2. `permissions.allow` 萬用字元 `*` 只在字尾生效（純字首比對），寫在指令
   文字中間的 `*` 會被當成字面字元、不會展開比對。要放行「固定前綴 + 後面
   接不同後綴指令」的情境，規則要把固定部分（含 `cd "..." && ` 前綴）完整
   照字面寫、只在最後面加一個 `*`。

實務上最可靠的做法：**跳出確認提示時，直接看提示裡顯示的完整指令文字，
複製貼上去寫規則**，不要憑印象重建指令字串。

寫入後可視需要刪除暫存檔（非必要，下次覆蓋寫入即可）。

## 2. 派生指標（週回顧時由 reporter 聚合）

| 指標 | 定義 | 健康方向 |
|------|------|----------|
| **一次通過率** | reopen=0 就到 Done 的 Story ÷ 完成 Story 數 | ↑，目標 ≥ 70% |
| **人工介入率** | human_intervention 次數 ÷ 完成 Story 數 | ↓（gate 全 manual 期間扣除例行放行） |
| **階段停留時間** | 各狀態的中位停留時長 | 發現瓶頸用 |
| **Gate 駁回率** | rejected ÷ (approved+rejected)，分 gate 統計 | ↓；連續低駁回是開 auto 的依據（docs/06 §5） |
| **Escalation 頻率** | escalation_used ÷ 完成 Story 數 | 穩定低值；飆高=Story 太大或需求品質差 |
| **Silent failure 檢查** | 存在 >3 天無事件且非 Done/Backlog 的工單數 | **必須為 0**，>0 直接列入報告紅色區 |
| **Token 效率** | session tokens_estimate ÷ 該 session 完成的階段轉換數 | 趨勢觀察 |

## 3. 週回顧流程

每週（或每完成一個 Epic）由人類觸發 `/sdlc:report weekly`：

1. reporter（Haiku）聚合 events.jsonl → 產出 `metrics/retro-<date>.md`（模板：templates/retro-report.md）
2. 內容：指標表 + 趨勢對比上週 + 紅色區（silent failure、長期 Blocked、escalation 失敗）+ **流程改善建議**（例：某類 Story 反覆 reopen → 建議需求模板加一節）
3. 人類裁決建議 → 採納的落實為文件/config 修改並 commit
4. 回顧報告本身入 git，形成框架演化史

## 4. 「運作良好」的判定基準（v1 初始值，可調）

- 一次通過率 ≥ 70% 且趨勢不降
- Silent failure = 0
- 人工介入率逐週下降（排除 manual gate 例行放行）
- 每張 Story 的端到端時間中位數穩定或下降
- 高階模型用量佔比 < 5%（token 估計）

連續 4 週達標 → 框架進入穩定狀態，可依 docs/06 §5 推進 auto gate。
