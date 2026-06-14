# phantom-companion

[![CI](https://github.com/markl-a/phantom-companion/actions/workflows/ci.yml/badge.svg)](https://github.com/markl-a/phantom-companion/actions/workflows/ci.yml)
![status: alpha · Tier 1 (gathering baseline)](https://img.shields.io/badge/status-alpha%20%C2%B7%20Tier%201%20(baseline)-orange)
![license: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue)
[![phantom-mesh ecosystem](https://img.shields.io/badge/ecosystem-phantom--mesh-purple)](https://github.com/markl-a/phantom-mesh)

> A self-hosted, shame-free daily/weekly report generator for the
> [phantom-mesh](https://github.com/markl-a/phantom-mesh) ecosystem. It reads
> the activity phantom-mesh already captures on disk and turns it into a
> readable Markdown report — no cloud, no upload.

*(中文說明見 [README — 中文](#readme--中文) below.)*

## What it is

`phantom-companion` is a small, stdlib-only Python tool with one job: read the
runtime artifacts phantom-mesh writes under `~/.phantom-mesh/` and compose a
**daily or weekly Markdown report** from them.

What is actually implemented today (Tier 1):

- **Aggregator** (`phantom_companion.aggregator`) — scans
  `~/.phantom-mesh/events/<id>/{meta,analysis}.json`, per-satellite daily logs,
  and `*-heartbeat.log` liveness files for a given day. On a real mesh it
  prefers `phantom recall --json` (the decrypting read path) and falls back to
  a raw directory scan when the `phantom` binary is absent (e.g. CI).
- **Five insight modules** — LLM usage tally, attention/context-switch density,
  learning ROI (parses the ai-feed digest), jobseek follow-up gap, and a
  health-vs-output module. Each returns a `baseline_ready` flag so the report
  honestly distinguishes "real signal" from "still gathering baseline".
- **Reporter** with a **shame-free lint**: every generated line is checked
  against a blame-language pattern list, and the reporter *refuses to write the
  file* if a shame pattern leaks in. If the optional `phantom coach review` LLM
  is installed it is merged in as an extra section; otherwise the report is
  fully deterministic and offline.
- **From-scratch robust-statistics anomaly detector**
  (`phantom_companion.anomaly_detector`) — see the dedicated section below.

Honest scope note: this is a report generator over data phantom-mesh already
captures. It does not itself collect telemetry, talk to the network, or require
any cloud service.

### Highlight: from-scratch robust-stats anomaly detector

`phantom_companion/anomaly_detector/detector.py` is a dependency-free
(stdlib-only — no NumPy, no scikit-learn) time-series anomaly detector:

- **Rolling robust z-score** using **median + MAD** (median absolute deviation)
  over a trailing window, with the `1.4826` consistency factor so MAD estimates
  std-dev for normal data. MAD is used precisely because it is robust to the
  anomalies being surfaced.
- **Warm-up / degenerate-MAD guards** so early-series points and flat windows
  cannot fire false positives.
- **5-fold cross-validated threshold calibration** (`calibrate_threshold`) that
  sweeps candidate thresholds and picks the one maximising mean validation F1 —
  the scikit-learn-free equivalent of a calibrated threshold search.

It is covered by `tests/test_anomaly_detector.py`, which injects two anomalies
into 30 days of synthetic `N(80, 5)` sleep-score data and asserts both are
flagged with at most one false positive.

Status: the detector is a **standalone, tested module**. It is **not yet wired
into the daily/weekly report pipeline** — that integration is Tier 2 work.

## Why it exists (the pain)

Existing self-tracking tools each see only one slice and most ship your data to
someone else's cloud:

- RescueTime sees app usage only; Rize sees focus only; Apple Screen Time is
  Apple-only; Bearable is manual entry.
- None of them read the activity a developer tool like phantom-mesh is already
  recording locally (LLM calls, captured events, an RSS/ai-feed digest,
  jobseek research), and none combine it into one **local-only** report.
- Generic "productivity reports" lean on blame/streak-shaming language.
  phantom-companion makes shame-free a **structural guarantee**: the reporter
  literally cannot emit a line that trips its blame-language lint.

So the niche is: a **self-hosted, offline, shame-free** report generator that
sits on top of data you already have on disk.

What is **not** done yet — stated plainly so the README doesn't overclaim:

- **Health correlation / HealthKit ingest is a placeholder.** The
  `health_productivity_correlation` module has the right shape but reports
  `baseline` ("Waiting on: health … commits …") because no health source feeds
  it today. There is no HealthKit integration in this repo. A real Pearson-r
  correlation is planned for a later tier once a multi-week health window
  exists.
- The anomaly detector is not yet called by the report pipeline (see above).
- Push delivery (Telegram/email) is roadmap, not shipped.

## 60-second run

```bash
git clone https://github.com/markl-a/phantom-companion
cd phantom-companion
pip install -e .

# Daily report — reads ~/.phantom-mesh/ (or a path you pass via --mesh-root)
python -m phantom_companion.cli daily-report

# Weekly report (7-day window)
python -m phantom_companion.cli weekly-report

# Run the tests (no extra deps beyond pytest)
pip install pytest && pytest -q
```

By default the report is written to:

```
~/.phantom-mesh/logs/phantom-companion/<date>-report.md
```

Don't have a populated mesh yet? See **[`docs/sample-daily-report.md`](docs/sample-daily-report.md)**
for a real CLI run against a synthetic fixture (no real data), including the
exact commands to reproduce it against a throwaway `--mesh-root`:

```bash
python -m phantom_companion.cli --mesh-root /tmp/synth-mesh \
  daily-report --day 2026-05-22 --out /tmp/synth-out
```

On a fresh install with an empty mesh, the report is mostly a **baseline
snapshot** — that is by design, not a bug. The tool only has something useful
to say after a few weeks of real activity accumulate.

## Architecture (within phantom-mesh)

```
~/.phantom-mesh/events/        <- captured events (meta.json + analysis.json)
~/.phantom-mesh/logs/
  phantom-ai-feed/             <- RSS / ai-feed digest (read by learning_roi)
  phantom-flow/                <- jobseek triggers
  phantom-*-heartbeat.log      <- satellite liveness
                          │
                          ▼
              phantom_companion.aggregator   (recall --json, or raw scan)
                          │
                          ▼
       5 insight_modules/* (llm, attention, learning, jobseek, health*)
                          │                  (* health = placeholder today)
                          ▼
                 reporter  (shame-free lint, optional coach LLM)
                          │
                          ▼
   ~/.phantom-mesh/logs/phantom-companion/<date>-report.md
```

All personal behavior data stays local; there is no cloud sync in this repo.

## License

Apache-2.0. © 2026 Mark Lai ([markl-a](https://github.com/markl-a)). See
[LICENSE](LICENSE).

---

# README — 中文

> phantom-mesh 生態系的自架、shame-free 日 / 週報產生器。讀取 phantom-mesh
> 已經寫在本機磁碟上的活動,產出可讀的 Markdown 報告 — 不上傳、不連雲。

## 這是什麼

`phantom-companion` 是一個小型、純 stdlib 的 Python 工具,只做一件事:讀取
phantom-mesh 在 `~/.phantom-mesh/` 下寫的 runtime 產物,合成一份**日報或週報**。

目前真正實作的(Tier 1):

- **Aggregator** — 掃 `~/.phantom-mesh/events/<id>/{meta,analysis}.json`、各
  satellite 的每日 log、`*-heartbeat.log` liveness。真實 mesh 上優先走
  `phantom recall --json`(解密讀取路徑),沒有 `phantom` binary 時(如 CI)
  退回原始目錄掃描。
- **5 個 insight modules** — LLM 使用統計、注意力/切換密度、學習 ROI(解析
  ai-feed digest)、求職 follow-up 缺口、健康×產出。每個都回傳 `baseline_ready`
  旗標,讓報告誠實區分「真有訊號」與「還在累積 baseline」。
- **Reporter + shame-free lint** — 每一行都會比對 blame 語言模式;一旦洩漏
  shame 模式,reporter **拒絕寫檔**。若安裝了選用的 `phantom coach review`
  LLM 會併入一段;否則報告完全 deterministic 且離線。
- **從零手寫的 robust-statistics 異常偵測器**(`phantom_companion.anomaly_detector`)。

誠實範圍:這是一個建立在 phantom-mesh 已擷取資料之上的報告產生器。它本身不
收集 telemetry、不連網、不需要任何雲端服務。

### 亮點:從零手寫的 robust-stats 異常偵測器

`detector.py` 是零相依(純 stdlib,無 NumPy、無 scikit-learn)的時序異常偵測:

- 以 **median + MAD**(中位數絕對離差)在 trailing window 上算 **robust
  z-score**,帶 `1.4826` 一致性係數;選 MAD 正是因為它對要偵測的異常本身穩健。
- warm-up / 退化 MAD 的防護,讓序列早期點與平坦 window 不會誤報。
- **5-fold 交叉驗證的 threshold 校準**(`calibrate_threshold`),掃候選
  threshold 取驗證 F1 平均最大者 — 不依賴 scikit-learn 的等效作法。

`tests/test_anomaly_detector.py` 在 30 天合成 `N(80,5)` 睡眠分數中注入兩個異
常,驗證兩個都被標記且最多一個 false positive。

狀態:此偵測器是**獨立、已測**的模組,**尚未接進日 / 週報 pipeline**(Tier 2)。

## 為什麼存在(痛點)

現有自我追蹤工具各自只看一片、且多半把資料送上別人的雲:RescueTime 只看 app、
Rize 只看 focus、Apple Screen Time 只限 Apple、Bearable 是手動記錄。沒有一個會
讀像 phantom-mesh 這種開發工具已經在本機記錄的活動(LLM 呼叫、擷取的事件、
ai-feed digest、求職研究),也沒有一個把它合成成單一的**純本機**報告。一般的
「生產力報告」又愛用 blame / streak-shaming 語氣。phantom-companion 把 shame-free
做成**結構性保證**:reporter 根本無法輸出觸發 blame lint 的句子。

**尚未完成(明說以免 overclaim):**

- **健康 correlation / HealthKit 接入是 placeholder。**
  `health_productivity_correlation` 形狀正確,但因為今天沒有健康資料來源餵它,
  它回報 `baseline`(「Waiting on: health … commits …」)。本 repo **沒有**
  HealthKit 整合;真正的 Pearson-r correlation 是後續 tier、要有數週健康資料後才做。
- 異常偵測器尚未被報告 pipeline 呼叫(見上)。
- 推播(Telegram / email)是 roadmap,尚未 ship。

## 60 秒上手

```bash
git clone https://github.com/markl-a/phantom-companion
cd phantom-companion
pip install -e .

python -m phantom_companion.cli daily-report     # 日報
python -m phantom_companion.cli weekly-report    # 週報(7 天)

pip install pytest && pytest -q                   # 測試
```

報告預設寫到 `~/.phantom-mesh/logs/phantom-companion/<date>-report.md`。
還沒有資料?看 **[`docs/sample-daily-report.md`](docs/sample-daily-report.md)** —
一次對合成 fixture(無真實資料)的真實 CLI run,含可重現指令。空 mesh 上報告
主要是 baseline 快照,這是 by design;累積數週真實活動後才會有有用的內容。

## 招聘 / 共建角度

- **Garmin / 穿戴裝置團隊** — multi-source 健康×行為 correlation 與 on-device
  privacy。(注意:健康面今天仍是 placeholder,見上。)
- **Anthropic / LLM-tooling** — proactive、on-device privacy、cost-aware 路由。
- **Micron AIoT / 醫療 AI** — shame-free coaching 作為硬約束、longitudinal
  個人資料不綁雲。

## License

Apache-2.0. © 2026 Mark Lai ([markl-a](https://github.com/markl-a))。見
[LICENSE](LICENSE)。
