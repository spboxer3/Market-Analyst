#!/usr/bin/env python3
"""
Market Analyst Pipeline Runner

Orchestrates the 7-stage pipeline, managing JSON data flow between stages.
Each stage reads its input JSON, processes, and writes output JSON.

Usage:
    python pipeline_runner.py --report-type post_market [--portfolio portfolio.json]
    python pipeline_runner.py --trigger-json trigger_request.json
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def get_timestamp():
    """Get current timestamp in ISO 8601 with timezone."""
    return datetime.now().astimezone().isoformat()


def generate_report_id(report_type: str) -> str:
    """Generate a unique report ID."""
    now = datetime.now().astimezone()
    return f"{report_type}_{now.strftime('%Y%m%d_%H%M%S')}"


def create_workspace(report_id: str) -> Path:
    """Create workspace directory for this report run."""
    workspace = Path(f"runs/{report_id}")
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "fetched").mkdir(exist_ok=True)
    (workspace / "processed").mkdir(exist_ok=True)
    (workspace / "charts").mkdir(exist_ok=True)
    (workspace / "output").mkdir(exist_ok=True)
    return workspace


def write_json(filepath: Path, data: dict):
    """Write JSON with UTF-8 BOM encoding per conventions."""
    with open(filepath, "w", encoding="utf-8-sig") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  Written: {filepath}")


def read_json(filepath: Path) -> dict:
    """Read JSON with UTF-8 BOM support."""
    with open(filepath, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def stage1_trigger(report_type: str, user_instructions: str = None,
                   focus_tickers: list = None, focus_sectors: list = None) -> dict:
    """Stage 1: Parse trigger into structured request."""
    report_id = generate_report_id(report_type)

    input_mode = "minimal"
    if focus_tickers or focus_sectors:
        input_mode = "contextual"
    if focus_tickers and focus_sectors and user_instructions and len(user_instructions) > 50:
        input_mode = "detailed"

    return {
        "schema_version": "1.0",
        "report_id": report_id,
        "report_type": report_type,
        "input_mode": input_mode,
        "requested_at": get_timestamp(),
        "target_date": datetime.now().astimezone().strftime("%Y-%m-%d"),
        "locale_priority": ["zh-TW", "zh-CN"],
        "user_instructions": user_instructions,
        "focus_tickers": focus_tickers or [],
        "focus_sectors": focus_sectors or [],
        "custom_parameters": None
    }


def stage2_portfolio_gate(report_id: str, portfolio_path: str = None) -> dict:
    """Stage 2: Check portfolio availability."""
    result = {
        "schema_version": "1.0",
        "report_id": report_id,
        "mode": "without_portfolio",
        "checked_at": get_timestamp(),
        "portfolio": None
    }

    if portfolio_path and os.path.exists(portfolio_path):
        try:
            portfolio_data = read_json(Path(portfolio_path))
            result["mode"] = "with_portfolio"
            result["portfolio"] = portfolio_data
        except (json.JSONDecodeError, KeyError) as e:
            print(f"  Warning: Portfolio file invalid ({e}), falling back to without_portfolio")

    return result


def stage5_resolve_sections(report_type: str, portfolio_mode: str, report_id: str) -> dict:
    """Stage 5: Determine which sections to include."""
    inclusion_matrix = {
        "market_overview":   {"pre_market": True,  "post_market": True,  "weekly": True,  "monthly": True},
        "breaking_news":     {"pre_market": True,  "post_market": True,  "weekly": True,  "monthly": True},
        "technical_signals": {"pre_market": True,  "post_market": True,  "weekly": True,  "monthly": True},
        "sector_heatmap":    {"pre_market": False, "post_market": True,  "weekly": True,  "monthly": True},
        "polymarket":        {"pre_market": True,  "post_market": True,  "weekly": True,  "monthly": True},
        "reddit_sentiment":  {"pre_market": False, "post_market": True,  "weekly": True,  "monthly": False},
        "portfolio_pnl":     {"pre_market": False, "post_market": True,  "weekly": True,  "monthly": True},
        "tomorrow_preview":  {"pre_market": True,  "post_market": True,  "weekly": False, "monthly": False},
    }

    titles = {
        "market_overview":   ("市場總覽", "市场总览"),
        "breaking_news":     ("重大新聞", "重大新闻"),
        "technical_signals": ("技術訊號", "技术信号"),
        "sector_heatmap":    ("產業熱力圖", "行业热力图"),
        "polymarket":        ("預測市場", "预测市场"),
        "reddit_sentiment":  ("社群情緒", "社区情绪"),
        "portfolio_pnl":     ("投資組合損益", "投资组合损益"),
        "tomorrow_preview":  ("明日展望", "明日展望"),
    }

    sections = []
    for i, (section_id, matrix_row) in enumerate(inclusion_matrix.items(), 1):
        included = matrix_row.get(report_type, False)
        exclusion_reason = None

        if not included:
            exclusion_reason = "not_applicable_for_report_type"
        elif section_id == "portfolio_pnl" and portfolio_mode == "without_portfolio":
            included = False
            exclusion_reason = "portfolio_not_available"

        zh_tw, zh_cn = titles[section_id]
        sections.append({
            "section_number": i,
            "section_id": section_id,
            "title_zh_tw": zh_tw,
            "title_zh_cn": zh_cn,
            "included": included,
            "exclusion_reason": exclusion_reason
        })

    return {
        "schema_version": "1.0",
        "report_id": report_id,
        "report_type": report_type,
        "portfolio_mode": portfolio_mode,
        "resolved_at": get_timestamp(),
        "sections": sections
    }


def stage4_report_draft_placeholder(report_id: str, report_type: str, portfolio_mode: str) -> dict:
    """Stage 4 placeholder: insight-first draft skeleton."""
    return {
        "schema_version": "1.0",
        "report_id": report_id,
        "drafted_at": get_timestamp(),
        "report_metadata": {
            "report_type": report_type,
            "target_date": datetime.now().astimezone().strftime("%Y-%m-%d"),
            "portfolio_mode": portfolio_mode,
            "total_sections": 0
        },
        "insight_scorecard": [
            {
                "title": "Placeholder insight",
                "signal": "neutral",
                "confidence": "low",
                "type": "inference",
                "evidence": ["Data fetch pending"],
                "invalidation": "Replace after source data is available"
            },
            {
                "title": "Placeholder insight",
                "signal": "neutral",
                "confidence": "low",
                "type": "inference",
                "evidence": ["Data fetch pending"],
                "invalidation": "Replace after source data is available"
            },
            {
                "title": "Placeholder insight",
                "signal": "neutral",
                "confidence": "low",
                "type": "inference",
                "evidence": ["Data fetch pending"],
                "invalidation": "Replace after source data is available"
            }
        ],
        "scenarios": [
            {
                "name": "base",
                "probability": "50%",
                "trigger_conditions": ["Awaiting data"],
                "expected_behavior": "Awaiting data",
                "recommended_action": "Awaiting data"
            },
            {
                "name": "bull",
                "probability": "25%",
                "trigger_conditions": ["Awaiting data"],
                "expected_behavior": "Awaiting data",
                "recommended_action": "Awaiting data"
            },
            {
                "name": "bear",
                "probability": "25%",
                "trigger_conditions": ["Awaiting data"],
                "expected_behavior": "Awaiting data",
                "recommended_action": "Awaiting data"
            }
        ],
        "open_playbook": [
            {
                "time_window": "open",
                "condition": "Awaiting data",
                "action": "Awaiting data",
                "risk_control": "Awaiting data"
            },
            {
                "time_window": "mid_session",
                "condition": "Awaiting data",
                "action": "Awaiting data",
                "risk_control": "Awaiting data"
            },
            {
                "time_window": "late_session",
                "condition": "Awaiting data",
                "action": "Awaiting data",
                "risk_control": "Awaiting data"
            }
        ],
        "sections": []
    }


def run_pipeline(report_type: str, portfolio_path: str = None,
                 user_instructions: str = None, focus_tickers: list = None,
                 focus_sectors: list = None):
    """Run the full 7-stage pipeline."""
    print(f"=== Market Analyst Pipeline v1.0 ===")
    print(f"Report type: {report_type}")
    print()

    # Stage 1: Trigger
    print("[Stage 1] Parsing trigger...")
    trigger = stage1_trigger(report_type, user_instructions, focus_tickers, focus_sectors)
    report_id = trigger["report_id"]
    workspace = create_workspace(report_id)
    write_json(workspace / "trigger_request.json", trigger)

    # Stage 2: Portfolio Gate
    print("[Stage 2] Checking portfolio...")
    portfolio_gate = stage2_portfolio_gate(report_id, portfolio_path)
    write_json(workspace / "portfolio_gate.json", portfolio_gate)

    # Stage 3: Parallel Data Fetch (placeholder — actual fetching requires API keys)
    print("[Stage 3] Data fetch (6 sources)...")
    sources = ["financial_datasets", "yfinance", "alpha_vantage", "polymarket", "reddit", "web_search"]
    for source in sources:
        placeholder = {
            "schema_version": "1.0",
            "source": source,
            "status": "pending",
            "error_message": None,
            "fetched_at": get_timestamp(),
            "data": None
        }
        write_json(workspace / "fetched" / f"{source}.json", placeholder)

    # Stage 5: Section Resolution
    print("[Stage 5] Resolving report sections...")
    sections = stage5_resolve_sections(report_type, portfolio_gate["mode"], report_id)
    write_json(workspace / "report_structure.json", sections)

    # Stage 4: Draft placeholder (insight-first skeleton)
    print("[Stage 4] Creating report draft skeleton...")
    draft = stage4_report_draft_placeholder(report_id, report_type, portfolio_gate["mode"])
    write_json(workspace / "processed" / "report_draft.json", draft)

    # Stage 6: Output Manifest
    print("[Stage 6] Creating output manifest...")
    output_manifest = {
        "schema_version": "1.0",
        "report_id": report_id,
        "generated_at": get_timestamp(),
        "style_contract": {
            "market_color_convention": "us_stock",
            "stock_up_color": "#16A34A",
            "stock_down_color": "#DC2626",
            "stock_flat_color": "#6B7280",
            "uses_sign_and_icon_with_color": True,
            "interpretation_on_hover_enabled": True,
            "hover_targets": [
                "hero_takeaways",
                "quick_stats",
                "watchlist_rows",
                "technical_signals",
                "heatmap_cells",
                "chart_key_points"
            ]
        },
        "outputs": [
            {
                "locale": "zh-TW",
                "priority": "primary",
                "audience": "Taiwan + HK",
                "audience_share": "0.89",
                "file_path": f"output/{report_id}_zh-TW.html",
                "file_format": "html",
                "is_primary_human_deliverable": True,
                "file_size_bytes": None,
                "page_count": None,
                "status": "pending",
                "error_message": None,
                "terminology_adaptations": []
            },
            {
                "locale": "zh-CN",
                "priority": "secondary",
                "audience": "Mainland + NA",
                "audience_share": "0.11",
                "file_path": f"output/{report_id}_zh-CN.pdf",
                "file_format": "pdf",
                "is_primary_human_deliverable": False,
                "file_size_bytes": None,
                "page_count": None,
                "status": "pending",
                "error_message": None,
                "terminology_adaptations": []
            }
        ]
    }
    write_json(workspace / "output_manifest.json", output_manifest)

    print()
    print(f"Pipeline workspace: {workspace}")
    print(f"Report ID: {report_id}")
    included_count = sum(1 for s in sections["sections"] if s["included"])
    print(f"Sections included: {included_count}/8")
    print(f"Portfolio mode: {portfolio_gate['mode']}")
    print("Done. Data fetch stage requires API configuration to proceed.")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Market Analyst Pipeline Runner")
    parser.add_argument("--report-type", required=True,
                        choices=["pre_market", "post_market", "weekly", "monthly"])
    parser.add_argument("--portfolio", help="Path to portfolio.json")
    parser.add_argument("--instructions", help="User instructions text")
    parser.add_argument("--tickers", nargs="*", help="Focus tickers (space-separated)")
    parser.add_argument("--sectors", nargs="*", help="Focus sectors (space-separated)")

    args = parser.parse_args()
    run_pipeline(
        report_type=args.report_type,
        portfolio_path=args.portfolio,
        user_instructions=args.instructions,
        focus_tickers=args.tickers,
        focus_sectors=args.sectors
    )
