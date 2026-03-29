# Market Analyst

A Claude Code skill that generates structured US stock market analysis reports in Traditional and Simplified Chinese. It orchestrates parallel data fetches from 6 sources, processes them through a 7-stage pipeline, and outputs localized reports.

## What changed

This skill no longer treats markdown and PDF as the primary presentation layer.

New default behavior:

- Generate an HTML dashboard first
- Highlight important information by severity
- Distinguish sourced facts from model inference
- Keep JSON artifacts for auditability
- Export PDF only as a secondary format

## Core output contract

For each report run, aim to create:

- `output/report_<type>_<date>_<locale>.html`
- `processed/report_draft.json`
- optional `output/report_<type>_<date>_<locale>.md`
- optional `output/report_<type>_<date>_<locale>.pdf`

The HTML dashboard is the primary human-facing deliverable.

## Highlighting rules

Every report should visually annotate major items using these levels:

- `Critical`
- `Key`
- `Watch`
- `Context`

At minimum, surface:

- top 3 market-moving takeaways
- next important macro event
- biggest risk into the next session / week
- strongest or weakest index / sector / watchlist name
- all inference statements, clearly labeled as inference

## Report flow

```
Read watchlist.md -> Trigger -> Portfolio Gate -> Parallel Data Fetch
  -> Integrate -> Indicators -> Charts -> Report Draft
  -> HTML Dashboard -> Optional PDF export
```

## Report types

- `pre_market`
- `post_market`
- `weekly`
- `monthly`

## Watchlist

The persistent watchlist lives in `watchlist.md`.

Priority behavior:

- `high`: dedicated analysis card
- `medium`: compact summary row
- `low`: include only on abnormal activity or meaningful news

## Design expectations

The dashboard should:

- work on desktop and mobile
- use cards, sections, tables, and callouts
- avoid raw markdown styling
- make the information hierarchy obvious at a glance

## Data sources

- Financial Datasets
- yfinance
- Alpha Vantage
- Polymarket
- Reddit
- Web search
