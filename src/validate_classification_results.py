from pathlib import Path
import sqlite3


# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

CLASSIFICATION_DB = (
    PROJECT_ROOT / "23158587-sq26-classification.db"
)


# ============================================================
# EXPECTED VALUES
# ============================================================

VALID_PROJECT_TYPES = {
    "QDA_PROJECT",
    "QD_PROJECT",
    "OTHER_PROJECT",
    "NOT_A_PROJECT",
}

EXPECTED_TOTAL_PROJECTS = 62


# ============================================================
# HELPERS
# ============================================================

def scalar(
    conn: sqlite3.Connection,
    sql: str,
    parameters: tuple = (),
):
    """
    Return the first column of the first row.
    """

    row = conn.execute(
        sql,
        parameters,
    ).fetchone()

    if row is None:
        return None

    return row[0]


def print_header(
    title: str,
) -> None:
    """
    Print a clear section header.
    """

    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


# ============================================================
# SCHEMA VALIDATION
# ============================================================

def validate_required_tables(
    conn: sqlite3.Connection,
) -> None:
    """
    Verify all expected Part 1 and Part 2 tables exist.
    """

    required_tables = {
        "projects",
        "files",
        "keywords",
        "person_role",
        "licenses",
        "isic_divisions",
        "classification_inputs",
        "project_classifications",
        "file_classifications",
    }

    actual_tables = {
        row[0]
        for row in conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            """
        ).fetchall()
        if not row[0].startswith("sqlite_")
    }

    missing = (
        required_tables - actual_tables
    )

    if missing:
        raise RuntimeError(
            "Missing required tables: "
            + ", ".join(
                sorted(missing)
            )
        )

    print(
        "Required tables: OK"
    )


def validate_required_columns(
    conn: sqlite3.Connection,
) -> None:
    """
    Verify required Part 2 columns exist.
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

    for table_name, required in (
        required_columns.items()
    ):

        actual = {
            row[1]
            for row in conn.execute(
                f"PRAGMA table_info({table_name})"
            ).fetchall()
        }

        missing = required - actual

        if missing:
            raise RuntimeError(
                f"Missing columns in "
                f"{table_name}: "
                + ", ".join(
                    sorted(missing)
                )
            )

    print(
        "Required Part 2 columns: OK"
    )


# ============================================================
# DATA VALIDATION
# ============================================================

def validate_project_count(
    conn: sqlite3.Connection,
) -> None:
    """
    Verify the expected number of projects.
    """

    total_projects = scalar(
        conn,
        """
        SELECT COUNT(*)
        FROM projects
        """
    )

    print(
        f"Total projects: {total_projects}"
    )

    if total_projects != EXPECTED_TOTAL_PROJECTS:
        raise RuntimeError(
            f"Expected "
            f"{EXPECTED_TOTAL_PROJECTS} projects, "
            f"but found {total_projects}."
        )


def validate_project_types(
    conn: sqlite3.Connection,
) -> None:
    """
    Verify every project has a valid PROJECT_TYPE.
    """

    rows = conn.execute(
        """
        SELECT id, type
        FROM projects
        ORDER BY id
        """
    ).fetchall()

    invalid = [
        (
            project_id,
            project_type,
        )
        for (
            project_id,
            project_type,
        ) in rows
        if (
            project_type
            not in VALID_PROJECT_TYPES
        )
    ]

    if invalid:
        raise RuntimeError(
            "Invalid or missing PROJECT_TYPE "
            f"values: {invalid}"
        )

    print(
        "All projects have valid PROJECT_TYPE: OK"
    )


def validate_project_classes(
    conn: sqlite3.Connection,
) -> None:
    """
    Verify every QDA_PROJECT and QD_PROJECT
    has a project class.
    """

    relevant_count = scalar(
        conn,
        """
        SELECT COUNT(*)
        FROM projects
        WHERE type IN (
            'QDA_PROJECT',
            'QD_PROJECT'
        )
        """
    )

    missing_count = scalar(
        conn,
        """
        SELECT COUNT(*)
        FROM projects
        WHERE type IN (
            'QDA_PROJECT',
            'QD_PROJECT'
        )
        AND (
            class IS NULL
            OR TRIM(class) = ''
        )
        """
    )

    print(
        f"Relevant projects: "
        f"{relevant_count}"
    )

    print(
        "Relevant projects without class: "
        f"{missing_count}"
    )

    if missing_count != 0:
        raise RuntimeError(
            f"{missing_count} relevant projects "
            "have no class."
        )


def validate_project_classification_rows(
    conn: sqlite3.Connection,
) -> None:
    """
    Verify detailed project classification row count.
    """

    relevant_count = scalar(
        conn,
        """
        SELECT COUNT(*)
        FROM projects
        WHERE type IN (
            'QDA_PROJECT',
            'QD_PROJECT'
        )
        """
    )

    classification_count = scalar(
        conn,
        """
        SELECT COUNT(*)
        FROM project_classifications
        """
    )

    print(
        "Detailed project classification rows: "
        f"{classification_count}"
    )

    if classification_count != relevant_count:
        raise RuntimeError(
            "Project classification row count "
            "does not match relevant projects."
        )


def validate_file_classifications(
    conn: sqlite3.Connection,
) -> None:
    """
    Verify all detailed classified files
    have files.class populated.
    """

    classified_files = scalar(
        conn,
        """
        SELECT COUNT(*)
        FROM file_classifications
        """
    )

    missing_file_class = scalar(
        conn,
        """
        SELECT COUNT(*)

        FROM file_classifications AS fc

        JOIN files AS f
            ON f.id = fc.file_id

        WHERE
            f.class IS NULL
            OR TRIM(f.class) = ''
        """
    )

    print(
        f"Classified primary files: "
        f"{classified_files}"
    )

    print(
        "Classified primary files "
        "without files.class: "
        f"{missing_file_class}"
    )

    if missing_file_class != 0:
        raise RuntimeError(
            f"{missing_file_class} classified files "
            "have no files.class value."
        )


def validate_isic_codes(
    conn: sqlite3.Connection,
) -> None:
    """
    Verify all project and file primary classes
    exist in isic_divisions.
    """

    invalid_project_codes = (
        conn.execute(
            """
            SELECT DISTINCT
                pc.primary_class

            FROM project_classifications AS pc

            LEFT JOIN isic_divisions AS idv
                ON idv.code = pc.primary_class

            WHERE idv.code IS NULL
            """
        ).fetchall()
    )

    invalid_file_codes = (
        conn.execute(
            """
            SELECT DISTINCT
                fc.primary_class

            FROM file_classifications AS fc

            LEFT JOIN isic_divisions AS idv
                ON idv.code = fc.primary_class

            WHERE idv.code IS NULL
            """
        ).fetchall()
    )

    if invalid_project_codes:
        raise RuntimeError(
            "Invalid project ISIC codes: "
            f"{invalid_project_codes}"
        )

    if invalid_file_codes:
        raise RuntimeError(
            "Invalid file ISIC codes: "
            f"{invalid_file_codes}"
        )

    print(
        "All project and file ISIC codes "
        "exist in taxonomy: OK"
    )


# ============================================================
# PROJECT TYPE STATISTICS
# ============================================================

def show_project_type_statistics(
    conn: sqlite3.Connection,
) -> None:
    """
    Show project-type counts by repository.
    """

    print_header(
        "PROJECT TYPE STATISTICS BY REPOSITORY"
    )

    rows = conn.execute(
        """
        SELECT
            repository_id,
            type,
            COUNT(*) AS project_count

        FROM projects

        GROUP BY
            repository_id,
            type

        ORDER BY
            repository_id,
            CASE type
                WHEN 'QDA_PROJECT' THEN 1
                WHEN 'QD_PROJECT' THEN 2
                WHEN 'OTHER_PROJECT' THEN 3
                WHEN 'NOT_A_PROJECT' THEN 4
                ELSE 5
            END
        """
    ).fetchall()

    current_repository = None

    for (
        repository_id,
        project_type,
        project_count,
    ) in rows:

        if (
            repository_id
            != current_repository
        ):
            print(
                f"\nRepository {repository_id}"
            )

            current_repository = (
                repository_id
            )

        print(
            f"  {project_type:<15}"
            f": {project_count}"
        )


# ============================================================
# DOMINANT PROJECT CLASSES
# ============================================================

def show_dominant_project_classes(
    conn: sqlite3.Connection,
) -> None:
    """
    Show dominant class by repository and project type.
    """

    print_header(
        "DOMINANT PROJECT CLASSES"
    )

    combinations = conn.execute(
        """
        SELECT DISTINCT
            p.repository_id,
            p.type

        FROM projects AS p

        WHERE p.type IN (
            'QDA_PROJECT',
            'QD_PROJECT'
        )

        ORDER BY
            p.repository_id,
            p.type
        """
    ).fetchall()

    for (
        repository_id,
        project_type,
    ) in combinations:

        row = conn.execute(
            """
            SELECT
                pc.primary_class,
                pc.primary_title,
                COUNT(*) AS class_count

            FROM project_classifications AS pc

            JOIN projects AS p
                ON p.id = pc.project_id

            WHERE
                p.repository_id = ?
                AND p.type = ?

            GROUP BY
                pc.primary_class,
                pc.primary_title

            ORDER BY
                class_count DESC,
                pc.primary_class

            LIMIT 1
            """,
            (
                repository_id,
                project_type,
            ),
        ).fetchone()

        if row is None:
            continue

        (
            primary_class,
            primary_title,
            class_count,
        ) = row

        print(
            f"\nRepository {repository_id}"
            f" | {project_type}"
        )

        print(
            f"  Dominant class: "
            f"{primary_class} - "
            f"{primary_title}"
        )

        print(
            f"  Count: {class_count}"
        )


# ============================================================
# TOP PROJECT CLASSES
# ============================================================

def show_top_project_classes(
    conn: sqlite3.Connection,
) -> None:
    """
    Show top project classes by repository.
    """

    print_header(
        "TOP PROJECT CLASSES BY REPOSITORY"
    )

    repositories = conn.execute(
        """
        SELECT DISTINCT repository_id
        FROM projects
        ORDER BY repository_id
        """
    ).fetchall()

    for (
        repository_id,
    ) in repositories:

        print(
            f"\nRepository {repository_id}"
        )

        rows = conn.execute(
            """
            SELECT
                pc.primary_class,
                pc.primary_title,
                COUNT(*) AS class_count

            FROM project_classifications AS pc

            JOIN projects AS p
                ON p.id = pc.project_id

            WHERE p.repository_id = ?

            GROUP BY
                pc.primary_class,
                pc.primary_title

            ORDER BY
                class_count DESC,
                pc.primary_class

            LIMIT 20
            """,
            (
                repository_id,
            ),
        ).fetchall()

        if not rows:
            print(
                "  No classified projects."
            )
            continue

        for (
            code,
            title,
            count,
        ) in rows:

            print(
                f"  {code:<4}"
                f" | {count:>3}"
                f" | {title}"
            )


# ============================================================
# CONFIDENCE STATISTICS
# ============================================================

def show_confidence_statistics(
    conn: sqlite3.Connection,
) -> None:
    """
    Show project and file confidence distributions.
    """

    print_header(
        "CONFIDENCE STATISTICS"
    )

    print(
        "\nProject classifications:"
    )

    project_rows = conn.execute(
        """
        SELECT
            confidence,
            COUNT(*)

        FROM project_classifications

        GROUP BY confidence

        ORDER BY
            CASE confidence
                WHEN 'HIGH' THEN 1
                WHEN 'MEDIUM' THEN 2
                WHEN 'LOW' THEN 3
                ELSE 4
            END
        """
    ).fetchall()

    for confidence, count in project_rows:
        print(
            f"  {confidence:<10}: {count}"
        )

    print(
        "\nFile classifications:"
    )

    file_rows = conn.execute(
        """
        SELECT
            confidence,
            COUNT(*)

        FROM file_classifications

        GROUP BY confidence

        ORDER BY
            CASE confidence
                WHEN 'HIGH' THEN 1
                WHEN 'MEDIUM' THEN 2
                WHEN 'LOW' THEN 3
                WHEN 'INHERITED' THEN 4
                ELSE 5
            END
        """
    ).fetchall()

    for confidence, count in file_rows:
        print(
            f"  {confidence:<10}: {count}"
        )


# ============================================================
# EVIDENCE STATISTICS
# ============================================================

def show_file_evidence_statistics(
    conn: sqlite3.Connection,
) -> None:
    """
    Show file-classification evidence modes.
    """

    print_header(
        "FILE CLASSIFICATION EVIDENCE"
    )

    rows = conn.execute(
        """
        SELECT
            evidence_mode,
            COUNT(*)

        FROM file_classifications

        GROUP BY evidence_mode

        ORDER BY COUNT(*) DESC
        """
    ).fetchall()

    for evidence_mode, count in rows:
        print(
            f"  {evidence_mode:<40}"
            f": {count}"
        )


# ============================================================
# FINAL SUMMARY
# ============================================================

def show_final_summary(
    conn: sqlite3.Connection,
) -> None:
    """
    Show final high-level result counts.
    """

    print_header(
        "FINAL VALIDATION SUMMARY"
    )

    total_projects = scalar(
        conn,
        """
        SELECT COUNT(*)
        FROM projects
        """
    )

    relevant_projects = scalar(
        conn,
        """
        SELECT COUNT(*)
        FROM projects
        WHERE type IN (
            'QDA_PROJECT',
            'QD_PROJECT'
        )
        """
    )

    project_classifications = scalar(
        conn,
        """
        SELECT COUNT(*)
        FROM project_classifications
        """
    )

    file_classifications = scalar(
        conn,
        """
        SELECT COUNT(*)
        FROM file_classifications
        """
    )

    isic_divisions = scalar(
        conn,
        """
        SELECT COUNT(*)
        FROM isic_divisions
        """
    )

    print(
        f"Total projects              : "
        f"{total_projects}"
    )

    print(
        f"Relevant classified projects: "
        f"{relevant_projects}"
    )

    print(
        f"Project classification rows : "
        f"{project_classifications}"
    )

    print(
        f"Primary file classifications: "
        f"{file_classifications}"
    )

    print(
        f"ISIC Rev. 5 divisions       : "
        f"{isic_divisions}"
    )


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    """
    Main entry point.
    """

    print("=" * 78)

    print(
        "SEEDING QDARCHIVE - "
        "VALIDATE CLASSIFICATION RESULTS"
    )

    print("=" * 78)

    if not CLASSIFICATION_DB.exists():

        print("\nERROR:")

        print(
            "Classification database not found:"
        )

        print(CLASSIFICATION_DB)

        raise SystemExit(1)

    print(
        "\nClassification database:"
    )

    print(CLASSIFICATION_DB)

    try:

        with sqlite3.connect(
            CLASSIFICATION_DB
        ) as conn:

            print_header(
                "STRUCTURE AND DATA VALIDATION"
            )

            validate_required_tables(conn)

            validate_required_columns(conn)

            validate_project_count(conn)

            validate_project_types(conn)

            validate_project_classes(conn)

            validate_project_classification_rows(
                conn
            )

            validate_file_classifications(
                conn
            )

            validate_isic_codes(conn)

            show_project_type_statistics(
                conn
            )

            show_dominant_project_classes(
                conn
            )

            show_top_project_classes(
                conn
            )

            show_confidence_statistics(
                conn
            )

            show_file_evidence_statistics(
                conn
            )

            show_final_summary(
                conn
            )

    except (
        sqlite3.Error,
        RuntimeError,
        OSError,
    ) as error:

        print("\nERROR:")

        print(error)

        raise SystemExit(1) from error

    print("\n" + "=" * 78)

    print("SUCCESS")

    print(
        "Classification database validation "
        "completed successfully."
    )

    print("=" * 78)


if __name__ == "__main__":
    main()