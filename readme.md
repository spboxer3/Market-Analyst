# Market Analyst

A Claude Code skill that generates structured US stock market analysis reports in Traditional and Simplified Chinese. It orchestrates parallel data fetches from 6 sources, processes them through a 7-stage pipeline, and outputs localized reports.

> [繁體中文版 README](readme_zh-TW.md)

## Features

- **4 report types**: Pre-market daily, post-market daily, weekly, monthly
- **6 data sources**: Financial Datasets, yfinance, Alpha Vantage, Polymarket, Reddit, web search
- **Persistent watchlist**: Track specific stocks across all reports with customizable priority levels
- **Portfolio support**: Optional portfolio integration for personalized P&L analysis
- **Localized output**: Reports in zh-TW (Traditional Chinese) and zh-CN (Simplified Chinese)
- **Auditable pipeline**: All intermediate data saved as JSON

## Quick Start

### Generate a report

```
/market-analyst 給我今日美股盤前日報
/market-analyst generate post-market report, focus on semiconductors
/market-analyst 週報，追蹤 TSMC、AAPL
```

### Manage your watchlist

```
加入 TSMC 到關注清單
從關注清單移除 AAPL
顯示我的關注清單
把 NVDA 優先級改為 high
```

## Architecture

```
Read watchlist.md → Trigger → Portfolio Gate → Parallel Data Fetch (6 sources)
  → Processing Pipeline (4 steps) → Report Structure (8+1 sections)
  → Output (localized) → Distribution (PDF)
```

### 7-Stage Pipeline

| Stage | Description | Output |
|-------|-------------|--------|
| 0 | Read watchlist | Watchlist entries injected into pipeline |
| 1 | Parse user command | `trigger_request.json` |
| 2 | Portfolio gate | `portfolio_gate.json` |
| 3 | Parallel data fetch (6 sources) | `fetched/*.json` |
| 4 | Processing (integrate → indicators → charts → template) | `integrated_data.json`, `indicators.json`, `charts_manifest.json` |
| 5 | Report structure (up to 9 sections) | Section inclusion matrix |
| 6 | Localization (zh-TW / zh-CN) | Localized report files |
| 7 | Distribution | PDF delivery |

### Report Types

| Type | ID | Schedule | Timezone |
|------|-----|----------|----------|
| Pre-market daily | `pre_market` | Daily 8:00 | America/New_York |
| Post-market daily | `post_market` | Daily 17:00 | America/New_York |
| Weekly | `weekly` | Friday close | America/New_York |
| Monthly | `monthly` | Month-end | America/New_York |

### Report Sections

| Section | pre_market | post_market | weekly | monthly | Requires |
|---------|:---------:|:-----------:|:------:|:-------:|----------|
| 1. Market overview | Y | Y | Y | Y | — |
| 2. Breaking news | Y | Y | Y | Y | — |
| 3. Technical signals | Y | Y | Y | Y | — |
| 3.5 Watchlist analysis | Y | Y | Y | Y | Watchlist |
| 4. Sector heatmap | — | Y | Y | Y | — |
| 5. Polymarket | Y | Y | Y | Y | — |
| 6. Reddit sentiment | — | Y | Y | — | — |
| 7. Portfolio P&L | — | Y | Y | Y | Portfolio |
| 8. Tomorrow preview | Y | Y | — | — | — |

## Watchlist

The watchlist is stored in **`watchlist.md`** at the skill root directory. It persists across sessions and automatically enriches every generated report.

### Priority Levels

| Priority | Behavior in report |
|----------|--------------------|
| `high` | Dedicated analysis paragraph: price action, technicals, news, outlook |
| `medium` | One-line summary in a table (ticker, price, change%, note) |
| `low` | Only appears on abnormal activity (volume spike, breaking news) |

### File Format

The watchlist uses a Markdown table with these columns:

```markdown
| Ticker | Name | Sector | Priority | Notes | Date Added |
```

## Data Sources

| Source | Data | Method |
|--------|------|--------|
| Financial Datasets | Fundamentals, SEC filings, insider/institutional trades | MCP |
| yfinance | Indices, sectors, VIX, futures | Python |
| Alpha Vantage | RSI, MACD, SMA technical indicators | REST API |
| Polymarket | Geopolitical odds, Fed rate bets | Free API |
| Reddit | WSB, r/stocks, r/investing sentiment | Python (praw) |
| Web search | News, economic calendar, geopolitics | Built-in |

## Project Structure

```
market-analyst/
├── SKILL.md                 # Skill definition & pipeline instructions
├── watchlist.md             # Persistent user watchlist
├── readme.md                # This file (English)
├── readme_zh-TW.md          # README in Traditional Chinese
├── evals/
│   └── evals.json           # Test cases for skill evaluation
├── references/
│   ├── schema_index.md      # Data flow diagram & schema registry
│   └── schemas/
│       ├── 00_conventions.json   # Universal JSON conventions
│       ├── 01_trigger.json       # Stage 1: Trigger request
│       ├── 02_portfolio.json     # Stage 2: Portfolio gate
│       ├── 03a_financial_datasets.json
│       ├── 03b_yfinance.json
│       ├── 03c_alpha_vantage.json
│       ├── 03d_polymarket.json
│       ├── 03e_reddit.json
│       ├── 03f_web_search.json   # Stage 3: Data source schemas
│       ├── 04_pipeline.json      # Stage 4: Processing pipeline
│       ├── 05_report_structure.json  # Stage 5: Section matrix
│       ├── 06_output.json        # Stage 6: Localization
│       └── 07_distribution.json  # Stage 7: Distribution
├── scripts/
│   ├── pipeline_runner.py   # Pipeline orchestration
│   └── validate_json.py     # JSON schema validation
└── output/                  # Generated reports (by date & type)
    └── YYYY-MM-DD_<type>/
        ├── trigger_request.json
        ├── portfolio_gate.json
        ├── fetched/             # Raw data from each source
        └── report_<type>_<date>_<locale>.md
```

## JSON Standards

All JSON files in the pipeline follow strict conventions to prevent parsing errors:

1. **Encoding**: UTF-8 with BOM (Windows compatibility)
2. **Timestamps**: ISO 8601 with timezone (e.g., `2026-03-17T08:00:00-04:00`)
3. **Money/Decimals**: String type with exact representation (e.g., `"154.32"`)
4. **Null handling**: Explicit `null`, never empty string or `0`
5. **Arrays**: Always arrays, even for single items
6. **Versioning**: Every file includes `"schema_version": "1.0"`
7. **Status codes**: Every result includes `"status": "ok" | "error" | "partial"`

## License

This skill is for personal use. Market data is sourced from public APIs and may be subject to their respective terms of service.
