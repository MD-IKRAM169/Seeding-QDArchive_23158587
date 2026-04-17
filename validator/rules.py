from __future__ import annotations

import re
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from .report import Issue, ValidationReport
from .spec_loader import ValidationSpec
from .sqlite_inspector import connect_readonly, get_table_info, list_tables, query_column_values


EXPECTED_FILE_RE = re.compile(r"^\d{8}-(?:seeding|sq26)\.db$", re.IGNORECASE)


@dataclass(frozen=True)
class EnumTarget:
    table: str
    column: str
    enum_key: str


@dataclass(frozen=True)
class ValidationConfig:
    filename_pattern: re.Pattern[str]
    filename_hint: str
    enum_targets: tuple[EnumTarget, ...]


DEFAULT_CONFIG = ValidationConfig(
    filename_pattern=EXPECTED_FILE_RE,
    filename_hint="'<8-digit-student-id>-seeding.db' or '<8-digit-student-id>-sq26.db'",
    enum_targets=(
        EnumTarget("FILES", "status", "DOWNLOAD_RESULT"),
        EnumTarget("PERSON_ROLE", "role", "PERSON_ROLE"),
        EnumTarget("LICENSES", "license", "LICENSE"),
    ),
)


def _summarize_values(values: list[str], max_items: int = 10) -> str:
    if len(values) <= max_items:
        return ", ".join(values)
    shown = ", ".join(values[:max_items])
    return f"{shown}, ... ({len(values) - max_items} more)"


def _type_matches(expected: str, actual: str) -> bool:
    actual_upper = actual.upper()
    if expected == "INTEGER":
        return "INT" in actual_upper
    return True if expected == "TEXT" else expected in actual_upper


def _validate_filename(path: Path, strict: bool, issues: list[Issue], config: ValidationConfig) -> None:
    if config.filename_pattern.match(path.name):
        issues.append(Issue("pass", "filename.pattern", f"Filename '{path.name}' matches expected pattern"))
        return

    message = (
        f"Filename '{path.name}' does not match expected pattern "
        f"{config.filename_hint}"
    )
    if strict:
        issues.append(Issue("error", "filename.pattern", message))
    else:
        issues.append(Issue("warning", "filename.pattern", message))


def _validate_schema(conn: sqlite3.Connection, spec: ValidationSpec, strict: bool, issues: list[Issue]) -> None:
    actual_tables = list_tables(conn)
    required_tables = set(spec.tables.keys())

    missing_tables = sorted(required_tables - actual_tables)
    extra_tables = sorted(actual_tables - required_tables)

    if not missing_tables:
        issues.append(Issue("pass", "schema.tables.required", "All required tables are present"))
    else:
        issues.append(Issue("error", "schema.tables.required", f"Missing tables: {', '.join(missing_tables)}"))

    if extra_tables:
        sev = "error" if strict else "warning"
        issues.append(Issue(sev, "schema.tables.extra", f"Extra tables found: {', '.join(extra_tables)}"))

    for table_name, table_spec in spec.tables.items():
        if table_name not in actual_tables:
            continue
        info = get_table_info(conn, table_name)
        actual_cols = set(info.columns.keys())

        required_cols = {name for name, col in table_spec.columns.items() if col.required}
        all_expected_cols = set(table_spec.columns.keys())
        missing_cols = sorted(required_cols - actual_cols)

        if missing_cols:
            issues.append(
                Issue(
                    "error",
                    "schema.columns.required",
                    f"Table {table_name} missing required columns: {', '.join(missing_cols)}",
                )
            )
        else:
            issues.append(
                Issue("pass", "schema.columns.required", f"Table {table_name} has all required columns")
            )

        extras = sorted(actual_cols - all_expected_cols)
        if extras:
            sev = "error" if strict else "warning"
            issues.append(
                Issue(sev, "schema.columns.extra", f"Table {table_name} has extra columns: {', '.join(extras)}")
            )

        for column_name, column_spec in table_spec.columns.items():
            if column_name not in info.columns:
                continue
            if not _type_matches(column_spec.declared_type, info.columns[column_name]):
                sev = "error" if strict else "warning"
                issues.append(
                    Issue(
                        sev,
                        "schema.columns.type",
                        f"Table {table_name}.{column_name} has type '{info.columns[column_name]}', expected '{column_spec.declared_type}'",
                    )
                )


def _validate_enum_values(
    conn: sqlite3.Connection,
    spec: ValidationSpec,
    strict: bool,
    issues: list[Issue],
    config: ValidationConfig,
) -> None:
    for target in config.enum_targets:
        table = target.table
        column = target.column
        enum_key = target.enum_key
        if table not in spec.tables:
            continue

        allowed = spec.enums.get(enum_key, set())
        if not allowed:
            continue

        try:
            values = query_column_values(conn, table, column)
        except (sqlite3.DatabaseError, ValueError) as exc:
            severity = "error" if strict else "warning"
            issues.append(
                Issue(
                    severity,
                    "values.query",
                    f"Could not read {table}.{column} values for {enum_key}: {exc}",
                )
            )
            continue

        if enum_key == "LICENSE":
            invalid = sorted(v for v in values if not _is_valid_license(v, allowed))
            if invalid:
                sev = "error" if strict else "warning"
                issues.append(
                    Issue(
                        sev,
                        "values.license",
                        f"Unrecognized license values in {table}.{column}: {_summarize_values(invalid)}",
                    )
                )
            else:
                issues.append(Issue("pass", "values.license", f"All non-null values in {table}.{column} are recognized"))
            continue

        invalid = sorted(v for v in values if v not in allowed)
        if invalid:
            issues.append(
                Issue(
                    "error",
                    f"values.{enum_key.lower()}",
                    f"Invalid values in {table}.{column}: {_summarize_values(invalid)}",
                )
            )
        else:
            issues.append(Issue("pass", f"values.{enum_key.lower()}", f"All non-null values in {table}.{column} are valid"))


def _is_valid_license(value: str, allowed: set[str]) -> bool:
    if value in allowed:
        return True
    upper_value = value.upper()
    for base in allowed:
        if not base.startswith("CC "):
            continue
        pattern = re.compile(rf"^{re.escape(base.upper())}(\s+\d+(?:\.\d+)*)?$")
        if pattern.match(upper_value):
            return True
    return False


def validate_submission(
    path: Path,
    spec: ValidationSpec,
    strict: bool,
    config: ValidationConfig = DEFAULT_CONFIG,
) -> ValidationReport:
    issues: list[Issue] = []
    _validate_filename(path, strict, issues, config)

    try:
        with closing(connect_readonly(path)) as conn:
            _validate_schema(conn, spec, strict, issues)
            _validate_enum_values(conn, spec, strict, issues, config)
    except sqlite3.DatabaseError as exc:
        issues.append(Issue("error", "sqlite.open", f"Could not open SQLite database: {exc}"))

    return ValidationReport(issues=issues)
