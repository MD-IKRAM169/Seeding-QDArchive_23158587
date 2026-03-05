import sqlite3
from typing import Dict, Any
from src.config import DB_PATH

def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)

def init_db():
    """
    Output Format v1 (professor):
      - URL of QDA file (required)
      - last download timestamp (required)
      - local directory (required)
      - local filename (required)
    Plus optional helpful fields.
    :contentReference[oaicite:2]{index=2}
    """
    with connect() as con:
        con.execute("""
        CREATE TABLE IF NOT EXISTS qda_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            -- REQUIRED columns (v1)
            url TEXT NOT NULL,                 -- URL of QDA file
            timestamp TEXT NOT NULL,           -- last download timestamp
            local_dir TEXT NOT NULL,           -- name of local directory
            local_filename TEXT NOT NULL,      -- name of local downloaded QDA file

            -- OPTIONAL but recommended
            repository TEXT,
            dataset_url TEXT,
            dataset_id TEXT,
            title TEXT,
            description TEXT,
            license TEXT,
            doi TEXT,
            uploader_name TEXT,
            uploader_email TEXT,
            file_type TEXT,
            size_bytes INTEGER,
            sha256 TEXT,

            UNIQUE(url)
        );
        """)
        con.commit()

def insert_row(row: Dict[str, Any]):
    cols = ",".join(row.keys())
    placeholders = ",".join(["?"] * len(row))
    values = list(row.values())
    with connect() as con:
        con.execute(f"INSERT OR IGNORE INTO qda_files ({cols}) VALUES ({placeholders})", values)
        con.commit()