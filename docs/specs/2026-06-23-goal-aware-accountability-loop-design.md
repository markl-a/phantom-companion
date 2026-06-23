# phantom-companion — Goal-Aware 問責閉環 設計

- **日期:** 2026-06-23
- **狀態:** DRAFT(待 owner review → 進 writing-plans)
- **作者:** Claude Code(brainstorming;依 owner 校正「companion 原始目的 = 目標問責閉環」+ 拍板自用/營利)
- **關係:** 本文實作 `docs/phantom-companion.md`〈方向與願景〉裡標為 vision-not-shipped 的 **目標函數 + 主動推播 + 閉環**。既有 Tier 1–3 引擎(aggregator / insight_modules / anomaly_detector / reporter / notify / checkin)全部保留;本文在其上加一層「目標對齊」。落地後回填主文件。

---

## 0. 一句話

> 把 companion 從**被動分析**變**主動問責**:你宣告你的目標(運動/睡眠/求職/產出/AI花費)→ companion 拿你的行為**deterministic 地**對著目標量 → 偏離/違反時,經既有 notify 發一則**shame-free 提醒**。這是願景閉環的心臟,今天是空的。

## 1. 為什麼(owner 校正)

companion 已出貨「分析 + 日/週/月複盤 + 統計異常警示 + 主動推播」,但**缺「對著你宣告的目標」這一塊**。現況的警示是 *statistical anomaly*(「這對你不尋常」),**不是** *goal-violation*(「這違反你設的目標」)。差別:現在=「你今天 commit 異常低」;願景=「你說這週要運動 + 投 3 家工作,你 3 天沒動、求職掛零 —— 拉回來」。缺的核心 = **目標函數**(宣告目標 → 對齊量測 → 違反提醒)。這也是 companion 唯一站得住的獨立營利(問責是已驗證付費市場:Beeminder/StickK/Focusmate)的前提引擎。

## 2. 守住既有紅線(不可違反)

| 紅線 | 本 phase 如何遵守 |
|---|---|
| **金額/判定不交給會幻覺的 LLM**(同 finance 稅務原則) | 「有沒有違反目標」**永遠 deterministic** 規則判定;LLM 只**潤飾提醒語氣**,離線時 deterministic 模板照樣提醒 |
| density-gated,不對雜訊瞎報 | 沿用 `MIN_SAMPLES`;某指標資料不足 → 狀態 `insufficient_data`,**不提醒** |
| shame-free(提醒你而不羞辱你) | 每則目標提醒過既有 shame-free lint;不過則 deterministic 安全樣板勝出(同 reporter 既有不變式) |
| local-first / 離線可跑 | goals.json 本地;eval 純本機 deterministic;無網路/無 AI 也能算出目標狀態 |
| AI 永遠是補完非必需 | coach 潤飾提醒預設可關;關閉時功能不降級 |
| 任何外送經 mesh 既有同意機制 | 目標提醒走既有 `notify`(local sink always;off-device relay opt-in + consent-gated) |

## 3. 架構取向

**延伸現有管線,不重寫。** 既有 `aggregate_window() -> AggregateWindow`(typed、day-ordered、SQLite-cached)就是量測底料。新增三塊 + 兩處整合:

```
goals.json ──► goals.py (Goal schema, load/save)
                    │
AggregateWindow ────┤
checkin(mood) ──────┼──► goal_eval.py  ──► [GoalStatus]  (deterministic, density-gated)
llm_usage(cost) ────┘                         │
                                              ├──► reporter.py   「🎯 目標追蹤」段(日/週報)
                                              └──► notify.py     違反 → shame-free 提醒(consent-gated push)
                       CLI: companion goal set/list/rm · companion goals
```

- deterministic、無 LLM、純 stdlib + 既有模組;測試比照 repo 慣例放 `tests/`。

## 4. 範圍 + 行為

**目標 schema(`goals.json`,人類可讀可編輯):**
```
Goal = {
  id: str,                       # 穩定 slug
  label: str,                    # "每週運動 3 次"
  metric: "commits" | "activity_min" | "sleep_hr" | "jobs_applied" | "llm_cost" | "mood",
  direction: "at_least" | "at_most",
  target: float,                 # 門檻
  window_days: int,              # 評估窗(7=週、30=月、1=每日)
  agg: "sum" | "mean" | "count_days_meeting"   # 預設依 metric 給合理值
}
```
**指標對映既有真實欄位(不憑空造):** `commits`←`OutputSample.commits`;`activity_min`/`sleep_hr`←`HealthSample`;`jobs_applied`←events `applied=True` 計數;`llm_cost`←`llm_usage` 模組總額;`mood`←nightly `checkin`。

