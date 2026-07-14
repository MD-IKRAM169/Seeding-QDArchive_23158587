from pathlib import Path
import sqlite3


PROJECT_ROOT = Path(__file__).resolve().parent.parent

CLASSIFICATION_DB = (
    PROJECT_ROOT / "23158587-sq26-classification.db"
)


def column_exists(
    conn: sqlite3.Connection,
    table_name: str,
    column_name: str,
) -> bool:
    """
    Check whether a column already exists in a table.
    """

    cursor = conn.execute(
        f"PRAGMA table_info({table_name})"
    )

    columns = {
        row[1]
        for row in cursor.fetchall()
    }

    return column_name in columns


def add_column_if_missing(
    conn: sqlite3.Connection,
    table_name: str,
    column_name: str,
    column_type: str,
) -> None:
    """
    Add a column only if it does not already exist.
    """

    if column_exists(
        conn,
        table_name,
        column_name,
    ):
        print(
            f"Column already exists: "
            f"{table_name}.{column_name}"
        )
        return

    sql = (
        f"ALTER TABLE {table_name} "
        f"ADD COLUMN {column_name} {column_type}"
    )

    conn.execute(sql)

    print(
        f"Added column: "
        f"{table_name}.{column_name}"
    )


def verify_columns(
    conn: sqlite3.Connection,
) -> None:
    """
    Verify that all required Part 2 columns exist.
    """

    required_columns = {
        "projects": {
            "type",
            "class",
        },
        "files": {
            "class",
        },
    }

    print("\nVerifying required columns...")

    for table_name, columns in required_columns.items():

        cursor = conn.execute(
            f"PRAGMA table_info({table_name})"
        )

        actual_columns = {
            row[1]
            for row in cursor.fetchall()
        }

        missing_columns = (
            columns - actual_columns
        )

        if missing_columns:
            raise RuntimeError(
                f"Missing columns in {table_name}: "
                + ", ".join(
                    sorted(missing_columns)
                )
            )

        print(
            f"{table_name}: verification successful"
        )


def show_schema(
    conn: sqlite3.Connection,
    table_name: str,
) -> None:
    """
    Print table columns for easy verification.
    """

    print(f"\nSchema for table: {table_name}")

    cursor = conn.execute(
        f"PRAGMA table_info({table_name})"
    )

    for row in cursor.fetchall():
        column_id = row[0]
        column_name = row[1]
        column_type = row[2]

        print(
            f"  {column_id}: "
            f"{column_name} "
            f"({column_type or 'NO TYPE'})"
        )


def main() -> None:
    """
    Main entry point.
    """

    print("=" * 60)
    print(
        "SEEDING QDARCHIVE - "
        "ADD CLASSIFICATION COLUMNS"
    )
    print("=" * 60)

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

            add_column_if_missing(
                conn,
                "projects",
                "type",
                "PROJECT_TYPE",
            )

            add_column_if_missing(
                conn,
                "projects",
                "class",
                "TEXT",
            )

            add_column_if_missing(
                conn,
                "files",
                "class",
                "TEXT",
            )

            conn.commit()

            verify_columns(conn)

            show_schema(
                conn,
                "projects",
            )

            show_schema(
                conn,
                "files",
            )

    except sqlite3.Error as error:
        print("\nDATABASE ERROR:")
        print(error)

        raise SystemExit(1) from error

    except RuntimeError as error:
        print("\nVERIFICATION ERROR:")
        print(error)

        raise SystemExit(1) from error

    print("\n" + "=" * 60)
    print("SUCCESS")
    print(
        "Required Part 2 classification "
        "columns are ready."
    )
    print("=" * 60)


if __name__ == "__main__":
    main()