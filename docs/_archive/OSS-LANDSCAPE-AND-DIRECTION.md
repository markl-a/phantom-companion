> ARCHIVED 2026-06-19 — 內容已併入 docs/phantom-companion.md;此為歷史版本。

# 開源生態與方向 — phantom-companion

_最後調查於 2026-06-19。領域：個人生活／健康／生產力陪伴助手、
量化自我（quantified-self）、生活紀錄（life-logging）、個人分析、AI 生活教練／日誌代理。_

> **本文件是什麼。** 對本專案所競爭與借鏡的開源領域所做的紮實掃描，最終提出一份
> 採用／包裝／參考／自建（adopt / wrap / reference / build）的建議，以守住利基。
> 它**不是**狀態文件——狀態的單一真實來源是 [`ROADMAP.md`](../ROADMAP.md)。
> 星數與中繼資料已於調查當日對照上游 repo 驗證；
> 任何未經直接驗證者皆標記為 `[unverified]`。

---

## 1. phantom-companion 的現況（紮根於提交歷史）

phantom-companion **並非一個全新未開墾的構想——引擎其實早已交付。** 紮根於
`master`（`git log`）與 [`ROADMAP.md`](../ROADMAP.md)：

- **已交付（Tier 1–3，Python，Apache-2.0）：**
  - `aggregator.py` — 純 Python 資料層，讀取 `~/.phantom-mesh/events/`（透過
    `phantom recall`，由它解密）加上 6 個衛星姊妹專案的日誌，匯整成型別化的
    `DailyAggregate`。此層無 LLM、無網路。
  - **5 個洞察模組**（`llm_usage`、`attention_switches`、
    `health_productivity_correlation`、`learning_roi`、`jobseek_followup`），各自具備
    統一的 `{module, summary, details, baseline_ready}` 契約，並在輸入為空時誠實地退回
    baseline-stub。
  - **無羞辱式報告器**（`reporter.py`），對應 phantom-mesh 的 `coach_prompts/lint.rs`；
    若 LLM 潤飾路徑未通過 lint，則由決定性樣板勝出。
  - **統計層位於單一來源 `MIN_SAMPLES`（約 14 天）密度門檻之後：** 經門檻管控的
    Pearson **與** Spearman 健康×產出相關性（不暗示因果的措辭）、每週跨衛星彙整、
    經密度門檻的 rolling-MAD 異常警示、本地優先且經同意門檻的通知遞送、夜間主觀
    check-in 加上每月／每季趨勢、情緒×產出的跨領域相關性，以及求職線索過期老化。
  - **正式接線**（`ingest-output`、`ingest-health`），使先前「宣稱為綠燈但實際無法觸及」
    的路徑取得真實資料。
  - 封裝衛生：Apache-2.0、CI ＋ 徽章、asciinema 示範。
- **進行中：** 無追蹤項目。就現有範圍而言，程式碼引擎基本上已完成。
- **誠實且設計使然的注意事項：** 有用的洞察需要**累積 30 天以上的 phantom-mesh
  事件**，外加 {③ ai-feed 摘要、⑥ flow 求職} 至少其一以真實節奏寫入。今天就執行的話，
  報告*結構正確但訊號稀薄*——它們會退化為「正在蒐集 baseline」的 stub，而非憑空捏造
  洞察。**這是應該主導方向的核心事實：瓶頸在於資料量與真實裝置／衛星的擷取，而非更多
  功能。**

**利基（依 README ＋ spec 的定位）：** 一個**跨裝置 ＋ 自動 ＋ LLM 洞察 ＋
無羞辱**的個人精進迴圈，**整合於整個 phantom-mesh 之上**（LLM 用量、提交、RSS 閱讀、
行事曆、健康、求職線索），且其無羞辱式框架**由 lint 在結構上強制實施**。可防禦的
護城河在於**跨衛星相關性**——*在下方所調查的開源專案中*，沒有任何一個把 LLM 成本、
健康、學習與求職在同一處串接起來——再加上**本地優先／無羞辱**作為硬性約束，而非
行銷話術。（此為受調查範圍所限的主張，並非絕對的「史上首見」。）

