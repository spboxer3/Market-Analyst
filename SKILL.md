---
name: market-analyst
description: >
  Generate structured US market analysis reports (盤前日報, 盤後日報, 週報, 月報) with a UI-first
  output flow. The skill orchestrates parallel fetches from 6 sources, processes the data through
  a 7-stage pipeline, and produces localized zh-TW / zh-CN dashboard-style reports. Use this skill
  whenever the user asks for market reports, stock analysis, portfolio P&L, sector heatmaps,
  technical indicators, sentiment analysis, or any financial market briefing. The skill also owns
  the persistent watchlist file `watchlist.md`.
---

# Market Analyst Skill

Generate structured market reports through a 7-stage pipeline. All inter-stage data is saved as
standardized JSON, but the user-facing deliverable is no longer markdown-first or PDF-first.

## Output Policy: UI First

This skill must now generate reports as a visual interface by default.

### Required user-facing outputs

For every report run, produce outputs in this order:

1. **Primary deliverable: HTML dashboard**
   - A styled, readable, single-file or asset-backed HTML report.
   - Must look intentional, not like raw markdown rendered in a browser.
   - Must support both desktop and mobile widths.
   - Must use information hierarchy, cards, tables, callouts, and emphasis.

2. **Secondary deliverables: structured source artifacts**
   - JSON files for fetched and processed data.
   - Optional markdown draft for auditability.

3. **Optional export deliverables**
   - PDF only as an export of the dashboard or report, not as the primary presentation layer.

If the environment cannot produce a PDF, still ship the HTML dashboard and JSON artifacts.
Do not fall back to “just markdown” unless the user explicitly asks for markdown-only output.

## Information Highlighting Policy

The skill must identify and visually mark important information instead of treating every point
with equal weight.

### Importance levels

Every major point in the report should be tagged into one of these categories:

- `critical`: market-moving data, regime shifts, surprise macro prints, war / Fed / earnings shocks
- `high`: strong directional signals, broad index breakdowns, major sector rotation, urgent catalysts
- `medium`: supporting context, secondary movers, sentiment changes
- `low`: background detail, nice-to-have context, audit notes

### Required UI annotations

The HTML dashboard must visually distinguish important items using consistent labels, such as:

- `Critical`
- `Key`
- `Watch`
- `Context`

At minimum, the UI must highlight:

- Top 3 market-moving takeaways
- The most important macro event(s) ahead
- Largest risk to next session / next week
- Strongest or weakest major index / sector / watchlist name
- Any inference vs directly sourced fact

### Fact vs inference rules

The dashboard must clearly separate:

- **Directly sourced facts**
- **Model inference / interpretation**

When a statement is inferred rather than directly quoted from a source or dataset, label it clearly,
for example:

- `Inference`
- `Interpretation`
- `Scenario`

## Watchlist

The user maintains a persistent watchlist file at:

```
<skill-base-dir>/watchlist.md
```

Read `watchlist.md` before generating any report. Parse the markdown table and extract:

- `Ticker`
- `Priority`: `high` | `medium` | `low`
- `Notes`

If the file does not exist or the table is empty, proceed without watchlist overrides.

### How watchlist affects reports

1. **Stage 1 (Trigger)**:
   - Merge `high`-priority watchlist tickers into `focus_tickers`.

2. **Stage 3 (Data Fetch)**:
   - Fetch stock-specific data for `high`-priority watchlist names.

3. **Stage 5 (Report Structure)**:
   - Insert a dedicated **Watchlist 個股追蹤** section after Technical Signals.

### Watchlist presentation rules

- `high`: dedicated card with price action, technicals, catalysts, and outlook
- `medium`: compact table row with 1-line summary
- `low`: only show when there is abnormal volume, breaking news, or a meaningful catalyst

## Watchlist management commands

If the user request is a watchlist action rather than a report request, execute it and confirm.

| Action | Example | Behavior |
|---|---|---|
| Add | `加入 TSMC 到關注清單`, `watchlist add NVDA` | Add the row; default priority is `medium` if unspecified |
| Remove | `從關注清單移除 AAPL`, `watchlist remove AAPL` | Remove the row and confirm |
| Show | `顯示我的關注清單`, `watchlist show` | Display the current table |
| Update | `把 TSMC 優先級改為 high`, `NVDA 備註：追蹤 GTC` | Update the existing row |
| Clear | `清空關注清單`, `watchlist clear` | Clear all rows after confirmation |

When modifying `watchlist.md`, always update the frontmatter `last_updated` field.

## Architecture Overview

```
Read watchlist.md -> Trigger -> Portfolio Gate -> Parallel Data Fetch (6 sources)
  -> Processing Pipeline (4 steps) -> Report Structure (8+1 sections)
  -> UI Rendering (HTML dashboard first) -> Optional PDF export -> Distribution
```

## Stage 1: Trigger

Resolve the natural-language user request into `trigger_request.json`.

### Report types

| Type | ID | Schedule | Timezone |
|---|---|---|---|
| 盤前日報 | `pre_market` | Daily ET 08:00 | America/New_York |
| 盤後日報 | `post_market` | Daily ET 17:00 | America/New_York |
| 週報 | `weekly` | Friday close | America/New_York |
| 月報 | `monthly` | Month-end | America/New_York |

