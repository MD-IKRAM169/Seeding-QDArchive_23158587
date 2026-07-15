from pathlib import Path
import sqlite3


PROJECT_ROOT = Path(__file__).resolve().parent.parent

CLASSIFICATION_DB = (
    PROJECT_ROOT / "23158587-sq26-classification.db"
)

QDA_EXTENSIONS = {
    # REFI-QDA
    ".qdpx",
    ".qdc",

    # MAXQDA
    ".mqda",
    ".mqbac",
    ".mqtc",
    ".mqex",
    ".mqmtr",
    ".mx24",
    ".mx24bac",
    ".mc24",
    ".mex24",
    ".mx22",
    ".mx20",
    ".mx18",
    ".mx12",
    ".mx11",
    ".mx5",
    ".mx4",
    ".mx3",
    ".mx2",
    ".m2k",
    ".loa",
    ".sea",
    ".mtr",
    ".mod",
    ".mex22",

    # NVivo
    ".nvp",
    ".nvpx",

    # ATLAS.ti
    ".atlasproj",
    ".hpr7",

    # QDA Miner
    ".ppj",
    ".pprj",
    ".qlt",

    # f4analyse
    ".f4p",

    # Quirkos
    ".qpd",
}

PRIMARY_DATA_EXTENSIONS = {
    # Text and documents
    ".txt",
    ".rtf",
    ".pdf",
    ".doc",
    ".docx",
    ".odt",

    # Tabular data
    ".csv",
    ".tsv",
    ".tab",
    ".xls",
    ".xlsx",
    ".ods",

    # Images
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".bmp",
    ".tif",
    ".tiff",

    # Audio
    ".mp3",
    ".wav",
    ".m4a",
    ".aac",
    ".flac",
    ".ogg",

    # Video
    ".mp4",
    ".avi",
    ".mov",
    ".mkv",
    ".wmv",
    ".webm",
}

OTHER_VALID_EXTENSIONS = {
    ".xml",
    ".json",
    ".zip",
    ".7z",
    ".rar",
    ".html",
    ".htm",
    ".md",
    ".yaml",
    ".yml",
}

METADATA_ONLY_FILE_NAMES = {
    "export.xml",
    "export.json",
}


def normalize_extension(
    file_name: str | None,
    file_type: str | None,
) -> str:
    """
    Return a normalized lowercase file extension.

    Preference:
    1. file_type column
    2. extension derived from file_name
    """

    if file_type:
        value = str(file_type).strip().lower()

        if not value:
            return ""

        if not value.startswith("."):
            value = "." + value

        return value

    if not file_name:
        return ""

    suffix = Path(str(file_name).strip()).suffix.lower()

    return suffix


def is_metadata_only_file(
    file_name: str | None,
) -> bool:
    """
    Check whether a file is a known metadata-only export.
    """

    if not file_name:
        return False

    normalized_name = (
        Path(str(file_name).strip())
        .name
        .lower()
    )

    return normalized_name in METADATA_ONLY_FILE_NAMES


def classify_project(
    file_rows: list[tuple[str | None, str | None]],
) -> str:
    """
    Classify one project based on its file records.

    Priority:
    1. QDA_PROJECT
    2. QD_PROJECT
    3. OTHER_PROJECT
    4. NOT_A_PROJECT
    """

    has_qda_file = False
    has_primary_file = False
    has_other_valid_file = False

    for file_name, file_type in file_rows:

        extension = normalize_extension(
            file_name,
            file_type,
        )

        # Ignore records without usable file type information.
        if not extension:
            continue

        # Highest priority: known QDA extension.
        if extension in QDA_EXTENSIONS:
            has_qda_file = True
            continue

        # Known CESSDA metadata exports should not create
        # a QD_PROJECT classification.
        if is_metadata_only_file(file_name):

            if extension in OTHER_VALID_EXTENSIONS:
                has_other_valid_file = True

            continue

        # Primary qualitative data.
        if extension in PRIMARY_DATA_EXTENSIONS:
            has_primary_file = True
            continue

        # Other valid project files.
        if extension in OTHER_VALID_EXTENSIONS:
            has_other_valid_file = True

    if has_qda_file:
        return "QDA_PROJECT"

    if has_primary_file:
        return "QD_PROJECT"

    if has_other_valid_file:
        return "OTHER_PROJECT"

    return "NOT_A_PROJECT"


def verify_database(
    conn: sqlite3.Connection,
) -> None:
    """
    Verify that the required Part 2 column exists.
    """

    cursor = conn.execute(
        "PRAGMA table_info(projects)"
    )

    columns = {
        row[1]
        for row in cursor.fetchall()
    }

    if "type" not in columns:
        raise RuntimeError(
            "Missing required column: projects.type\n"
            "Run Step 2 first."
        )