---

## 2. 生態盤點

### 2a. 自動活動／時間追蹤（「觀察你在做什麼」這一層）

| 專案 | URL | 星數 | 語言 | 授權 | 成熟度 | 契合度／落差 |
|---|---|---|---|---|---|---|
| **ActivityWatch** | github.com/activitywatch/activitywatch | 17.9k | Python | MPL-2.0 | 成熟；最後釋出 v0.13.2（2024 年 10 月） | **同類中最佳的本地、隱私優先、跨平台（Win/Mac/Linux/Android）自動追蹤器。** 落差：僅有原始 bucket，*無 LLM 洞察、無跨領域相關性、無健康／求職*。**理想的上游資料來源，應包裝而非與之競爭。** |
| **Rize.io** | rize.io | n/a（閉源） | n/a | 專有、雲端（AWS） | 成熟的商業產品 | 以 LLM 解讀為主的專注力追蹤＋教練，但**僅限雲端、$9.99–29.99/mo、閉源。** 直接的概念競爭者；我們的差異化在於本地 ＋ 跨衛星 ＋ 免費。 |
| **Toggl / RescueTime / Apple Screen Time** | — | n/a | n/a | 專有 | 成熟 | 手動（Toggl）、被動原始（RescueTime）、僅限 Apple（Screen Time）。皆為單一領域，無 LLM 跨相關性。可作為 UX 參考，不可採用。 |

### 2b. 量化自我匯整／相關性（「把一切串起來」這一層——我們的核心）

| 專案 | URL | 星數 | 語言 | 授權 | 成熟度 | 契合度／落差 |
|---|---|---|---|---|---|---|
| **QS Ledger** | github.com/markwk/qs_ledger | 1.1k | Jupyter | MIT | 穩定但以 notebook 為中心；約 78 次提交 | 在本地匯整 17 種以上服務（Fitbit、Strava、Apple Health、Todoist、Last.fm）並提供相關性／儀表板 notebook。**與我們的 aggregator 在精神上最相近的姊妹專案。** 落差：手動 notebook 流程、*無常駐程式、無 LLM、無無羞辱框架、未與 phantom 整合*。**可作為連接器廣度＋相關性模式的參考。** |
| **Fluxtream / Gyroscope / Open Humans** | various | varies `[unverified]` | varies | varies | 較舊／小眾 `[unverified]` | 個人資料視覺化框架（Fluxtream 大致已休眠 `[unverified]`）；Gyroscope 已商業化；Open Humans 是研究資料共享。僅供參考——皆非本地 LLM 教練。 |
| **Exist.io** | exist.io | n/a（閉源） | n/a | 專有、雲端 | 成熟的商業產品 | 「把你的人生相關聯」這一典範產品（情緒 × 步數 × 天氣）。**僅限雲端。** 這正是我們要以本地、AI 原生、無羞辱去回應的產品。無可採用的程式碼；是*使用者想要哪些相關性*的黃金參考。 |

### 2c. 健康／健身裝置擷取（感測邊緣）

| 專案 | URL | 星數 | 語言 | 授權 | 成熟度 | 契合度／落差 |
|---|---|---|---|---|---|---|
| **OpenScale** | github.com/oliexdev/openscale | 1.1k | Java | GPL-3.0 | 成熟；130 位貢獻者 | 從 BLE 體重計取得本地體重＋22 項身體指標，**無網際網路權限＝強隱私保證。** 可餵入 ④ 安全連接器。**參考／可選的擷取來源。** |
| **OpenTracks** | github.com/OpenTracksApp/OpenTracks | `[unverified]` ~2k | Java | Apache-2.0 | 成熟；F-Droid | 尊重隱私的離線運動追蹤器。Apache-2.0 ＝ **授權相容**。可作為健康資料來源，透過匯出 → ④ 擷取。 |
| **Firefly III** | github.com/firefly-iii/firefly-iii | 23.8k | PHP | AGPL-3.0 | 非常成熟 | 自架的個人財務（「絕不聯絡外部伺服器」）。對應到 spec 中延後的**財務**面向。**AGPL ＋ 笨重的 PHP 技術棧＝僅供參考，請勿 vendor。** 若日後確實要做財務，透過其 REST API 包裝即可。 |

