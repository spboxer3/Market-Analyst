# Market Analyst — 美股市場分析報告生成器

一個 Claude Code 技能，用於生成結構化的美股市場分析報告。透過 7 階段管線從 6 個數據來源平行抓取資料，處理後輸出繁體中文 / 簡體中文的本地化報告。

> [English README](readme.md)

## 功能特色

- **4 種報告類型**：盤前日報、盤後日報、週報、月報
- **6 大數據來源**：Financial Datasets、yfinance、Alpha Vantage、Polymarket、Reddit、Web Search
- **自訂關注清單**：透過 `watchlist.md` 持久化記錄關注個股，自動在每份報告中強化分析
- **投資組合支援**：可選擇性整合個人持倉，生成客製化 P&L 分析
- **本地化輸出**：zh-TW（繁體中文）與 zh-CN（簡體中文）雙語版本
- **可審計管線**：所有中間數據以 JSON 格式保存

## 快速開始

### 生成報告

```
/market-analyst 給我今日美股盤前日報
/market-analyst 盤後日報，重點看半導體跟台積電
/market-analyst 週報，追蹤 TSMC、AAPL，加入 Fed 利率分析
```

### 管理關注清單

| 操作 | 指令範例 |
|------|----------|
| 新增個股 | `加入 TSMC 到關注清單` 或 `watchlist add NVDA` |
| 移除個股 | `從關注清單移除 AAPL` 或 `watchlist remove AAPL` |
| 查看清單 | `顯示我的關注清單` 或 `watchlist show` |
| 修改優先級 | `把 TSMC 的優先級改為 high` |
| 新增備註 | `NVDA 備註：關注 GTC 後法說會指引` |
| 清空清單 | `清空關注清單` 或 `watchlist clear` |

## 架構總覽

```
讀取 watchlist.md → 觸發解析 → 投資組合閘門 → 平行數據抓取（6 來源）
  → 處理管線（4 步驟）→ 報告結構（8+1 章節）→ 本地化輸出 → 分發 PDF
```

### 7 階段管線

| 階段 | 說明 | 輸出 |
|------|------|------|
| 0 | 讀取關注清單 | Watchlist 項目注入管線 |
| 1 | 解析使用者指令 | `trigger_request.json` |
| 2 | 投資組合閘門 | `portfolio_gate.json` |
| 3 | 平行數據抓取（6 來源） | `fetched/*.json` |
| 4 | 處理管線（整合 → 指標 → 圖表 → 模板） | `integrated_data.json`、`indicators.json`、`charts_manifest.json` |
| 5 | 報告結構（最多 9 章節） | 章節納入矩陣 |
| 6 | 本地化（zh-TW / zh-CN） | 本地化報告檔案 |
| 7 | 分發 | PDF 交付 |

### 報告類型

| 類型 | ID | 排程 | 時區 |
|------|-----|------|------|
| 盤前日報 | `pre_market` | 每日 8:00 | 美東時間 |
| 盤後日報 | `post_market` | 每日 17:00 | 美東時間 |
| 週報 | `weekly` | 週五收盤 | 美東時間 |
| 月報 | `monthly` | 月底 | 美東時間 |

### 報告章節

| 章節 | 盤前 | 盤後 | 週報 | 月報 | 前置條件 |
|------|:---:|:---:|:---:|:---:|----------|
| 1. 市場概覽 | Y | Y | Y | Y | — |
| 2. 重大新聞 | Y | Y | Y | Y | — |
| 3. 技術訊號 | Y | Y | Y | Y | — |
| 3.5 Watchlist 個股追蹤 | Y | Y | Y | Y | 關注清單 |
| 4. 板塊熱力圖 | — | Y | Y | Y | — |
| 5. Polymarket 預測市場 | Y | Y | Y | Y | — |
| 6. Reddit 社群情緒 | — | Y | Y | — | — |
| 7. 投資組合 P&L | — | Y | Y | Y | 投資組合 |
| 8. 明日預覽 | Y | Y | — | — | — |

## 關注清單（Watchlist）

關注清單儲存在技能根目錄下的 **`watchlist.md`**。此檔案跨對話持久化保存，每次生成報告時自動讀取並強化相關個股分析。

### 優先級分級

