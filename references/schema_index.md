# Market Analyst JSON Schema Index

All schemas follow the conventions defined in `schemas/00_conventions.json`.

## Pipeline Data Flow

```
[User Command]
      │
      ▼
┌─────────────────┐     ┌─────────────────┐
│ 01_trigger.json │────▶│ 02_portfolio.json│
│ trigger_request  │     │ portfolio_gate   │
└─────────────────┘     └────────┬─────────┘
                                 │
                    ┌────────────┼────────────┐
                    ▼            ▼            ▼
              ┌──────────┐ ┌──────────┐ ┌──────────┐
              │03a       │ │03b       │ │03c       │
              │financial │ │yfinance  │ │alpha     │
              │datasets  │ │          │ │vantage   │
              └────┬─────┘ └────┬─────┘ └────┬─────┘
                   │            │            │
              ┌──────────┐ ┌──────────┐ ┌──────────┐
              │03d       │ │03e       │ │03f       │
              │polymarket│ │reddit    │ │web_search│
              └────┬─────┘ └────┬─────┘ └────┬─────┘
                   │            │            │
                   └────────────┼────────────┘
                                │
                                ▼
                    ┌─────────────────────┐
                    │ 04_pipeline.json    │
                    │ integrated_data     │
                    │ indicators          │
                    │ charts_manifest     │
                    │ report_draft        │
                    └─────────┬───────────┘
                              │
                    ┌─────────┴───────────┐
                    ▼                     ▼
          ┌─────────────────┐   ┌─────────────────┐
          │05_report        │   │06_output.json   │
          │structure.json   │   │ output_manifest  │
          └─────────────────┘   └────────┬────────┘
                                         │
                                         ▼
                               ┌─────────────────┐
                               │07_distribution   │
                               │.json             │
                               └─────────────────┘
```

## Schema Files

| File | Stage | Description |
|------|-------|-------------|
| `00_conventions.json` | All | Universal conventions: encoding, datetime, decimal safety, null handling |
| `01_trigger.json` | 1 | Parsed user command → report type, mode, focus areas |
| `02_portfolio.json` | 2 | Portfolio gate decision + holdings/trades data |
| `03a_financial_datasets.json` | 3 | Fundamentals, SEC, insider, institutional (MCP) |
| `03b_yfinance.json` | 3 | Indices, sectors, VIX, futures (Python) |
| `03c_alpha_vantage.json` | 3 | RSI, MACD, SMA technical indicators (API) |
| `03d_polymarket.json` | 3 | Prediction market odds and probabilities (Free) |
| `03e_reddit.json` | 3 | Social sentiment from WSB/stocks/investing (Python) |
| `03f_web_search.json` | 3 | News, economic calendar, geopolitics (Built-in) |
| `04_pipeline.json` | 4 | Processing: integrate → indicators → charts → template |
| `05_report_structure.json` | 5 | Section inclusion matrix (8 sections × 4 report types) |
| `06_output.json` | 6 | Localized output manifest (HTML-first, plus optional PDF/MD/JSON) |
| `07_distribution.json` | 7 | Delivery tracking per subscriber |

## Key Anti-Parsing-Error Rules

1. **Decimal-safe strings** — All money/price/percentage fields are `"string"` not `number`
2. **Explicit null** — Never use `""`, `0`, or `-1` for missing data
3. **ISO 8601 + timezone** — Every timestamp includes offset (`-04:00`, `+08:00`)
4. **Always arrays** — Single items are `["AAPL"]` not `"AAPL"` for list fields
5. **schema_version** — Every file includes `"schema_version": "1.0"` for version checking
6. **status + error_message** — Every fetch/process result reports its status