### 2d. AI 日誌／生活教練／本地 LLM 代理（「洞察＋反思」這一層）

| 專案／模式 | URL | 星數 | 語言 | 授權 | 成熟度 | 契合度／落差 |
|---|---|---|---|---|---|---|
| **Logseq**（日誌優先的 PKM） | github.com/logseq/logseq | 33k+ | Clojure/TS | AGPL-3.0 | 成熟 | 本地優先、預設每日筆記、純 markdown。**可作為日誌 UX 的參考**，並非分析引擎。AGPL——僅供參考。 |
| **Obsidian ＋ AI／日誌外掛** | obsidianstats.com/plugins/ai-tools | varies | TS | mixed | 活躍的生態系 | 龐大的本地優先反思生態系；外掛在每日筆記之上加入 LLM 反思。Obsidian 核心為閉源；外掛多為 MIT 類。**可作為 markdown 報告＋反思介面的參考**（我們已經產出 markdown 報告）。 |
| **本地 LLM 日誌技術棧**（Ollama / LM Studio ＋ DIY） | — | n/a | — | mixed | 2026 新興 | 「在你的機器上全離線進行 AI 日誌」這一模式現已普遍。佐證了我們的本地 LLM 教練方向；**無單一可採用的 repo**——這些是配方，不是產品。確認我們應讓教練流程可路由到*本地*模型。 |

---

## 3. 建議方向（採用／包裝／參考／自建）

**標題：建置已完成；槓桿在於擷取廣度與資料累積，而非新的分析程式碼。** 借用連接器，
別重建引擎。

| 決策 | 對象 | 原因 |
|---|---|---|
| **WRAP** | 以 **ActivityWatch** 作為專注力／情境切換來源 | 它已解決跨平台的本地活動擷取（spec 中「Tab／情境切換」那一列）。把它的本地 REST/SQLite 匯出包裝進 `attention_switches`，遠比自己造監看器更便宜且更穩健，而且能讓資料留在本地。**最高價值、最低成本的一步。** |
| **REFERENCE** | **QS Ledger** 的連接器清單＋相關性 notebook | 從中挖掘*接下來該擷取哪些*外部服務以及相關性慣用法——但保留我們的常駐程式＋無羞辱＋門檻統計架構；不要採用 notebook 流程。 |
| **REFERENCE** | **Exist.io** 的相關性目錄 | 以它作為「使用者實際覺得有價值的相關性」目標清單，藉以排序要呈現哪些經門檻的相關性。我們是它在本地、無羞辱、AI 原生的對應版本。 |
| **WRAP（可選，稍後）** | **OpenScale / OpenTracks** 匯出 → ④ 安全連接器 | Apache-2.0/GPL 的本地健康來源，能在不必接上 iOS/Garmin/Relay 的情況下，把更多「等待：健康」門檻翻成真實指標。僅在確實有裝置在使用時才做。 |
| **僅 REFERENCE** | **Firefly III**（財務）、**Logseq/Obsidian**（日誌 UX） | 笨重／AGPL 或閉源核心。至多透過 API 整合；切勿 vendor。財務面向已明確延後。 |
| **BUILD（保留我們的）** | **跨衛星相關性引擎＋無羞辱 lint＋治理器／同意門檻** | 這是護城河。所調查的開源專案中，沒有一個在同一個本地、無羞辱的迴圈裡串接 LLM 成本 × 健康 × 學習 × 求職。只在這裡持續建置。 |

