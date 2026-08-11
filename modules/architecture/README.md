# architecture 模組

> 掛在 `post_ready` hook——G1(需求核准)之後、Story 進 `Ready`(可開發)之前,
> 插入一個 `Designing` 階段,強制每張 Story 在寫程式前先有 SA/SD 設計文件。

## 目的

需求規格(G1 產出)講的是「要什麼」,不講「怎麼做」。沒有這個模組時,技術設計決策
（介面契約、資料模型、非顯而易見的取捨）是 developer 邊寫邊決定的——這對單一 Story
沒問題,但跨多個 Story 時容易產生不一致（例如兩個 Story 各自對同一份資料設計出不同
形狀的欄位）。這個模組把設計決策提前、寫成文件,讓 developer 照著做,也讓後續 Story
的 architect 能讀到既有設計、保持一致。

## 與 docs/05 §5 原始規劃的差異

原始登記表把這個模組定位成「大型 Story/Epic 的系統設計階段」,隱含只有複雜的票才
需要。**本模組實作放寬為:任何通過 G1 的 Story 都要先過 Designing。** 這是啟用專案
的選擇,不是核心框架的預設立場——如果你的專案覺得每票都要設計太重,可以在
`architect.md` 的委派指令裡加條件(例如工單有 `trivial` label 就跳過),而不是改
這份 manifest。

## 流程

```
Refining → [G1] → Designing → [G1b] → Ready → In Progress → ...
```

1. Story 過 G1,不直接進 `Ready`,先進 `Designing`
2. orchestrator 委派 architect:讀需求規格 + 既有程式碼 + `docs/design/` 下既有設計文件
3. architect 產出 `docs/design/<JIRA-KEY>.md`(依 `templates/design-spec.md`):介面契約、
   資料模型、關鍵技術決策、開放設計問題
4. 退出條件全過 → 進 `Awaiting Gate` 等 G1b 放行(`config/gates.yaml` 的
   `default_mode: manual`,啟用時人類可改)
5. G1b 放行 → 進 `Ready`,開發階段照常開始(developer 讀設計文件 + 需求規格一起做)
   G1b 駁回 → 退回 `Designing`,駁回理由成為新輸入

## 退出條件(機器可判定)

- [ ] `docs/design/<JIRA-KEY>.md` 存在,且依 `templates/design-spec.md` 格式產出
- [ ] 「介面/API 契約」章節非空(或明示「無」並說明原因)
- [ ] 「資料模型」章節非空(或明示「無新增資料模型」)
- [ ] 「開放設計問題」章節為空——設計逼出的產品層決策不可自行假設,走 HUMAN-INPUT

## 啟用步驟

依 [docs/05 §3](../../docs/05-module-registry.md) 通用流程,本模組具體要做的:

1. Jira workflow 新增 `Designing` 狀態,調整轉場:
   - `Awaiting Gate` 的「G1 放行」轉場目標從 `Ready` 改成 `Designing`
   - 新增 `Designing → Awaiting Gate`(送審 G1b)
   - 新增 `Awaiting Gate → Ready`(G1b 放行,新轉場,因為原本那條已經被 G1 佔用改道)
   - 新增 `Awaiting Gate → Designing`(G1b 駁回)
   - 新增 `Blocked → Designing`(Resume 回到 Designing;`任何狀態 → Blocked` 的
     global transition 不用另外加,新狀態自動涵蓋)
2. 複製 `agents/architect.md` 到專案 `.claude/agents/`
3. 複製 `templates/design-spec.md` 到專案 `templates/`
4. 在 `config/gates.yaml` 加入 `G1b` 條目(見 module.yaml 的 `hooks[0].stage.gate`)
5. 在專案根目錄 `modules-enabled.yaml` 登記 `architecture` 模組
6. 冒煙驗證(見下)

## 冒煙驗證步驟(啟用前必跑)

1. 挑一張已過 G1、原本會直接進 `Ready` 的 Story
2. 確認它改為進入 `Designing`,而非 `Ready`
3. 委派 architect,確認 `docs/design/<KEY>.md` 產出且四項退出條件都能對照到具體內容
4. 確認 `Awaiting Gate` 上出現 G1b 的 gate report,格式比照 `templates/gate-report.md`
5. 人類留言 `GATE APPROVED`,確認狀態正確轉入 `Ready`,且 developer 委派時能讀到設計文件
6. 反向驗證駁回路徑:留言 `GATE REJECTED: <理由>`,確認退回 `Designing`
