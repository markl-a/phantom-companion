# ⑦ phantom-companion

> **shame-free 日報 / 週報生成器,跑在 phantom-mesh 上**
> Life Track wedge(Tier 1:gathering baseline;以下多為 roadmap 願景)

> **狀態說明**:本文是 phantom-companion 的願景 / roadmap spec。目前實作(Tier 1)
> 只是一個讀取 phantom-mesh 已落地的 events + ai-feed digest 並產出 Markdown 報告的
> stdlib-only 工具,詳見 [README](../README.md)。下方的健康相關性、跨 7 項目 keystone、
> 主動推送等多為 **規劃中(placeholder / roadmap)**,尚未實作。

## 一句話定位(願景)

「phantom-mesh 上的個人行為分析 agent — 觀察你怎麼用 phantom、phantom 累積的事件,找出 pattern,產出 shame-free 報告。」(健康資料 ingest 為 roadmap,見下。)

## 對齊 BIG-GOAL

- **P2 多模態理解**:把 lifestyle event(食物、運動、心跳、focus session audio、commit)全收進來
- **P3 進化網**:Hermes loop 的「judge」step 升級成「分析行為的長期 pattern」
- **Life Track 主軸**:陪你進步(fat-loss、focus、habit、daily review)— v0.6.0 wedge
- 直接服務 audience #1:「既要 workforce 又要 daily coach」

## 跟 Daily Coach 的差別(重要 — 為什麼這個 niche 強)

| 維度 | Daily Coach(舊版定義) | phantom-companion(新定位)|
|---|---|---|
| 互動模式 | reactive(你問,它答) | **proactive**(它觀察 → 主動提) |
| 資料源 | 對話 history | phantom 全部多模態事件 + sensor + 行為 |
| 結論 | 一次性建議 | 跨時段 pattern + 相關性分析 |
| 風險 | 容易講罐頭話 | 真實數據驅動 |

## 競品分析(這個 niche 競爭最分散)

| 競品 | 強項 | phantom-companion 差異 |
|---|---|---|
| **RescueTime** | 純被動 tracking | 沒 LLM insight,只 raw data |
| **Rize.io** | LLM 解讀 focus | Cloud-only,本專案 on-prem |
| **Daily.dev** | dev habit tracking | 只 dev,本專案健康 + 學習 + 家人都包 |
| **Toggl Track** | 手動計時 | 本專案自動 + 主動建議 |
| **Apple Screen Time** | iOS 內建 | 限 Apple,本專案跨 5 OS |
| **Bearable / Welltory** | 健康追蹤 | 沒整合 dev workflow 跟 LLM 用量 |
| **Sintelly / Calmly Coach** | LLM coach app | 沒看你「實際在做什麼」,只看你打字 |

**niche**:**第一個 self-hosted + 跨裝置 + LLM-powered + 整合 dev workflow + 健康 + 學習 + 行為 的個人行為分析**。

## 核心功能

### 觀察什麼

| 資料源 | 來自哪 |
|---|---|
| LLM 使用 history | phantom FTS5(自動,phantom 內每個 prompt 都進)|
| commit / skill 產出 | phantom Hermes Curator + git activity |
| Tab / context switch | phantom 內 web/screenshot 工具(consent-gated)|
| Apple HealthKit / Garmin | **(roadmap)** iOS Shortcut → ④ secure-connector ingest;repo 內無 HealthKit,health module 目前回傳 baseline |
| RSS 訂閱 vs 實際閱讀 | ③ phantom-ai-feed 答題紀錄 |
| Calendar / focus session | mac focus mode + phantom event capture |
| 接案 / 求職 lead | ⑥ phantom-flow trigger 紀錄 |
| 主觀紀錄 | 每晚 1 行(腸胃 1-5、心情 1-5、睡眠 hr)|

### 分析什麼

```
日:今天怎麼活?(原始事件 timeline)
週:這週的 pattern(產出高/低時段、注意力 trigger、消費分類)
月:跨領域相關性(健康 × 工作、學習 × 產出、消費 × 心情)
季:長期趨勢(體重 trend、技能成長、收入軌跡)
```

### 建議什麼(roadmap 願景範例 — 非實際輸出)

> ⚠ 以下為 **目標願景的示意**,非目前產出。實作上健康相關性 module 是 placeholder
> (回傳 `baseline`:「Waiting on: health …」,repo 內無 HealthKit ingest),睡眠等
> 具體數字 / 主動推送皆 **尚未實作**。實際範例見 [`docs/sample-daily-report.md`](sample-daily-report.md)。

```
[晨報 ─ roadmap]
昨天最後 2 個 commit 在 23:47 + 00:32,GraphQL 那段需要再 review
今天 14:00-17:00 commit/PR review 品質歷史最好,
要不要把那段保留給 phantom-flow 那個 PR?
(健康相關性,如睡眠 vs 產出,為 roadmap;需先有多週 health window)

[週六複盤 ─ roadmap]
本週 review:
✓ 投了 5 家(若干公司),3 家有回應,1 家 onsite
⚠ 訂的 15 個 AI source,只讀了 3 個 → 建議砍掉其他
⚠ LLM 成本本月已超月度預算 70% → 推薦改用較便宜 model
(睡眠平均、家人量血壓 compliance 等健康項為 roadmap,尚無 health 資料源)
```