---

## 4. 分階段路徑（先做便宜高價值、且保護護城河者）

1. **階段 1 — 讓資料累積（不寫程式）。** 已交付引擎的瓶頸是 30 天以上的注意事項。
   最高價值的「工作」就是每天執行 mesh，讓真實訊號浮現。一旦有了時間窗，就用真實
   （非 fixture）資料驗證示範。
2. **階段 2 — 把 ActivityWatch 包裝**進 `attention_switches`（它的本地匯出 → 我們的
   正規化紀錄）。這是把專注力模組從 stub 形狀變成真實的最便宜方式，且零隱私退步。
3. **階段 3 — 可選的裝置擷取**（OpenScale/OpenTracks 匯出 → ④ 擷取）*僅在有裝置每天
   在用時*。否則跳過——為不存在的資料建置擷取純屬過度建置。
4. **階段 4 — 將教練路由到本地／MCP-broker 模型**（已在 roadmap 上作為「MCP broker
   LLM 路徑」）。讓 LLM 洞察留在本地且成本經路由，符合 2026 年的本地 LLM 日誌模式。
5. **階段 5（延後）— 透過 Firefly III API 做財務**、家庭儀表板、個人模型微調。只有在
   核心迴圈於真實縱向資料上被證明有價值之後才進行。

---

## 5. 誠實的過度建置與隱私警示

- **過度建置風險高且具體：** 引擎已超出它所擁有的資料。在*真實資料累積滿 30 天之前*
  加入更多洞察模組、更多多模態示範或裝置擷取，只會產出無人能驗證的假綠燈功能。
  **在真實資料對既有門檻施壓之前，抗拒全新的分析程式碼。**
- **不要重新實作 ActivityWatch。** 撰寫跨平台監看器是一項多年工程，那個 17.9k 星的
  專案早已掌握。包裝它是正確的；複製它則是典型的單人開發陷阱。
- **隱私就是產品，所以每一個新的擷取都是新的攻擊面。** ActivityWatch、OpenScale、
  Firefly III 之所以被選中，部分原因正是它們*預設本地*。維持不變式：不讓 PII 跨越裝置
  邊界；離開裝置的轉送維持 opt-in、經同意門檻、payload 最小化（`notify.py` 中已是
  如此）。任何新連接器都必須繼承相同門檻，否則不予出貨。
- **無羞辱是硬性約束，不是功能旗標。** lint 必須在每一條輸出的行上執行，包含任何新的
  LLM 路徑（Obsidian 式的反思外掛明顯*沒有*這項保證——那正是我們的差異化，別稀釋
  它）。
- **商業競爭者（Rize、Exist.io）被鎖在雲端。** 別在他們的條件上追逐功能對等；本地 ＋
  跨衛星 ＋ 無羞辱的組合，是單人專案唯一能贏的戰場。守在上面。

---

## 來源

- [ActivityWatch](https://github.com/activitywatch/activitywatch) ·
  [activitywatch.net](https://activitywatch.net/)
- [QS Ledger](https://github.com/markwk/qs_ledger) ·
  [awesome-quantified-self](https://github.com/markwk/awesome-quantified-self)
- [Firefly III](https://github.com/firefly-iii/firefly-iii)
- [OpenScale](https://github.com/oliexdev/openscale) · [OpenTracks](https://alternativeto.net/software/opentracks/about/)
- [Logseq](https://github.com/logseq/logseq) · [Obsidian AI plugins](https://www.obsidianstats.com/plugins/ai-tools)
- [Rize pricing](https://rize.io/pricing) · [Exist.io](https://exist.io/)
- [Build Open-Source Personal AI Agents 2026 (SitePoint)](https://www.sitepoint.com/the-rise-of-open-source-personal-ai-agents-a-new-os-paradigm/)
