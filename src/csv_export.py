import csv
import sqlite3
from pathlib import Path

from src.config import DB_PATH


EXPORT_DIR = Path("exports")
EXPORT_DIR.mkdir(exist_ok=True)


def export_table(table_name: str, output_file: Path) -> None:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute(f"SELECT * FROM {table_name}")
    rows = cur.fetchall()
    headers = [desc[0] for desc in cur.description]

    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)

    conn.close()
    print(f"Exported {table_name} -> {output_file}")


def main():
    export_table("projects", EXPORT_DIR / "projects.csv")
    export_table("files", EXPORT_DIR / "files.csv")
    export_table("keywords", EXPORT_DIR / "keywords.csv")
    export_table("person_role", EXPORT_DIR / "person_role.csv")
    export_table("licenses", EXPORT_DIR / "licenses.csv")


if __name__ == "__main__":
    main()