---
name: market-analyst
description: >
  Generate comprehensive market analysis reports (盤前日報, 盤後日報, 週報, 月報) by orchestrating
  parallel data fetches from 6 sources (Financial Datasets, yfinance, Alpha Vantage, Polymarket,
  Reddit, Web search), processing through a 4-step pipeline, and outputting localized PDF reports
  in 繁體中文 and 簡體中文. Use this skill whenever the user asks for market reports, stock analysis,
  portfolio P&L summaries, sector heatmaps, technical indicators, sentiment analysis, or any
  financial market briefing — even if they don't explicitly say "market analyst". Also triggers
  on requests involving pre-market/post-market analysis, weekly/monthly market summaries,
  or combining multiple financial data sources into a single report. Additionally, this skill
  manages a persistent watchlist (`watchlist.md`) — trigger it when the user wants to add, remove,
  view, or modify their tracked stocks (e.g., "加入 TSMC 到關注清單", "watchlist add NVDA",
  "顯示我的關注清單"), or when they mention wanting to track or follow specific stocks in their reports.
---

# Market Analyst Skill

Generate structured market analysis reports following a 7-stage pipeline. All inter-stage data
is transmitted as standardized JSON to ensure parsing reliability downstream.

## Watchlist — 自訂關注個股

The user maintains a persistent watchlist file at **`watchlist.md`** (in the skill's base directory).
This file records which stocks the user wants every report to pay extra attention to.

### Watchlist File Location

```
<skill-base-dir>/watchlist.md
```

### Before generating any report, read `watchlist.md` first

This is a prerequisite step that happens before Stage 1. Read `watchlist.md` and parse the
markdown table to extract the current watchlist entries. Each entry has:
- **Ticker**: the stock symbol (e.g., `TSMC`, `AAPL`, `2330.TW`)
- **Priority**: `high` | `medium` | `low`
- **Notes**: user's reason for watching this stock

If `watchlist.md` does not exist or the table is empty, proceed with no watchlist overrides —
the report will be generated normally based on whatever the user specified in the command.

### How the watchlist affects report generation

When watchlist entries exist, they are injected into the pipeline at multiple points:

1. **Stage 1 (Trigger)**: Watchlist tickers with `high` priority are merged into `focus_tickers`
   in the trigger request, even if the user did not mention them in the command. This means a
   `minimal` mode command like "盤前日報" will automatically include watchlist stocks.

2. **Stage 3 (Data Fetch)**: For each `high`-priority watchlist stock, fetch individual stock
   data in addition to index-level data. This includes: current/pre-market price, recent price
   action, key technicals (RSI, MACD), recent news, and upcoming catalysts (earnings, ex-div).

3. **Stage 5 (Report Structure)**: Add a dedicated section to the report:

   **"Watchlist 個股追蹤"** — inserted between "Technical signals" (Section 3) and
   "Sector heatmap / Polymarket" (Section 4/5). This section contains:
   - For `high`-priority stocks: individual analysis paragraph with price action, technical
     signals, news catalysts, and a brief outlook/盤勢預估
   - For `medium`-priority stocks: one-line summary (price, change%, brief note) grouped
     in a table
   - `low`-priority stocks: only mentioned if there's breaking news or unusual volume

### Watchlist management commands

The user can manage their watchlist through natural language. When the user's command is a
watchlist management action (not a report request), execute it and confirm the result.

| Action | Example Commands | Behavior |
|--------|-----------------|----------|
| Add | "加入 TSMC 到關注清單", "watchlist add NVDA" | Add the ticker to `watchlist.md` table. Ask for priority if not specified (default: `medium`). |
| Remove | "從關注清單移除 AAPL", "watchlist remove AAPL" | Remove the row from the table. Confirm which stock was removed. |
| Show | "顯示我的關注清單", "watchlist show" | Display the current watchlist table to the user. |
| Update | "把 TSMC 優先級改為 high", "NVDA 備註：追蹤 GTC" | Edit the specified field in the existing row. |
| Clear | "清空關注清單", "watchlist clear" | Remove all entries (keep table header). Confirm before executing. |

When modifying `watchlist.md`, always update the `last_updated` field in the frontmatter
to the current date.

## Architecture Overview

```
Read watchlist.md → Trigger → Portfolio Gate → Parallel Data Fetch (6 sources)
  → Processing Pipeline (4 steps) → Report Structure (8+1 sections) → Output (localized)
  → Distribution (PDF)
```

## Stage 1: Trigger — Parse User Command

Accept a natural language command and resolve it into a structured trigger request.

**Report types** (exactly one must be selected):
| Type | ID | Schedule | Timezone |
|------|-----|----------|----------|
| 盤前日報 | `pre_market` | Daily ET 8:00 | America/New_York |
| 盤後日報 | `post_market` | Daily ET 17:00 | America/New_York |
| 週報 | `weekly` | Friday close | America/New_York |
| 月報 | `monthly` | Month-end | America/New_York |

**Input modes** — the user's command falls into one of three levels of detail:
- `minimal`: just the report type, e.g. "盤前日報"
- `contextual`: report type + focus areas, e.g. "盤後日報, focus on tech sector and TSMC"
- `detailed`: full specification with tickers, date ranges, special requests

Parse the command into `trigger_request.json`. See `references/schemas/01_trigger.json` for the
exact schema. If the report type is ambiguous, ask the user to clarify — never guess.

## Stage 2: Portfolio Gate

Before generating any report, check whether the user has portfolio data available.

- **Mode A — With portfolio**: The user provides or has previously stored `portfolio.json`
  containing holdings (ticker, shares, cost_basis, trades). The report will include personalized
  sections like Portfolio P&L.
- **Mode B — Without portfolio**: Skip all personal data. Generate a public-only report.

The gate outputs `portfolio_gate.json` which downstream stages read to decide which sections
to include. The portfolio data schema is in `references/schemas/02_portfolio.json`.

Portfolio data is sensitive — never log raw holdings to shared outputs. The JSON schema
enforces that trade history uses ISO 8601 dates and decimal-safe string amounts to avoid
floating-point drift.

## Stage 3: Parallel Data Fetch

Fetch from all 6 sources concurrently. Each source writes its own JSON file into a `fetched/`
directory. The schemas are strict so that the processing pipeline can merge them without
ambiguity.

| Source | Data | Access Method | Schema File |
|--------|------|---------------|-------------|
| Financial Datasets | Fundamentals, SEC, insider, institutional | MCP | `03a_financial_datasets.json` |
| yfinance | Index, sector, VIX, futures | Python (`yfinance`) | `03b_yfinance.json` |
| Alpha Vantage | RSI, MACD, SMA indicators | REST API | `03c_alpha_vantage.json` |
| Polymarket | Geopolitical odds, Fed bets | Free API | `03d_polymarket.json` |
| Reddit | WSB, r/stocks, r/investing sentiment | Python (`praw`/`asyncpraw`) | `03e_reddit.json` |
| Web search | News, econ calendar, geopolitics | Built-in web search | `03f_web_search.json` |

**Critical rules for data fetching:**
- Every fetch must include a `fetched_at` timestamp (ISO 8601 with timezone) so staleness
  can be detected.
- If a source fails, write a result with `"status": "error"` and a human-readable `error_message`.
  Never silently drop a source — the processing pipeline needs to know what's missing.
- Numeric values that represent money use `string` type with exact decimal representation
  (e.g., `"154.32"`) to prevent floating-point issues. The schema files document which fields
  are decimal-safe strings vs. regular numbers.

## Stage 4: Processing Pipeline

Four sequential steps that transform raw fetched data into report-ready content.

1. **Integrate** — Merge all 6 source JSONs into a unified `integrated_data.json`. Resolve
   conflicts (e.g., different close prices from different sources) by preferring the source
   with the most recent `fetched_at`.
2. **Indicators** — Compute derived metrics (moving averages, RSI confirmation, sector
   rotation signals). Output `indicators.json`.
3. **Charts** — Generate chart artifacts using matplotlib/plotly. Save as PNG/SVG files.
   Output `charts_manifest.json` listing all generated chart paths and their metadata.
4. **Template** — Apply the report template using ReportLab. Combine text sections and
   chart images into the final layout. Output `report_draft.json` with the structured
   content ready for localization.

See `references/schemas/04_pipeline.json` for the schemas of each intermediate output.

## Stage 5: Report Structure

The report has up to 9 sections. Each section is conditionally included based on report type,
portfolio mode, and watchlist status. The inclusion matrix:

| Section | pre_market | post_market | weekly | monthly | Requires |
|---------|-----------|-------------|--------|---------|----------|
| 1. Market overview | Yes | Yes | Yes | Yes | — |
| 2. Breaking news | Yes | Yes | Yes | Yes | — |
| 3. Technical signals | Yes | Yes | Yes | Yes | — |
| **3.5 Watchlist 個股追蹤** | **Yes** | **Yes** | **Yes** | **Yes** | **Watchlist** |
| 4. Sector heatmap | No | Yes | Yes | Yes | — |
| 5. Polymarket | Yes | Yes | Yes | Yes | — |
| 6. Reddit sentiment | No | Yes | Yes | No | — |
| 7. Portfolio P&L | No | Yes | Yes | Yes | Portfolio |
| 8. Tomorrow preview | Yes | Yes | No | No | — |

**Section 3.5 — Watchlist 個股追蹤** is included in ALL report types whenever `watchlist.md`
contains at least one entry. It appears after the broad-market technical analysis and before
sector/prediction data, so the reader flows from "market-level → individual stocks → sectors."

For each watchlist stock, the depth of analysis depends on its priority:

- **high**: Full analysis paragraph — price/pre-market quote, technical indicators (RSI, MACD),
  recent news, upcoming catalysts, and a brief 盤勢預估 (outlook/expected price action)
- **medium**: One-line row in a summary table (ticker, price, change%, one-sentence note)
- **low**: Only appears if there's abnormal activity (volume spike, breaking news, earnings surprise)

The report structure schema is in `references/schemas/05_report_structure.json`.

## Stage 6: Output — Localization

Generate two localized versions of the report:

| Version | Locale | Audience | Priority | Share |
|---------|--------|----------|----------|-------|
| 繁體中文版 | `zh-TW` | Taiwan + HK | Primary | ~89% |
| 簡體中文版 | `zh-CN` | Mainland + NA | Secondary | ~11% |

Localization is more than character conversion — financial terminology differs between
regions (e.g., 殖利率 vs 收益率, 融資 vs 融资). The output schema tracks which locale
each PDF corresponds to. See `references/schemas/06_output.json`.

## Stage 7: Distribution

Deliver PDF reports to catedward.com subscribers.

- **Current**: Manual delivery
- **Future**: Resend API for automated email with PDF attachment

The distribution manifest (`07_distribution.json`) tracks delivery status per subscriber.
Email API integration is reserved but not yet active.

## JSON Schema Standards

All JSON files in this pipeline follow these conventions to prevent parsing errors:

1. **Encoding**: UTF-8 with BOM for Windows compatibility
2. **Dates/Times**: ISO 8601 with timezone (`2026-03-17T08:00:00-04:00`), never Unix timestamps
3. **Money/Decimals**: String type with exact representation (`"154.32"`), never bare floats
4. **Enums**: Closed sets validated at parse time (e.g., report_type is one of 4 values)
5. **Null handling**: Explicit `null` for missing data, never empty string `""` or `0`
6. **Arrays**: Always arrays even for single items (no scalar/array ambiguity)
7. **Versioning**: Every JSON file includes `"schema_version": "1.0"` at the root
8. **Status codes**: Every fetch/process result includes `"status": "ok" | "error" | "partial"`

Read `references/schemas/00_conventions.json` for the full convention specification that
all schemas inherit from.

## Quick Start

### Generate a report
1. User says something like "幫我生成今天的盤後日報" or "generate post-market report"
2. Read `watchlist.md` → parse trigger → check portfolio gate → fetch data → process → generate → deliver
3. All intermediate data is saved as JSON in the working directory for auditability

### Manage watchlist
1. User says "加入 TSMC 到關注清單" → skill edits `watchlist.md`, adds TSMC row
2. User says "顯示我的關注清單" → skill reads `watchlist.md`, displays the table
3. Next report generation automatically picks up the watchlist and includes focused analysis
