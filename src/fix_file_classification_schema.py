from pathlib import Path
import sqlite3


PROJECT_ROOT = Path(__file__).resolve().parent.parent

CLASSIFICATION_DB = (
    PROJECT_ROOT / "23158587-sq26-classification.db"
)


def table_exists(
    conn: sqlite3.Connection,
    table_name: str,
) -> bool:
    """
    Check whether a table exists.
    """

    row = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name = ?
        """,
        (table_name,),
    ).fetchone()

    return row is not None


def show_schema(
    conn: sqlite3.Connection,
    table_name: str,
) -> None:
    """
    Show table schema.
    """

    print(f"\nSchema for {table_name}:")

    rows = conn.execute(
        f"PRAGMA table_info({table_name})"
    ).fetchall()

    for row in rows:
        column_name = row[1]
        column_type = row[2]
        not_null = row[3]

        print(
            f"  {column_name:<20}"
            f" type={column_type:<12}"
            f" not_null={not_null}"
        )


def recreate_file_classifications_table(
    conn: sqlite3.Connection,
) -> None:
    """
    Recreate file_classifications with nullable score fields.
    """

    print(
        "\nRecreating file_classifications "
        "with nullable score fields..."
    )

    conn.execute(
        """
        DROP TABLE IF EXISTS file_classifications
        """
    )

    conn.execute(
        """
        CREATE TABLE file_classifications (
            file_id INTEGER PRIMARY KEY,
            project_id INTEGER NOT NULL,
            repository_id INTEGER,
            project_type PROJECT_TYPE,

            primary_class TEXT NOT NULL,
            primary_title TEXT NOT NULL,
            primary_score REAL,

            secondary_class TEXT,
            secondary_title TEXT,
            secondary_score REAL,

            score_margin REAL,

            confidence TEXT NOT NULL,
            evidence_mode TEXT NOT NULL,

            input_characters INTEGER NOT NULL DEFAULT 0,
            file_status TEXT,

            method TEXT NOT NULL,
            classified_at TEXT NOT NULL,

            FOREIGN KEY (file_id)
                REFERENCES files(id),

            FOREIGN KEY (project_id)
                REFERENCES projects(id)
        )
        """
    )


def verify_schema(
    conn: sqlite3.Connection,
) -> None:
    """
    Verify that primary_score and score_margin allow NULL.
    """

    rows = conn.execute(
        """
        PRAGMA table_info(file_classifications)
        """
    ).fetchall()

    schema = {
        row[1]: {
            "type": row[2],
            "not_null": row[3],
        }
        for row in rows
    }

    required_nullable_columns = {
        "primary_score",
        "secondary_score",
        "score_margin",
    }

    for column_name in required_nullable_columns:

        if column_name not in schema:
            raise RuntimeError(
                f"Missing column: {column_name}"
            )

        if schema[column_name]["not_null"] != 0:
            raise RuntimeError(
                f"Column is still NOT NULL: "
                f"{column_name}"
            )

    print(
        "\nVerification successful."
    )

    print(
        "Fallback score fields now allow NULL."
    )


def main() -> None:
    """
    Main entry point.
    """

    print("=" * 72)
    print(
        "SEEDING QDARCHIVE - "
        "FIX FILE CLASSIFICATION SCHEMA"
    )
    print("=" * 72)

    if not CLASSIFICATION_DB.exists():

        print("\nERROR:")
        print(
            "Classification database not found:"
        )
        print(CLASSIFICATION_DB)

        raise SystemExit(1)

    print("\nClassification database:")
    print(CLASSIFICATION_DB)

    try:

        with sqlite3.connect(
            CLASSIFICATION_DB
        ) as conn:

            if table_exists(
                conn,
                "file_classifications",
            ):
                print(
                    "\nExisting table found."
                )

                show_schema(
                    conn,
                    "file_classifications",
                )

            recreate_file_classifications_table(
                conn
            )

            conn.commit()

            verify_schema(conn)

            show_schema(
                conn,
                "file_classifications",
            )

    except (
        sqlite3.Error,
        RuntimeError,
        OSError,
    ) as error:

        print("\nERROR:")
        print(error)

        raise SystemExit(1) from error

    print("\n" + "=" * 72)
    print("SUCCESS")
    print(
        "file_classifications schema corrected."
    )
    print("=" * 72)


if __name__ == "__main__":
    main()