from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from .report import format_text_with_options
from .rules import validate_submission
from .spec_loader import load_spec


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate a SQLite submission against the SQ26 schema")
    parser.add_argument("db_path", type=Path, help="Path to the SQLite .db file to validate")
    parser.add_argument(
        "--schema-csv",
        type=Path,
        default=Path("schema-definition") / "SQLite Meta Data Database Schema - schema.csv",
        help="Path to schema CSV definition",
    )
    parser.add_argument(
        "--data-types-tsv",
        type=Path,
        default=Path("schema-definition") / "SQLite Meta Data Database Schema - data_types.tsv",
        help="Path to data-types TSV definition",
    )
    parser.add_argument("--strict", action="store_true", help="Fail on warnings such as extra tables/columns")
    parser.add_argument("--json", action="store_true", dest="as_json", help="Print machine-readable JSON report")
    parser.add_argument(
        "--color",
        choices=("auto", "always", "never"),
        default="auto",
        help="Colorize text output (default: auto)",
    )
    return parser


def should_use_color(mode: str, as_json: bool) -> bool:
    if as_json:
        return False
    if mode == "always":
        return True
    if mode == "never":
        return False
    return sys.stdout.isatty() and "NO_COLOR" not in os.environ


def main() -> int:
    args = build_parser().parse_args()
    if not args.db_path.exists():
        if args.as_json:
            print(json.dumps({"ok": False, "error": f"File not found: {args.db_path}"}, indent=2))
        else:
            print(f"[ERROR] input.path: File not found: {args.db_path}")
        return 2

    try:
        spec = load_spec(args.schema_csv, args.data_types_tsv)
    except OSError as exc:
        if args.as_json:
            print(json.dumps({"ok": False, "error": f"Could not read schema definitions: {exc}"}, indent=2))
        else:
            print(f"[ERROR] input.schema: Could not read schema definitions: {exc}")
        return 2

    report = validate_submission(args.db_path, spec, strict=args.strict)
    if args.as_json:
        print(json.dumps(report.to_json(), indent=2))
    else:
        print(format_text_with_options(report, use_color=should_use_color(args.color, args.as_json)))

    return 1 if report.failed else 0
