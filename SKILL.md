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
     - hover interpretation payload for key numeric items
     - insight scorecard with confidence and invalidation conditions
     - scenario probabilities and action playbook
      - dashboard cards / tables / chart references

## Insight-First Analysis Contract (Mandatory)

This skill must produce decision-useful analysis, not only data listing.

### Required analysis blocks per report

Every generated report must include all of the following:

1. **Executive Insights (at least 3)**
   - Each insight must include:
     - `signal`: bullish | bearish | neutral | mixed
     - `confidence`: high | medium | low
     - `type`: fact | inference | mixed
     - `evidence`: concrete data points (numbers, not generic text)
     - `invalidation`: explicit condition that would make the insight no longer valid
   - Rendering requirement (hard): the HTML must contain a dedicated section heading
     `Executive Insights` and at least 3 separately visible insight items (not collapsed into Top 3 only).

2. **Scenario analysis (at least 3 scenarios)**
   - Include `base`, `bull`, `bear` (or equivalent naming)
   - Assign probabilities that sum to 100%
   - For each scenario include:
     - trigger conditions
     - expected market behavior
     - recommended positioning / action

3. **Execution playbook**
   - Time-window based actions (for example open / mid-session / close, or pre-open / first 30 min)
   - Must include risk control guidance and stop/invalidation level

4. **Cross-market transmission**
   - Explain how external markets/macros transmit into target market behavior
   - Must separate directly sourced facts from model interpretation

### Prohibited output pattern

- Do not ship reports that are primarily a flat list of raw metrics.
- Do not provide generic commentary without evidence thresholds or invalidation conditions.
- If sources are missing, explicitly state impact on confidence and reduce certainty level.
- Do not treat `Top 3 takeaways` as a replacement for the `Executive Insights` section.
- If `Executive Insights` has fewer than 3 items, the run must fail fast instead of producing a report.

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

## Visual Style Specification (Mandatory)

All generated dashboards must follow a consistent design system. Treat these as required constraints,
not optional suggestions.

### 1) Design tokens

Every HTML report must define CSS variables (or equivalent design tokens) for:

- `--bg-page`, `--bg-card`, `--bg-muted`
- `--text-primary`, `--text-secondary`, `--text-muted`
- `--border-subtle`, `--border-strong`
- `--state-critical`, `--state-key`, `--state-watch`, `--state-context`
- `--stock-up`, `--stock-down`, `--stock-flat`
- `--focus-ring`, `--shadow-card`

Base UI requirements:

- Use card-based layout, 12-column desktop grid, single-column mobile stack.
- Typography must have clear hierarchy: headline, section title, body, numeric metric.
- Numeric cells for price/percentage/volume must use tabular numbers when possible.
- All key badges (`Critical`, `Key`, `Watch`, `Context`) must keep fixed color mapping across the report.

Component styling safety rules:

- Do not use generic class names like `.tag`, `.badge`, `.card-title` for critical UI elements.
- Use namespaced classes for generated reports (for example `ma-*`) to avoid host-page CSS collisions.
- Market convention chip must render as compact inline element, not full-width block:
  - use `display: inline-flex`
  - use `width: fit-content; max-width: 100%`
  - desktop default `white-space: nowrap`, mobile can wrap

### 2) Stock color semantics by market (critical)

Stock up/down colors must follow market convention, not a single global rule.

#### Taiwan market convention (`tw_stock`)

- `up` (漲): red (`--stock-up: #D62828`)
- `down` (跌): green (`--stock-down: #1F9D55`)
- `flat` (平盤): neutral gray (`--stock-flat: #6B7280`)

#### US market convention (`us_stock`)

- `up`: green (`--stock-up: #16A34A`)
- `down`: red (`--stock-down: #DC2626`)
- `flat`: neutral gray (`--stock-flat: #6B7280`)

### 3) Market convention resolution rules

The rendering layer must explicitly set `market_color_convention` and cannot guess silently.

- `tw_stock`: Taiwan equities/indices (e.g., TWSE, TPEX, TAIEX, tickers ending `.TW`/`.TWO`)
- `us_stock`: US equities/indices (e.g., NYSE, NASDAQ, S&P 500, Dow, tickers like AAPL/NVDA/MSFT)
- `mixed`: both Taiwan and US assets in one report; each section/table/chart must declare which
  convention it uses, and the legend must be shown in that section header

Do not bind color convention to locale alone. `zh-TW` reports may still be `us_stock`.

### 4) Accessibility and ambiguity prevention

Color cannot be the only carrier of meaning. Always pair color with at least one of:

- explicit `+/-` sign for percentage change
- directional icon (`▲`, `▼`, `→`) or text (`Up`, `Down`, `Flat`)
- optional row-level label for large tables

Minimum contrast target:

- normal text: WCAG AA (4.5:1)
- large text / key metrics: WCAG AA (3:1)

### 5) Chart and table coloring rules

- Candlestick and OHLC colors must follow the active section convention (`tw_stock` or `us_stock`).
- Heatmap legends must show numeric ranges and direction labels, not only colors.
- If one dashboard contains both TW and US heatmaps, legends must be separate and explicitly named.
- Use the same up/down colors for KPI chips, table deltas, sparkline highlights, and chart legends
  within the same market section.

### 6) Hover interpretation layer (required)

The dashboard must provide explanation-on-hover for major metrics and signals, so users can
understand meaning instead of only seeing numbers.

Minimum scope (must support):

- hero top-3 takeaways
- quick stats row metrics
- key rows in watchlist / sector heatmap / technical signals
- chart key points (latest value, breakout, divergence, unusual move)

Required tooltip fields (per highlighted item):

- `what_it_is`: what this metric/signal is
- `why_it_matters`: why it matters for decision-making
- `how_to_read`: interpretation rule (bullish/bearish/neutral conditions)
- `confidence`: `high` | `medium` | `low`
- `type`: `fact` | `inference` | `mixed`
- `risk_note`: what could invalidate this read

Interaction rules:

- Desktop: show on hover and keep accessible via focus.
- Mobile: support tap-to-open bottom sheet/popover with same content.
- Keep tooltip concise (recommended 1-4 short lines), no long paragraphs.
- Tooltip text must be localized (`zh-TW`, `zh-CN`) with market terminology adaptation.

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

1. Encoding: UTF-8 (without BOM preferred; with BOM only if downstream explicitly requires it)
2. Dates/times: ISO 8601 with timezone
3. Money/decimals: exact string values
4. Enums: closed sets validated at parse time
5. Nulls: explicit `null`
6. Arrays: always arrays
7. Versioning: root includes `"schema_version": "1.0"`
8. Status: each fetch/process result uses `"ok" | "error" | "partial"`

## Encoding Safety (Mandatory)

Prevent mojibake and `?` replacement in all locales/shells (especially Windows PowerShell + cp950):

1. Always read/write report artifacts as explicit UTF-8.
   - Python write: `open(path, "w", encoding="utf-8")`
   - Python read: `open(path, "r", encoding="utf-8")`
2. Never transcode output through legacy code pages (`cp950`, `big5`, etc.) and never use
   `errors="ignore"` / `errors="replace"` when handling report text.
3. Before running Python in shell contexts, set UTF-8 runtime flags:
   - `PYTHONUTF8=1`
   - `PYTHONIOENCODING=utf-8`
4. If terminal rendering looks broken, validate by reopening files with UTF-8 before concluding.
5. If any generated content contains unexpected `?` in CJK text, treat it as data corruption:
   regenerate the affected artifact from source data immediately.

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
