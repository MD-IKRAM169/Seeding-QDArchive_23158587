from pathlib import Path
import shutil
import sqlite3


# Project root directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Part 1 database
SOURCE_DB = PROJECT_ROOT / "23158587-seeding.db"

# Part 2 classification database
CLASSIFICATION_DB = PROJECT_ROOT / "23158587-sq26-classification.db"


def verify_database(db_path: Path) -> None:
    """
    Verify that the expected Part 1 tables exist in the database.
    """

    expected_tables = {
        "projects",
        "files",
        "keywords",
        "person_role",
        "licenses",
    }

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            """
        )

        actual_tables = {
            row[0]
            for row in cursor.fetchall()
            if not row[0].startswith("sqlite_")
        }

    missing_tables = expected_tables - actual_tables

    if missing_tables:
        raise RuntimeError(
            "Database verification failed. Missing tables: "
            + ", ".join(sorted(missing_tables))
        )

    print("Database verification successful.")
    print("Found expected tables:")

    for table in sorted(expected_tables):
        print(f"  - {table}")


def create_classification_database() -> None:
    """
    Create the Part 2 classification database.
    """

    print("=" * 60)
    print("SEEDING QDARCHIVE - PREPARE CLASSIFICATION DATABASE")
    print("=" * 60)

    # Check whether the source database exists.
    if not SOURCE_DB.exists():
        raise FileNotFoundError(
            f"Part 1 database not found:\n{SOURCE_DB}"
        )

    print(f"\nSource database:\n{SOURCE_DB}")

    # Verify the source database.
    print("\nVerifying source database...")
    verify_database(SOURCE_DB)

    # Prevent accidental overwrite.
    if CLASSIFICATION_DB.exists():
        print(
            "\nClassification database already exists:\n"
            f"{CLASSIFICATION_DB}"
        )
        print("\nNo file was overwritten.")
        print(
            "Delete or rename the existing classification database "
            "only if you intentionally want to recreate it."
        )
        return

    # Create the classification database.
    shutil.copy2(SOURCE_DB, CLASSIFICATION_DB)

    print("\nClassification database created:")
    print(CLASSIFICATION_DB)

    # Verify the newly created database.
    print("\nVerifying classification database...")
    verify_database(CLASSIFICATION_DB)

    print("\n" + "=" * 60)
    print("SUCCESS")
    print("Part 2 classification database created successfully.")
    print("Database is ready for the next classification step.")
    print("=" * 60)


def main() -> None:
    """
    Main entry point.
    """

    try:
        create_classification_database()

    except (
        FileNotFoundError,
        RuntimeError,
        sqlite3.Error,
        OSError,
    ) as error:

        print("\nERROR:")
        print(error)

        raise SystemExit(1) from error


if __name__ == "__main__":
    main()