# phantom-companion

[![CI](https://github.com/markl-a/phantom-companion/actions/workflows/ci.yml/badge.svg)](https://github.com/markl-a/phantom-companion/actions/workflows/ci.yml)

> **Proactive 行為觀察 + LLM insight + 跨裝置整合** — RescueTime + Rize +
> Bearable 的整合版,phantom-mesh 七專案的 keystone(唯一消費其他六個輸出
> 的專案),招聘對齊 Garmin / Anthropic / Micron AIoT。

![status: alpha · Tier 1 (gathering baseline)](https://img.shields.io/badge/status-alpha%20%C2%B7%20Tier%201%20(baseline)-orange)
![license: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue)
[![phantom-mesh ecosystem](https://img.shields.io/badge/ecosystem-phantom--mesh-purple)](https://github.com/markl-a/phantom-mesh)

## 一句話 niche

RescueTime 只看 app 使用、Rize 只看 focus、Apple Screen Time 是 Apple-only、
Bearable 是手動記錄。**phantom-companion 是第一個跨裝置 + 自動 + LLM-insight
+ shame-free 的 personal-improvement loop** — 不是等你問才答,而是看你怎麼
活(LLM 使用、commit、RSS 閱讀、行事曆、健康、求職 leads),跨整個
phantom-mesh 找 pattern,寫日 / 週報,語言**結構上保證沒有羞辱**。

## Status (2026-05-22)

- ✅ **Tier 1 shipped**:
  - `phantom_companion.aggregator` — 從 `~/.phantom-mesh/events/` 與其他 6
    個 satellite 的 log 目錄聚合
  - 5 insight modules (LLM ROI / 注意力切換 / 健康×生產力 / 學習 ROI /
    求職 follow-up)
  - reporter with shame-free lint
  - cross-satellite read 即 day-one 可運作
- 🟡 **Tier 2 next**: Telegram / email push、SM-2 spaced repetition 給
  weekly pattern、跨 satellite correlation engine 升級。
- 🟡 **Tier 3 (M3-M4, ~2026-09)**: 健康 vs 生產力的 statistically-sound
  correlation(需要 ≥ 60 天資料)、自動 intervention 建議。
- ⚠️ **Honest caveat**: 真正有用要 **2-3 個月累積 phantom-mesh events** 之
  後。今天跑會吐 honest stub 報告,結構正確但 insight 稀薄 — 這是 by design,
  不是 bug。

## 30-second quickstart

```bash
git clone https://github.com/markl-a/phantom-companion
cd phantom-companion
pip install -e .

# 跑日報(會吃 ~/.phantom-mesh/events/ + 各 satellite log)
python -m phantom_companion.reporter --kind daily

# 週報
python -m phantom_companion.reporter --kind weekly

pytest -v
```

報告寫到:

```
~/.phantom-mesh/logs/phantom-companion/<date>-report.md
```

## Architecture (within phantom-mesh ecosystem)

phantom-companion 是 keystone — 唯一消費其他 6 個 satellite 輸出的 phantom-mesh
專案,把 phantom-mesh 從 developer toolbox 變成 daily-life product。

```
~/.phantom-mesh/events/        <- E002 event capture (meta.json + analysis.json)
~/.phantom-mesh/logs/
  phantom-ai-feed/             <- ③ digest + answered questions
  phantom-flow/                <- ⑥ jobseek triggers
  phantom-training/            <- ② training runs
  phantom-secure-connector/    <- ④ redaction / anomaly events
  phantom-enterprise/          <- ⑤ corp connector events
  phantom-*-heartbeat.log      <- satellite liveness
                          │
                          ▼
              phantom_companion.aggregator
                          │
                          ▼
       5 insight_modules/* (LLM, attention, health, learning, jobseek)
                          │
                          ▼
                 reporter (shame-free lint)
                          │
                          ▼
   ~/.phantom-mesh/logs/phantom-companion/<date>-report.md
```

Pillars served: **P3** (進化網 — pattern discovery 是 Hermes 6-step 的
自然延伸)、**P4** (加密為先 — 所有個人行為資料 local-only,沒有 cloud
sync)、**P1** (跨平台 — 行為資料來自 Mac/Win/Linux/iOS/Android)。

## What it covers (8 痛點)

1. LLM usage ROI — 哪個 provider 對哪個 task、$ / insight
2. Attention switches — context-switch 密度、peak focus 視窗
3. Health × productivity — sleep / HRV vs commit / PR quality
4. Learning ROI — RSS subscribed vs 真讀 vs 真用
5. Jobseek follow-up — 查過但沒投的公司
6. Daily review (shame-free) — what worked、不用 blame language
7. Weekly pattern surfacing — cross-domain correlation
8. Proactive suggestion delivery — push 到 file → Telegram → email later

## Target users (recruiter / co-builder angle)

- **Garmin / 穿戴裝置團隊** — multi-source 健康 × 行為 correlation 是核心
  能力,加上 on-device privacy 是 differentiator。
- **Anthropic / LLM-tooling 團隊** — proactive agent、on-device privacy、
  cost-aware routing 對齊 Claude Memory / Claude Code 演進方向。
- **Micron AIoT / 醫療 AI / digital-therapeutics** — shame-free coaching
  是 hard constraint(不是 marketing),longitudinal personal data without
  cloud lock-in 對醫療場景剛需。
- **Co-builders**: 想要 self-hosted RescueTime + Bearable + Rize 整合版的
  quantified-self / productivity 玩家。

## Roadmap (per master plan)

- 詳細設計: [`docs/07-phantom-companion.md`](docs/)
- 七專案總圖: [phantom-mesh planning tree](https://github.com/markl-a/phantom-mesh)

3-bullet:

1. **M2** — Telegram/email push、cross-satellite correlation 升級。
2. **M3-M4** — statistically-sound 健康 vs 生產力(≥ 60 天資料後)。
3. **Post-M4** — 自動 intervention 建議、行為 A/B 測試 framework。

## When this becomes valuable

After **30+ days of accumulated phantom-mesh events** AND at least one of
{③ ai-feed digest log, ⑥ flow jobseek log} being actively written. 在那之前,
insight 是 stub-shaped 但結構正確。

## License

Apache-2.0. © 2026 Mark Lai ([markl-a](https://github.com/markl-a)). See
[LICENSE](LICENSE).