## 招聘 / 副業 / 應用評分

| 維度 | 評分 | 對應 |
|---|---|---|
| **招聘** | ⭐⭐⭐⭐ | **Garmin**(health behavior)+ **Anthropic**(alignment & behavioral safety)+ Micron AIoT + 中型 AI |
| **副業** | ⭐⭐⭐ | 自我量化 SaaS niche(用戶 niche 但 ARPU 高,訂閱制) |
| **個人應用** | ⭐⭐⭐⭐⭐ | 覆蓋健康 / 學習 / 注意力 / 求職 / LLM 成本 / 財務 / 家人健康 / Prompt history 等多個 angle |

## 應用面覆蓋(8 個 angle)

- **健康**:跟產出/情緒 correlate(從個人資料學)
- **學習**:讀 vs 沒讀 ratio,推薦砍 source
- **注意力切換**:量化哪個 trigger 最致命(主推)
- **求職接案**:投出 7 天沒回的 follow-up 建議
- **LLM 成本**:哪類 task 用哪個 model 推薦
- **財務**:消費 pattern 分析 + 異常偵測
- **家人健康**:用藥/量測 compliance 追蹤
- **Prompt history**:用 prompt 的 ROI 分析

## MVP scope

### Must have(M3 W9-10)
- [ ] 事件 ingestion 統一介面(從 phantom 各 channel 收事件)
- [ ] 日報 / 週報自動生成(LLM-powered)
- [ ] 5 個內建分析 module:
  - LLM 使用效率(哪類 task 哪 model)
  - 注意力切換 pattern
  - 健康-產出 相關性
  - 學習 ROI(讀 vs 用)
  - 投履歷追蹤 + follow-up
- [ ] 早晚兩個 push 點(06:00 晨報、23:00 複盤)
- [ ] 主觀紀錄 input(每晚 1 行)

### Nice to have(M4+)
- [ ] 食物照片識別 + 卡路里(P2 多模態 demo)
- [ ] focus session audio 摘要
- [ ] 家人共用 dashboard(父母健康部分,⑦ + ④ 整合)
- [ ] 月報 / 季報(長期 trend)
- [ ] 跟 ② phantom-training 整合(用個人 pattern fine-tune 一個「懂你的小模型」)

### NOT doing
- 臨床診斷(BIG-GOAL 明確 ruled out)
- 監視式 surveillance(consent-gated 違反)
- Shame-based 介面(「你又熬夜了」)— 換成「比昨天的選擇好/差在哪」

## 為什麼必須放 M3 W9-10(中後段)

- **需要 phantom-mesh 跑 2-3 個月才有資料可分析**(M1 + M2 跑下來才有 pattern)
- **需要 ③ ai-feed 跟 ⑥ flow 都先 ship**,因為 companion 為它們的「reader」
- **需要 ④ secure-connector 已 ready**,才能接 sensor data ingest(roadmap)
- → companion 規劃為讀取多個 phantom-mesh channel 的報告層;目前(Tier 1)只讀
  events + ai-feed digest,「unlock 全部 insight 的 keystone」為 roadmap 願景

## 改裝來源

**沒有現成 repo**(新建)。但融合:
- phantom-mesh BIG-GOAL Life Track wedge(README 已寫 v0.6.0 lead)
- ③ phantom-ai-feed(學習資料)
- ④ phantom-secure-connector(健康 sensor)
- ⑥ phantom-flow(觸發紀錄)
- phantom Hermes Curator(行為 pattern judging)

## 風險

- **資料隱私 paranoia**:行為分析容易讓人覺得被監視,UI/UX 要極度 consent-gated + 可一鍵刪
- **Shame leakage**:LLM 容易講判斷性語言,要強制 prompt template 過 review
- **insight 品質**:LLM 容易講套話,要 ground in 真實 data + 引用具體事件
- **太晚開始**:M3 才做,若 M2 末已拿到 offer,可能就不做了

## 變現路徑

| 路徑 | 細節 |
|---|---|
| Pro tier 訂閱 | 進階分析 module + 長期趨勢,訂閱制 |
| 線上課程 | 「自我量化 + LLM coach」 |
| 健康訂閱 niche | 配合 ④ secure-connector,中年男性健康訂閱 |

## 為什麼這個 niche 真有市場

- 自我量化(Quantified Self)社群活躍但工具碎片化
- LLM + behavioral analytics 結合的還沒成熟(2026 才開始)
- on-prem privacy 為強差異化(健康/財務資料不想上雲)
- 規劃為 phantom 生態的報告層(roadmap 上連結其他項目的輸出);目前只讀 events + ai-feed digest

---

*Sanitized public spec. Author: Mark Lai ([@markl-a](https://github.com/markl-a)).*