| 優先級 | 報告中的呈現方式 |
|--------|------------------|
| `high` | 獨立分析段落：價格走勢、技術指標（RSI/MACD）、近期新聞、盤勢預估 |
| `medium` | 摘要表格中一行（代號、價格、漲跌幅、一句話備註） |
| `low` | 僅在出現異常活動時納入（成交量暴增、突發新聞、財報意外） |

### 檔案格式

`watchlist.md` 使用 Markdown 表格格式，欄位如下：

```markdown
| Ticker | 名稱 | 板塊 | 優先級 | 關注原因 | 加入日期 |
|--------|------|------|--------|----------|----------|
| TSMC   | 台積電 ADR | Semiconductors | high | AI 晶片供應鏈龍頭 | 2026-03-17 |
```

### 運作機制

1. **Stage 1（觸發）**：`high` 優先級個股自動合併至 `focus_tickers`，即使使用者僅輸入「盤前日報」
2. **Stage 3（數據抓取）**：為每支 `high` 個股額外抓取個別股票數據（價格、技術面、新聞、催化劑）
3. **Stage 5（報告結構）**：在「技術訊號」與「板塊熱力圖」之間插入「Watchlist 個股追蹤」章節

## 數據來源

| 來源 | 數據內容 | 存取方式 |
|------|----------|----------|
| Financial Datasets | 基本面、SEC 文件、內部人/機構交易 | MCP |
| yfinance | 指數、板塊、VIX、期貨 | Python |
| Alpha Vantage | RSI、MACD、SMA 技術指標 | REST API |
| Polymarket | 地緣政治賠率、Fed 利率賭盤 | Free API |
| Reddit | WSB、r/stocks、r/investing 社群情緒 | Python (praw) |
| Web Search | 新聞、經濟日曆、地緣政治 | 內建搜尋 |

## 專案結構

```
market-analyst/
├── SKILL.md                 # 技能定義與管線指令
├── watchlist.md             # 持久化使用者關注清單
├── readme.md                # README（English）
├── readme_zh-TW.md          # README（繁體中文，本檔案）
├── evals/
│   └── evals.json           # 測試案例
├── references/
│   ├── schema_index.md      # 數據流程圖與 schema 索引
│   └── schemas/
│       ├── 00_conventions.json   # 通用 JSON 規範
│       ├── 01_trigger.json       # Stage 1：觸發請求
│       ├── 02_portfolio.json     # Stage 2：投資組合閘門
│       ├── 03a_financial_datasets.json
│       ├── 03b_yfinance.json
│       ├── 03c_alpha_vantage.json
│       ├── 03d_polymarket.json
│       ├── 03e_reddit.json
│       ├── 03f_web_search.json   # Stage 3：數據來源 schemas
│       ├── 04_pipeline.json      # Stage 4：處理管線
│       ├── 05_report_structure.json  # Stage 5：章節矩陣
│       ├── 06_output.json        # Stage 6：本地化
│       └── 07_distribution.json  # Stage 7：分發
├── scripts/
│   ├── pipeline_runner.py   # 管線調度器
│   └── validate_json.py     # JSON schema 驗證器
└── output/                  # 生成的報告（依日期與類型）
    └── YYYY-MM-DD_<type>/
        ├── trigger_request.json
        ├── portfolio_gate.json
        ├── fetched/             # 各來源原始數據
        └── report_<type>_<date>_<locale>.md
```

## JSON 規範

管線中所有 JSON 檔案遵循以下規範以防止解析錯誤：

1. **編碼**：UTF-8 含 BOM（Windows 相容）
2. **時間戳記**：ISO 8601 含時區（如 `2026-03-17T08:00:00-04:00`）
3. **金額/小數**：使用字串型別精確表示（如 `"154.32"`），避免浮點數漂移
4. **Null 處理**：明確使用 `null`，不以空字串 `""` 或 `0` 替代
5. **陣列**：單一項目也使用陣列（如 `["AAPL"]`），消除純量/陣列歧義
6. **版本號**：每個檔案包含 `"schema_version": "1.0"`
7. **狀態碼**：每個結果包含 `"status": "ok" | "error" | "partial"`

## 授權

本技能供個人使用。市場數據來自公開 API，可能受各自服務條款約束。
