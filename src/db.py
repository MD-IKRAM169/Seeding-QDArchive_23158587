import sqlite3
from datetime import datetime
from typing import Iterable, Optional

from src.config import DB_PATH


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def now_timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def init_db() -> None:
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS projects (
            id                        INTEGER PRIMARY KEY AUTOINCREMENT,
            query_string              TEXT,
            repository_id             INTEGER NOT NULL,
            repository_url            TEXT NOT NULL,
            project_url               TEXT NOT NULL,
            version                   TEXT,
            title                     TEXT NOT NULL,
            description               TEXT,
            language                  TEXT,
            doi                       TEXT,
            upload_date               TEXT,
            download_date             TIMESTAMP NOT NULL,
            download_repository_folder TEXT NOT NULL,
            download_project_folder   TEXT NOT NULL,
            download_version_folder   TEXT,
            download_method           TEXT NOT NULL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS files (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id  INTEGER NOT NULL,
            file_name   TEXT NOT NULL,
            file_type   TEXT NOT NULL,
            status      TEXT NOT NULL DEFAULT 'SUCCEEDED',
            FOREIGN KEY (project_id) REFERENCES projects(id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS keywords (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id  INTEGER NOT NULL,
            keyword     TEXT NOT NULL,
            FOREIGN KEY (project_id) REFERENCES projects(id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS person_role (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id  INTEGER NOT NULL,
            name        TEXT NOT NULL,
            role        TEXT NOT NULL,
            FOREIGN KEY (project_id) REFERENCES projects(id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS licenses (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id  INTEGER NOT NULL,
            license     TEXT NOT NULL,
            FOREIGN KEY (project_id) REFERENCES projects(id)
        )
        """
    )

    conn.commit()
    conn.close()


def insert_project(
    query_string: Optional[str],
    repository_id: int,
    repository_url: str,
    project_url: str,
    version: Optional[str],
    title: str,
    description: Optional[str],
    language: Optional[str],
    doi: Optional[str],
    upload_date: Optional[str],
    download_repository_folder: str,
    download_project_folder: str,
    download_version_folder: Optional[str],
    download_method: str,
) -> int:
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO projects (
            query_string,
            repository_id,
            repository_url,
            project_url,
            version,
            title,
            description,
            language,
            doi,
            upload_date,
            download_date,
            download_repository_folder,
            download_project_folder,
            download_version_folder,
            download_method
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            query_string,
            repository_id,
            repository_url,
            project_url,
            version,
            title,
            description,
            language,
            doi,
            upload_date,
            now_timestamp(),
            download_repository_folder,
            download_project_folder,
            download_version_folder,
            download_method,
        ),
    )

    project_id = cur.lastrowid
    conn.commit()
    conn.close()
    return int(project_id)


def get_project_id_by_url(project_url: str) -> Optional[int]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM projects WHERE project_url = ? LIMIT 1", (project_url,))
    row = cur.fetchone()
    conn.close()
    return int(row[0]) if row else None


def project_exists(project_url: str) -> bool:
    return get_project_id_by_url(project_url) is not None


def insert_file(project_id: int, file_name: str, file_type: str, status: str = "SUCCEEDED") -> int:
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO files (project_id, file_name, file_type, status)
        VALUES (?, ?, ?, ?)
        """,
        (project_id, file_name, file_type, status),
    )

    file_id = cur.lastrowid
    conn.commit()
    conn.close()
    return int(file_id)


def insert_keywords(project_id: int, keywords: Iterable[str]) -> None:
    conn = get_connection()
    cur = conn.cursor()

    clean_keywords = []
    seen = set()
    for keyword in keywords:
        if not keyword:
            continue
        k = keyword.strip()
        if not k:
            continue
        lower_k = k.lower()
        if lower_k in seen:
            continue
        seen.add(lower_k)
        clean_keywords.append((project_id, k))

    if clean_keywords:
        cur.executemany(
            """
            INSERT INTO keywords (project_id, keyword)
            VALUES (?, ?)
            """,
            clean_keywords,
        )

    conn.commit()
    conn.close()


def insert_person_roles(project_id: int, people: Iterable[tuple[str, str]]) -> None:
    conn = get_connection()
    cur = conn.cursor()

    clean_people = []
    seen = set()
    for name, role in people:
        if not name:
            continue
        clean_name = name.strip()
        clean_role = (role or "UNKNOWN").strip().upper()
        if not clean_name:
            continue
        key = (clean_name.lower(), clean_role)
        if key in seen:
            continue
        seen.add(key)
        clean_people.append((project_id, clean_name, clean_role))

    if clean_people:
        cur.executemany(
            """
            INSERT INTO person_role (project_id, name, role)
            VALUES (?, ?, ?)
            """,
            clean_people,
        )

    conn.commit()
    conn.close()


def insert_license(project_id: int, license_value: str) -> None:
    if not license_value:
        return

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO licenses (project_id, license)
        VALUES (?, ?)
        """,
        (project_id, license_value.strip()),
    )

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print(f"Database initialized at: {DB_PATH}")