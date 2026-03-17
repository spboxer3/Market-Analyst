#!/usr/bin/env python3
"""
Market Analyst JSON Schema Validator

Validates pipeline JSON files against their corresponding schemas.
Usage:
    python validate_json.py <json_file> [--schema <schema_file>]
    python validate_json.py --all <pipeline_directory>

If --schema is not provided, the script auto-detects the schema based on
the 'source' or file naming convention.
"""

import json
import sys
import os
import re
from pathlib import Path
from datetime import datetime

SCHEMA_DIR = Path(__file__).parent.parent / "references" / "schemas"

# Auto-detection mapping: source field or filename pattern -> schema file
SOURCE_TO_SCHEMA = {
    "financial_datasets": "03a_financial_datasets.json",
    "yfinance": "03b_yfinance.json",
    "alpha_vantage": "03c_alpha_vantage.json",
    "polymarket": "03d_polymarket.json",
    "reddit": "03e_reddit.json",
    "web_search": "03f_web_search.json",
}

FILENAME_TO_SCHEMA = {
    "trigger_request": "01_trigger.json",
    "portfolio_gate": "02_portfolio.json",
    "integrated_data": "04_pipeline.json",
    "indicators": "04_pipeline.json",
    "charts_manifest": "04_pipeline.json",
    "report_draft": "04_pipeline.json",
    "report_structure": "05_report_structure.json",
    "output_manifest": "06_output.json",
    "distribution": "07_distribution.json",
}


class ValidationError:
    def __init__(self, path: str, message: str, severity: str = "error"):
        self.path = path
        self.message = message
        self.severity = severity  # "error" or "warning"

    def __str__(self):
        icon = "ERROR" if self.severity == "error" else "WARN"
        return f"[{icon}] {self.path}: {self.message}"


def validate_conventions(data: dict, path: str = "$") -> list[ValidationError]:
    """Validate data against the universal conventions (00_conventions.json)."""
    errors = []

    # Check schema_version
    if "schema_version" not in data:
        errors.append(ValidationError(path, "Missing required field 'schema_version'"))
    elif data["schema_version"] != "1.0":
        errors.append(ValidationError(
            f"{path}.schema_version",
            f"Expected '1.0', got '{data['schema_version']}'"
        ))

    # Recursively check for convention violations
    errors.extend(_check_conventions_recursive(data, path))

    return errors


def _check_conventions_recursive(obj, path: str) -> list[ValidationError]:
    """Recursively check for common convention violations."""
    errors = []

    if isinstance(obj, dict):
        for key, value in obj.items():
            current_path = f"{path}.{key}"

            # Check: empty strings where null should be used
            if value == "" and key not in ("question", "headline", "title", "summary", "description", "name"):
                errors.append(ValidationError(
                    current_path,
                    "Empty string found — use null instead of '' for missing data",
                    "warning"
                ))

            # Check: datetime fields have timezone
            if isinstance(value, str) and key in ("fetched_at", "requested_at", "checked_at",
                                                     "integrated_at", "computed_at", "generated_at",
                                                     "executed_at", "attempted_at", "delivered_at",
                                                     "created_at", "last_updated", "published_at",
                                                     "scheduled_at", "as_of", "resolved_at",
                                                     "drafted_at", "distribution_started_at",
                                                     "distribution_completed_at"):
                if value and not re.search(r'[+-]\d{2}:\d{2}$', value):
                    errors.append(ValidationError(
                        current_path,
                        f"Datetime '{value}' missing timezone offset. Use ISO 8601 with timezone."
                    ))

            # Check: ticker fields are uppercase
            if key == "ticker" and isinstance(value, str):
                if value != value.upper():
                    errors.append(ValidationError(
                        current_path,
                        f"Ticker '{value}' must be UPPERCASE",
                        "warning"
                    ))

            # Check: monetary fields should be strings, not numbers
            if key in ("price", "close", "open", "high", "low", "cost_basis_per_share",
                       "price_per_share", "market_value", "pnl", "market_cap", "revenue",
                       "net_income", "value", "total_volume", "fees"):
                if isinstance(value, (int, float)):
                    errors.append(ValidationError(
                        current_path,
                        f"Monetary field '{key}' should be a decimal-safe string, got {type(value).__name__}"
                    ))

            # Recurse
            errors.extend(_check_conventions_recursive(value, current_path))

    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            errors.extend(_check_conventions_recursive(item, f"{path}[{i}]"))

    return errors


def validate_status_field(data: dict, path: str = "$") -> list[ValidationError]:
    """Check that status field uses valid enum values."""
    errors = []
    if "status" in data:
        valid = {"ok", "error", "partial", "generated", "generating", "failed",
                 "delivered", "pending", "bounced", "unsubscribed"}
        if data["status"] not in valid:
            errors.append(ValidationError(
                f"{path}.status",
                f"Invalid status '{data['status']}'. Valid values: {sorted(valid)}"
            ))

        # If error status, must have error_message
        if data["status"] == "error" and not data.get("error_message"):
            errors.append(ValidationError(
                f"{path}.error_message",
                "Status is 'error' but 'error_message' is missing or null"
            ))
    return errors


def validate_file(filepath: str, schema_path: str = None) -> dict:
    """Validate a single JSON file. Returns validation report."""
    result = {
        "file": filepath,
        "valid": True,
        "errors": [],
        "warnings": [],
        "validated_at": datetime.now().astimezone().isoformat()
    }

    try:
        with open(filepath, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        result["valid"] = False
        result["errors"].append(f"JSON parse error: {e}")
        return result
    except FileNotFoundError:
        result["valid"] = False
        result["errors"].append(f"File not found: {filepath}")
        return result

    # Run convention checks
    all_issues = validate_conventions(data)
    all_issues.extend(validate_status_field(data))

    for issue in all_issues:
        if issue.severity == "error":
            result["errors"].append(str(issue))
            result["valid"] = False
        else:
            result["warnings"].append(str(issue))

    return result


def main():
    if len(sys.argv) < 2:
        print("Usage: python validate_json.py <json_file> [--schema <schema>]")
        print("       python validate_json.py --all <directory>")
        sys.exit(1)

    if sys.argv[1] == "--all":
        directory = sys.argv[2] if len(sys.argv) > 2 else "."
        json_files = list(Path(directory).glob("**/*.json"))
        results = []
        for f in json_files:
            if "schemas" not in str(f):  # Don't validate schema files themselves
                results.append(validate_file(str(f)))

        # Summary
        total = len(results)
        valid = sum(1 for r in results if r["valid"])
        print(f"\nValidation Summary: {valid}/{total} files passed")
        for r in results:
            status = "PASS" if r["valid"] else "FAIL"
            warnings = f" ({len(r['warnings'])} warnings)" if r["warnings"] else ""
            print(f"  [{status}] {r['file']}{warnings}")
            for err in r["errors"]:
                print(f"         {err}")
    else:
        result = validate_file(sys.argv[1])
        print(json.dumps(result, indent=2, ensure_ascii=False))
        sys.exit(0 if result["valid"] else 1)


if __name__ == "__main__":
    main()