### Input modes

- `minimal`: only the report type
- `contextual`: report type plus focus sectors / tickers / emphasis
- `detailed`: explicit scope, date range, tickers, and custom requests

If the report type is ambiguous, ask the user to clarify. Never guess.

## Stage 2: Portfolio Gate

Check whether portfolio data is available.

- `with_portfolio`: include personal sections such as P&L
- `without_portfolio`: generate a public-only report

Never expose raw sensitive portfolio details in the rendered UI beyond what is needed.

## Stage 3: Parallel Data Fetch

Fetch from all 6 sources concurrently and write source-specific JSON into `fetched/`.

| Source | Data | Access Method | Schema |
|---|---|---|---|
| Financial Datasets | Fundamentals, SEC, insider, institutional | MCP | `03a_financial_datasets.json` |
| yfinance | Index, sector, VIX, futures | Python | `03b_yfinance.json` |
| Alpha Vantage | RSI, MACD, SMA indicators | REST API | `03c_alpha_vantage.json` |
| Polymarket | Geopolitical odds, Fed bets | Free API | `03d_polymarket.json` |
| Reddit | WSB, r/stocks, r/investing sentiment | Python | `03e_reddit.json` |
| Web search | News, economic calendar, geopolitics | Built-in web search | `03f_web_search.json` |

### Critical fetch rules

- Every fetch must include `fetched_at` in ISO 8601 with timezone.
- If a source fails, write `"status": "error"` plus a readable `error_message`.
- Never silently drop a source.
- Monetary values use decimal-safe strings.

## Stage 4: Processing Pipeline

Process raw data in four steps:

1. **Integrate**
   - Merge the fetched data into `integrated_data.json`.

2. **Indicators**
   - Compute derived metrics and signal summaries in `indicators.json`.

3. **Charts**
   - Generate chart artifacts and store them in `charts_manifest.json`.

4. **Template / View Model**
   - Build a structured `report_draft.json` that includes:
     - ordered sections
     - callouts / highlight items
     - fact vs inference labeling
     - dashboard cards / tables / chart references

## Stage 5: Report Structure

The report may include up to 9 sections:

| Section | pre_market | post_market | weekly | monthly | Requires |
|---|---|---|---|---|---|
| 1. Market overview | Yes | Yes | Yes | Yes | - |
| 2. Breaking news | Yes | Yes | Yes | Yes | - |
| 3. Technical signals | Yes | Yes | Yes | Yes | - |
| 3.5 Watchlist 個股追蹤 | Yes | Yes | Yes | Yes | Watchlist |
| 4. Sector heatmap | No | Yes | Yes | Yes | - |
| 5. Polymarket | Yes | Yes | Yes | Yes | - |
| 6. Reddit sentiment | No | Yes | Yes | No | - |
| 7. Portfolio P&L | No | Yes | Yes | Yes | Portfolio |
| 8. Tomorrow preview | Yes | Yes | No | No | - |

### UI layout rules

The dashboard should generally render as:

1. Header with market date and report type
2. Hero strip with top 3 takeaways
3. Quick stats row for major indices / key metrics
4. Section cards for news, technicals, watchlist, sectors, prediction markets, sentiment
5. Forward-looking calendar / next catalysts
6. Source and methodology footer

Do not render the report as one long text column unless the user explicitly asks for a text-only version.

## Stage 6: Output and Localization

Generate at least two localized report variants:

| Version | Locale | Audience | Priority |
|---|---|---|---|
| 繁體中文版 | `zh-TW` | Taiwan + HK | Primary |
| 簡體中文版 | `zh-CN` | Mainland + NA | Secondary |

Localization must adapt terminology, not just convert characters.

### Required output files

Each report run should aim to create:

- `output/report_<type>_<date>_<locale>.html`
- `output/report_<type>_<date>_<locale>.json` or `report_draft.json`
- optional `output/report_<type>_<date>_<locale>.pdf`
- optional `output/report_<type>_<date>_<locale>.md`

The HTML file is the main deliverable.

## Stage 7: Distribution

Current delivery may remain manual, but the deliverable referenced for human consumption should be
the HTML dashboard first, not only the PDF.

## JSON Standards

All JSON files in this pipeline follow these rules:

1. Encoding: UTF-8 with BOM
2. Dates/times: ISO 8601 with timezone
3. Money/decimals: exact string values
4. Enums: closed sets validated at parse time
5. Nulls: explicit `null`
6. Arrays: always arrays
7. Versioning: root includes `"schema_version": "1.0"`
8. Status: each fetch/process result uses `"ok" | "error" | "partial"`

## Quick Start

### Generate a report

1. Read `watchlist.md`
2. Parse the trigger
3. Check the portfolio gate
4. Fetch data
5. Process and compute highlights
6. Render the HTML dashboard first
7. Export PDF only if useful / requested / supported

### Important implementation note

When this skill is used in future turns, the assistant should proactively produce:

- a presentable HTML UI
- highlighted key takeaways
- explicit fact vs inference labeling
- source links

It should not default to plain markdown plus PDF unless the user explicitly requests that format.