**目標評估(`goal_eval.py`,deterministic):** 對每個 goal 跑窗內量測 → `GoalStatus`:
- `on_track` — 達標。
- `drifting` — 未違反但落在違反邊緣(預設邊際,如 at_least 達成率 < 80%)。
- `violated` — 未達標(且資料足夠)。
- `insufficient_data` — 窗內有效樣本 < `MIN_SAMPLES` → **不提醒**。
- 回傳含 `actual`、`target`、`gap`、`days_observed`,供報告與提醒渲染(全 deterministic)。

**輸出:**
1. **報告整合**:日/週報新增「🎯 目標追蹤」段,逐目標渲染狀態(shame-free)。
2. **違反提醒**:`violated`(資料足夠)→ 經 `notify.deliver()` 發一則 shame-free 提醒(local sink always;push opt-in/consent-gated/payload-minimised)。`drifting` 預設只進報告不單獨推播(避免噪音;owner-gated)。
3. **CLI**:`companion goal set <metric> <at-least|at-most> <target> [--window N] [--label L]`、`companion goal list`、`companion goal rm <id>`、`companion goals`(列出當前各目標狀態)。

**離線/AI 邊界:** goal 判定全 deterministic;`PHANTOM_COMPANION_LLM` 開啟且 backend 可用時,coach 經 `phantom exec --provider <key>`(本生態系今日已 live)**潤飾提醒語氣**;關閉/離線時 deterministic 樣板勝出,功能不降級。

## 5. 三層界線

| 層 | 不接任何東西 | 接 4 AI | 接 mesh/relay |
|---|---|---|---|
| 能力 | 宣告目標 + deterministic 評估 + 報告段 + 本地提醒(全本機) | coach 潤飾提醒語氣(`--provider`,預設 off) | 提醒推播到手機(consent-gated,relay 便利層) |
| 角色 | **自用 + 獨立營利引擎(站得住)** | 更貼心 | 更有未來(= 營利 A 託管/推播) |

## 6. 自用 + 營利(owner 拍板鎖定)

- **自用** = 你私密、不羞辱、跨裝置的**個人目標問責教練**(願景閉環)。這是 companion 的本體。
- **營利** = **目標問責階梯**,疊在**免費 OSS 引擎**上(本 phase 只建引擎,收費包裝待真實訊號再分層,不在本 phase 蓋金流/託管):
  - **C** 一次性「目標系統建置 + 季度問責複盤」包(入門、低承諾)。
  - **A** 託管訂閱 $5–9/月(替不自架者跑 + 推播到手機;Nabu Casa 式便利)= 回流主線。
  - **B** Commitment 模式(押注/失敗扣錢;Beeminder 式)= premium、opt-in、最後做。
- 三者**不互斥**,同一引擎不同包裝。**能力永遠免費,只收便利/問責服務** —— 與核心 relay/no-gate-core 模式一致。

## 7. 風險與緩解

1. **把 goal 判定交給 LLM → 幻覺問責** → 判定一律 deterministic;LLM 只潤飾語氣;測試覆蓋「AI off 仍正確提醒」。
2. **資料不足時瞎提醒**(companion 老問題:需 30+ 天真資料)→ `MIN_SAMPLES` density gate;不足 → `insufficient_data` 靜默。
3. **提醒變成羞辱/噪音** → shame-free lint 每則必過;`drifting` 預設不單獨推播;提醒可調頻。
4. **過早蓋收費基建**(over-build) → 本 phase **只建免費引擎**;A/B/C 金流/託管待訊號。
5. **目標 metric 對映漂移**(指標欄位改名)→ metric 白名單集中一處 + 測試對著真實 schema 欄位斷言。

## 8. 待確認 / owner-gated

- `drifting` 邊際門檻(建議 at_least 達成率 < 80%)。
- 違反提醒的推播頻率/節流(建議:每目標每窗最多一則,避免轟炸)。
- `mood` 要不要納入可設目標(主觀;建議納入但標「主觀指標」)。
- 預設目標窗對映(建議:commits/sleep/activity=日、jobs=週、llm_cost=月)。

## 9. Phase 之後(非本 spec)

收費包裝(C 包 → A 託管訂閱 → B commitment 模式)各自獨立規劃,且只在引擎跑起來 + 有真實訊號後做;`apex-②` owned-memory 個人化校準(「對你而言睡 6.5h 就夠」)是更後面的願景介面。