def classify_all_projects(
    conn: sqlite3.Connection,
) -> None:
    """
    Classify every project and update projects.type.
    """

    project_rows = conn.execute(
        """
        SELECT
            id,
            repository_id,
            title
        FROM projects
        ORDER BY id
        """
    ).fetchall()

    print(
        f"\nProjects found: {len(project_rows)}"
    )

    for project_id, repository_id, title in project_rows:

        file_rows = conn.execute(
            """
            SELECT
                file_name,
                file_type
            FROM files
            WHERE project_id = ?
            """,
            (project_id,),
        ).fetchall()

        project_type = classify_project(
            file_rows
        )

        conn.execute(
            """
            UPDATE projects
            SET type = ?
            WHERE id = ?
            """,
            (
                project_type,
                project_id,
            ),
        )

        safe_title = (
            str(title)[:70]
            if title
            else "(no title)"
        )

        print(
            f"Project {project_id:>3} | "
            f"Repo {repository_id} | "
            f"{project_type:<15} | "
            f"{safe_title}"
        )


def verify_results(
    conn: sqlite3.Connection,
) -> None:
    """
    Verify that every project received a valid type.
    """

    valid_types = {
        "QDA_PROJECT",
        "QD_PROJECT",
        "OTHER_PROJECT",
        "NOT_A_PROJECT",
    }

    rows = conn.execute(
        """
        SELECT id, type
        FROM projects
        ORDER BY id
        """
    ).fetchall()

    invalid_rows = [
        (project_id, project_type)
        for project_id, project_type in rows
        if project_type not in valid_types
    ]

    if invalid_rows:
        raise RuntimeError(
            "Some projects have invalid or missing "
            f"project types: {invalid_rows}"
        )

    print(
        "\nVerification successful: "
        "every project has a valid PROJECT_TYPE."
    )


def show_summary(
    conn: sqlite3.Connection,
) -> None:
    """
    Show project-type counts by repository.
    """

    print("\n" + "=" * 72)
    print("PROJECT TYPE SUMMARY BY REPOSITORY")
    print("=" * 72)

    rows = conn.execute(
        """
        SELECT
            repository_id,
            type,
            COUNT(*) AS project_count
        FROM projects
        GROUP BY repository_id, type
        ORDER BY repository_id, type
        """
    ).fetchall()

    current_repository = None

    for repository_id, project_type, count in rows:

        if repository_id != current_repository:
            print(
                f"\nRepository ID: {repository_id}"
            )
            current_repository = repository_id

        print(
            f"  {project_type:<15} : {count}"
        )

    total_projects = conn.execute(
        """
        SELECT COUNT(*)
        FROM projects
        """
    ).fetchone()[0]

    classified_projects = conn.execute(
        """
        SELECT COUNT(*)
        FROM projects
        WHERE type IS NOT NULL
          AND TRIM(type) != ''
        """
    ).fetchone()[0]

    print("\n" + "-" * 72)
    print(
        f"Total projects     : {total_projects}"
    )
    print(
        f"Classified projects: {classified_projects}"
    )


def show_qda_projects(
    conn: sqlite3.Connection,
) -> None:
    """
    Display projects classified as QDA_PROJECT and the
    QDA file records responsible for that classification.
    """

    print("\n" + "=" * 72)
    print("QDA PROJECT EVIDENCE")
    print("=" * 72)

    qda_projects = conn.execute(
        """
        SELECT
            id,
            repository_id,
            title
        FROM projects
        WHERE type = 'QDA_PROJECT'
        ORDER BY id
        """
    ).fetchall()

    if not qda_projects:
        print("\nNo QDA_PROJECT records found.")
        return

    for project_id, repository_id, title in qda_projects:

        print(
            f"\nProject ID: {project_id}"
        )
        print(
            f"Repository ID: {repository_id}"
        )
        print(
            f"Title: {title}"
        )

        file_rows = conn.execute(
            """
            SELECT
                file_name,
                file_type,
                status
            FROM files
            WHERE project_id = ?
            ORDER BY id
            """,
            (project_id,),
        ).fetchall()

        found_qda_evidence = False

        for file_name, file_type, status in file_rows:

            extension = normalize_extension(
                file_name,
                file_type,
            )

            if extension in QDA_EXTENSIONS:
                found_qda_evidence = True

                print(
                    "  QDA file:"
                    f" {file_name}"
                    f" | extension={extension}"
                    f" | status={status}"
                )

        if not found_qda_evidence:
            print(
                "  WARNING: No QDA evidence found."
            )


def main() -> None:
    """
    Main entry point.
    """

    print("=" * 72)
    print(
        "SEEDING QDARCHIVE - "
        "CLASSIFY PROJECT TYPES"
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

            verify_database(conn)

            classify_all_projects(conn)

            conn.commit()

            verify_results(conn)

            show_summary(conn)

            show_qda_projects(conn)

    except sqlite3.Error as error:

        print("\nDATABASE ERROR:")
        print(error)

        raise SystemExit(1) from error

    except RuntimeError as error:

        print("\nVERIFICATION ERROR:")
        print(error)

        raise SystemExit(1) from error

    print("\n" + "=" * 72)
    print("SUCCESS")
    print(
        "Project-type classification completed."
    )
    print("=" * 72)


if __name__ == "__main__":
    main()
