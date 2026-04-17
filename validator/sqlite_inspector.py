from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass
class TableInfo:
    name: str
    columns: dict[str, str]


def connect_readonly(db_path: Path) -> sqlite3.Connection:
    uri = f"file:{db_path.as_posix()}?mode=ro"
    return sqlite3.connect(uri, uri=True)


def quote_identifier(name: str) -> str:
    if not name or "\x00" in name:
        raise ValueError("Invalid SQL identifier")
    return '"' + name.replace('"', '""') + '"'


def list_tables(conn: sqlite3.Connection) -> set[str]:
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    return {row[0].upper() for row in cursor.fetchall()}


def get_table_info(conn: sqlite3.Connection, table_name: str) -> TableInfo:
    rows = conn.execute(f"PRAGMA table_info({quote_identifier(table_name)})").fetchall()
    columns: dict[str, str] = {}
    for row in rows:
        col_name = str(row[1])
        col_type = str(row[2] or "").upper().strip() or "TEXT"
        columns[col_name.lower()] = col_type
    return TableInfo(name=table_name, columns=columns)


def query_column_values(conn: sqlite3.Connection, table: str, column: str) -> set[str]:
    quoted_table = quote_identifier(table)
    quoted_column = quote_identifier(column)
    sql = f"SELECT DISTINCT {quoted_column} FROM {quoted_table} WHERE {quoted_column} IS NOT NULL"
    rows = conn.execute(sql).fetchall()
    return {str(row[0]).strip() for row in rows if str(row[0]).strip()}
