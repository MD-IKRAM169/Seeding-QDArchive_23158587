from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ColumnSpec:
    name: str
    required: bool
    declared_type: str


@dataclass
class TableSpec:
    name: str
    columns: dict[str, ColumnSpec] = field(default_factory=dict)


@dataclass
class ValidationSpec:
    tables: dict[str, TableSpec]
    enums: dict[str, set[str]]


def _normalize_type(raw_type: str) -> str:
    text = (raw_type or "").strip().upper()
    mapping = {
        "STRING": "TEXT",
        "URL": "TEXT",
        "BCP 47": "TEXT",
        "DATE": "TEXT",
        "TIMESTAMP": "TEXT",
        "SCRAPING | API-CALL": "TEXT",
        "DOWNLOAD_RESULT": "TEXT",
        "PERSON_ROLE": "TEXT",
        "LICENSE": "TEXT",
        "INTEGER": "INTEGER",
        "TEXT": "TEXT",
    }
    return mapping.get(text, text or "TEXT")


TABLE_HEADER_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s+TABLE$", re.IGNORECASE)
COLUMN_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _parse_required_marker(value: str) -> bool | None:
    marker = (value or "").strip().lower()
    if marker in {"r", "required"}:
        return True
    if marker in {"o", "optional", ""}:
        return False if marker else None
    return None


def _looks_like_header_row(first: str, row: list[str]) -> bool:
    if first.strip().lower() == "field name":
        return True
    second = (row[1] if len(row) > 1 else "").strip().lower()
    third = (row[2] if len(row) > 2 else "").strip().lower()
    return second == "type" and "required" in third


def load_schema_csv(path: Path) -> dict[str, TableSpec]:
    tables: dict[str, TableSpec] = {}
    current_table: TableSpec | None = None

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        for row in reader:
            if not row:
                continue
            first = (row[0] or "").strip()
            if not first:
                continue

            match = TABLE_HEADER_RE.match(first)
            if match:
                table_name = match.group(1).upper()
                current_table = TableSpec(name=table_name)
                tables[table_name] = current_table
                continue

            if current_table is None:
                continue

            if _looks_like_header_row(first, row):
                continue

            name = first
            if not COLUMN_NAME_RE.match(name):
                continue

            marker = _parse_required_marker(row[2] if len(row) > 2 else "")
            if marker is None:
                continue

            raw_type = (row[1] if len(row) > 1 else "").strip()
            current_table.columns[name.lower()] = ColumnSpec(
                name=name,
                required=marker,
                declared_type=_normalize_type(raw_type),
            )

    return tables


def load_enums_tsv(path: Path) -> dict[str, set[str]]:
    enums: dict[str, set[str]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        for row in reader:
            if not row:
                continue
            key = (row[0] if len(row) > 0 else "").strip().upper()
            kind = (row[1] if len(row) > 1 else "").strip().lower()
            values = [cell.strip() for cell in row[2:] if cell.strip()]
            if key and kind in {"enum", "string"} and values:
                enums[key] = set(values)
    return enums


def load_spec(schema_csv: Path, enum_tsv: Path) -> ValidationSpec:
    return ValidationSpec(tables=load_schema_csv(schema_csv), enums=load_enums_tsv(enum_tsv))
