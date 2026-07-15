from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import html
import json
import logging
import re
import sqlite3
import xml.etree.ElementTree as ET
import zipfile

PROJECT_ROOT = Path(__file__).resolve().parent.parent

CLASSIFICATION_DB = (
    PROJECT_ROOT / "23158587-sq26-classification.db"
)

DOWNLOAD_ROOT = PROJECT_ROOT / "my_downloads"

MAX_CHARS_PER_FILE = 20_000

MAX_FILE_TEXT_PER_PROJECT = 100_000

MAX_FILE_NAMES_PER_PROJECT = 100

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

    # Structured data
    ".xml",
    ".json",

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


TEXT_EXTENSIONS = {
    ".txt",
    ".rtf",
    ".csv",
    ".tsv",
    ".tab",
    ".html",
    ".htm",
}

DOCX_EXTENSIONS = {
    ".docx",
}

PDF_EXTENSIONS = {
    ".pdf",
}

METADATA_ONLY_FILE_NAMES = {
    "export.xml",
    "export.json",
}


try:
    from pypdf import PdfReader

    PDF_SUPPORT_AVAILABLE = True

    # Suppress harmless warnings produced by imperfect PDFs.
    logging.getLogger("pypdf").setLevel(logging.ERROR)

except ImportError:
    PdfReader = None
    PDF_SUPPORT_AVAILABLE = False


def create_classification_inputs_table(
    conn: sqlite3.Connection,
) -> None:
    """
    Create the classification_inputs table if necessary.
    """

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS classification_inputs (
            project_id INTEGER PRIMARY KEY,
            repository_id INTEGER,
            project_type PROJECT_TYPE,
            metadata_text TEXT,
            file_names_text TEXT,
            file_content_text TEXT,
            combined_text TEXT,
            primary_file_count INTEGER NOT NULL DEFAULT 0,
            extracted_file_count INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (project_id) REFERENCES projects(id)
        )
        """
    )


def clean_text(
    value: str | None,
) -> str:
    """
    Normalize text and whitespace.
    """

    if value is None:
        return ""

    text = str(value)

    text = html.unescape(text)

    text = text.replace("\x00", " ")

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def truncate_text(
    text: str,
    max_chars: int,
) -> str:
    """
    Limit text length safely.
    """

    if len(text) <= max_chars:
        return text

    return text[:max_chars]


def normalize_extension(
    file_name: str | None,
    file_type: str | None,
) -> str:
    """
    Determine a lowercase file extension.

    Preference:
    1. file_type column
    2. extension from file_name
    """

    if file_type:
        value = str(file_type).strip().lower()

        if value:
            if not value.startswith("."):
                value = "." + value

            return value

    if not file_name:
        return ""

    return Path(
        str(file_name).strip()
    ).suffix.lower()


def is_metadata_only_file(
    file_name: str | None,
) -> bool:
    """
    Identify known metadata-only exports.
    """

    if not file_name:
        return False

    normalized_name = Path(
        str(file_name).strip()
    ).name.lower()

    return (
        normalized_name
        in METADATA_ONLY_FILE_NAMES
    )

def build_local_file_index() -> dict[str, list[Path]]:
    """
    Build an index of downloaded files using lowercase basename.
    """

    index: dict[str, list[Path]] = defaultdict(list)

    if not DOWNLOAD_ROOT.exists():
        return index

    for path in DOWNLOAD_ROOT.rglob("*"):

        if path.is_file():
            index[path.name.lower()].append(path)

    return index


def normalize_path_hint(
    value: str | None,
) -> str:
    """
    Normalize a database folder value for comparison.
    """

    if not value:
        return ""

    return (
        str(value)
        .replace("\\", "/")
        .strip("/")
        .lower()
    )


def build_project_folder_hints(
    download_repository_folder: str | None,
    download_project_folder: str | None,
    download_version_folder: str | None,
) -> list[str]:
    """
    Build useful folder hints for matching local files to
    the correct project.
    """

    hints = []

    for value in (
        download_repository_folder,
        download_project_folder,
        download_version_folder,
    ):
        normalized = normalize_path_hint(value)

        if normalized:
            hints.append(normalized)

            # Also preserve the final folder component.
            final_part = normalized.split("/")[-1]

            if final_part:
                hints.append(final_part)

    return list(dict.fromkeys(hints))


def find_local_file(
    file_name: str | None,
    file_index: dict[str, list[Path]],
    project_folder_hints: list[str],
) -> Path | None:
    
    if not file_name:
        return None

    normalized_name = Path(
        str(file_name).strip()
    ).name.lower()

    matches = file_index.get(
        normalized_name,
        [],
    )

    if not matches:
        return None

    if len(matches) == 1:
        return matches[0]

    matching_candidates = []

    for path in matches:

        normalized_path = (
            str(path)
            .replace("\\", "/")
            .lower()
        )

        if any(
            hint in normalized_path
            for hint in project_folder_hints
            if hint
        ):
            matching_candidates.append(path)

    if len(matching_candidates) == 1:
        return matching_candidates[0]

    # Do not guess when several files with identical names
    # remain ambiguous.
    return None

def read_text_file(
    file_path: Path,
) -> str:
    """
    Read ordinary text files safely.
    """

    encodings = (
        "utf-8",
        "utf-8-sig",
        "cp1252",
        "latin-1",
    )

    for encoding in encodings:

        try:
            text = file_path.read_text(
                encoding=encoding,
                errors="strict",
            )

            return truncate_text(
                clean_text(text),
                MAX_CHARS_PER_FILE,
            )

        except (
            UnicodeDecodeError,
            OSError,
        ):
            continue

    return ""


def read_json_file(
    file_path: Path,
) -> str:
    """
    Extract readable text from JSON.
    """

    try:
        with file_path.open(
            "r",
            encoding="utf-8",
            errors="replace",
        ) as handle:
            data = json.load(handle)

        text = json.dumps(
            data,
            ensure_ascii=False,
        )

        return truncate_text(
            clean_text(text),
            MAX_CHARS_PER_FILE,
        )

    except (
        json.JSONDecodeError,
        OSError,
    ):
        return read_text_file(file_path)


def read_xml_file(
    file_path: Path,
) -> str:
    """
    Extract visible values from XML.
    """

    try:
        tree = ET.parse(file_path)

        root = tree.getroot()

        parts = []

        for element in root.iter():

            if element.text:
                value = clean_text(element.text)

                if value:
                    parts.append(value)

        text = " ".join(parts)

        return truncate_text(
            clean_text(text),
            MAX_CHARS_PER_FILE,
        )

    except (
        ET.ParseError,
        OSError,
    ):
        return read_text_file(file_path)


def read_docx_file(
    file_path: Path,
) -> str:
    """
    Extract text from DOCX using the standard library.
    """

    try:
        with zipfile.ZipFile(
            file_path,
            "r",
        ) as archive:

            xml_data = archive.read(
                "word/document.xml"
            )

        root = ET.fromstring(xml_data)

        parts = []

        for element in root.iter():

            if element.text:
                value = clean_text(element.text)

                if value:
                    parts.append(value)

        text = " ".join(parts)

        return truncate_text(
            clean_text(text),
            MAX_CHARS_PER_FILE,
        )

    except (
        KeyError,
        OSError,
        zipfile.BadZipFile,
        ET.ParseError,
    ):
        return ""


def read_pdf_file(
    file_path: Path,
) -> str:
    """
    Extract readable text from PDF.

    Imperfect, encrypted, image-only, or malformed PDFs
    return an empty string without stopping the pipeline.
    """

    if not PDF_SUPPORT_AVAILABLE:
        return ""

    try:
        reader = PdfReader(
            str(file_path),
            strict=False,
        )

        parts = []

        current_length = 0

        for page in reader.pages:

            try:
                page_text = page.extract_text()

            except Exception:
                continue

            if not page_text:
                continue

            parts.append(page_text)

            current_length += len(page_text)

            if current_length >= MAX_CHARS_PER_FILE:
                break

        text = " ".join(parts)

        return truncate_text(
            clean_text(text),
            MAX_CHARS_PER_FILE,
        )

    except Exception:
        return ""


def extract_file_text(
    file_path: Path,
    extension: str,
) -> str:
    """
    Extract text according to file extension.
    """

    if extension == ".json":
        return read_json_file(file_path)

    if extension == ".xml":
        return read_xml_file(file_path)

    if extension in DOCX_EXTENSIONS:
        return read_docx_file(file_path)

    if extension in PDF_EXTENSIONS:
        return read_pdf_file(file_path)

    if extension in TEXT_EXTENSIONS:
        return read_text_file(file_path)

    # Images, audio, video, XLS/XLSX, old DOC files,
    # and unsupported binary formats are not extracted here.
    return ""

def get_project_keywords(
    conn: sqlite3.Connection,
    project_id: int,
) -> list[str]:
    """
    Return unique cleaned keywords.
    """

    rows = conn.execute(
        """
        SELECT keyword
        FROM keywords
        WHERE project_id = ?
        ORDER BY id
        """,
        (project_id,),
    ).fetchall()

    keywords = []

    for row in rows:

        keyword = clean_text(row[0])

        if keyword:
            keywords.append(keyword)

    return list(dict.fromkeys(keywords))


def build_metadata_text(
    title: str | None,
    description: str | None,
    language: str | None,
    keywords: list[str],
) -> str:
    """
    Build structured project metadata text.
    """

    sections = []

    clean_title = clean_text(title)

    if clean_title:
        sections.append(
            f"TITLE: {clean_title}"
        )

    clean_description = clean_text(description)

    if clean_description:
        sections.append(
            f"DESCRIPTION: {clean_description}"
        )

    clean_language = clean_text(language)

    if clean_language:
        sections.append(
            f"LANGUAGE: {clean_language}"
        )

    if keywords:
        sections.append(
            "KEYWORDS: "
            + "; ".join(keywords)
        )

    return "\n".join(sections)

def prepare_project_input(
    conn: sqlite3.Connection,
    project_id: int,
    repository_id: int,
    project_type: str,
    title: str | None,
    description: str | None,
    language: str | None,
    download_repository_folder: str | None,
    download_project_folder: str | None,
    download_version_folder: str | None,
    file_index: dict[str, list[Path]],
) -> dict[str, object]:
    """
    Prepare classification evidence for one project.
    """

    keywords = get_project_keywords(
        conn,
        project_id,
    )

    metadata_text = build_metadata_text(
        title,
        description,
        language,
        keywords,
    )

    project_folder_hints = build_project_folder_hints(
        download_repository_folder,
        download_project_folder,
        download_version_folder,
    )

    file_rows = conn.execute(
        """
        SELECT
            id,
            file_name,
            file_type,
            status
        FROM files
        WHERE project_id = ?
        ORDER BY id
        """,
        (project_id,),
    ).fetchall()

    all_primary_file_names = []

    extracted_parts = []

    primary_file_count = 0

    extracted_file_count = 0

    total_extracted_chars = 0

    for (
        file_id,
        file_name,
        file_type,
        status,
    ) in file_rows:

        extension = normalize_extension(
            file_name,
            file_type,
        )

        if not extension:
            continue

        # Exclude known CESSDA metadata exports.
        if is_metadata_only_file(file_name):
            continue

        if extension not in PRIMARY_DATA_EXTENSIONS:
            continue

        # Keep the real number of primary file records.
        primary_file_count += 1

        if file_name:
            cleaned_name = clean_text(file_name)

            if cleaned_name:
                all_primary_file_names.append(
                    cleaned_name
                )

        # Only successfully downloaded files can provide
        # local file content.
        if status != "SUCCEEDED":
            continue

        local_file = find_local_file(
            file_name=file_name,
            file_index=file_index,
            project_folder_hints=project_folder_hints,
        )

        if local_file is None:
            continue

        extracted_text = extract_file_text(
            local_file,
            extension,
        )

        if not extracted_text:
            continue

        remaining_chars = (
            MAX_FILE_TEXT_PER_PROJECT
            - total_extracted_chars
        )

        if remaining_chars <= 0:
            break

        extracted_text = truncate_text(
            extracted_text,
            remaining_chars,
        )

        extracted_parts.append(
            (
                f"FILE: {file_name}\n"
                f"CONTENT: {extracted_text}"
            )
        )

        extracted_file_count += 1

        total_extracted_chars += len(
            extracted_text
        )

    # Remove duplicates while preserving source order.
    unique_primary_file_names = list(
        dict.fromkeys(
            all_primary_file_names
        )
    )

    # Limit only what is presented to the classifier.
    # The real primary_file_count remains unchanged.
    selected_file_names = (
        unique_primary_file_names[
            :MAX_FILE_NAMES_PER_PROJECT
        ]
    )

    file_names_text = "\n".join(
        selected_file_names
    )

    file_content_text = "\n\n".join(
        extracted_parts
    )

    combined_sections = []

    if metadata_text:
        combined_sections.append(
            "=== PROJECT METADATA ===\n"
            + metadata_text
        )

    if file_names_text:
        combined_sections.append(
            "=== PRIMARY FILE NAMES ===\n"
            + file_names_text
        )

    if file_content_text:
        combined_sections.append(
            "=== EXTRACTED FILE CONTENT ===\n"
            + file_content_text
        )

    combined_text = "\n\n".join(
        combined_sections
    )

    return {
        "project_id": project_id,
        "repository_id": repository_id,
        "project_type": project_type,
        "metadata_text": metadata_text,
        "file_names_text": file_names_text,
        "file_content_text": file_content_text,
        "combined_text": combined_text,
        "primary_file_count": primary_file_count,
        "extracted_file_count": extracted_file_count,
        "unique_file_name_count": len(
            unique_primary_file_names
        ),
        "selected_file_name_count": len(
            selected_file_names
        ),
    }


def store_project_input(
    conn: sqlite3.Connection,
    result: dict[str, object],
) -> None:
    """
    Insert or update prepared classification input.
    """

    conn.execute(
        """
        INSERT INTO classification_inputs (
            project_id,
            repository_id,
            project_type,
            metadata_text,
            file_names_text,
            file_content_text,
            combined_text,
            primary_file_count,
            extracted_file_count
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)

        ON CONFLICT(project_id) DO UPDATE SET
            repository_id = excluded.repository_id,
            project_type = excluded.project_type,
            metadata_text = excluded.metadata_text,
            file_names_text = excluded.file_names_text,
            file_content_text = excluded.file_content_text,
            combined_text = excluded.combined_text,
            primary_file_count = excluded.primary_file_count,
            extracted_file_count = excluded.extracted_file_count
        """,
        (
            result["project_id"],
            result["repository_id"],
            result["project_type"],
            result["metadata_text"],
            result["file_names_text"],
            result["file_content_text"],
            result["combined_text"],
            result["primary_file_count"],
            result["extracted_file_count"],
        ),
    )


def verify_results(
    conn: sqlite3.Connection,
    expected_projects: int,
) -> None:
    """
    Verify all relevant projects received classification input.
    """

    actual_count = conn.execute(
        """
        SELECT COUNT(*)
        FROM classification_inputs
        """
    ).fetchone()[0]

    if actual_count != expected_projects:
        raise RuntimeError(
            "Classification input verification failed. "
            f"Expected {expected_projects} rows, "
            f"but found {actual_count}."
        )

    empty_count = conn.execute(
        """
        SELECT COUNT(*)
        FROM classification_inputs
        WHERE combined_text IS NULL
           OR TRIM(combined_text) = ''
        """
    ).fetchone()[0]

    print("\nVerification successful.")

    print(
        f"Prepared classification inputs: "
        f"{actual_count}"
    )

    print(
        f"Empty combined inputs: "
        f"{empty_count}"
    )


def show_summary(
    conn: sqlite3.Connection,
) -> None:
    """
    Show preparation statistics by repository and project type.
    """

    print("\n" + "=" * 72)
    print("CLASSIFICATION INPUT SUMMARY")
    print("=" * 72)

    rows = conn.execute(
        """
        SELECT
            repository_id,
            project_type,
            COUNT(*) AS projects,
            SUM(primary_file_count) AS primary_files,
            SUM(extracted_file_count) AS extracted_files
        FROM classification_inputs
        GROUP BY repository_id, project_type
        ORDER BY repository_id, project_type
        """
    ).fetchall()

    for (
        repository_id,
        project_type,
        projects,
        primary_files,
        extracted_files,
    ) in rows:

        print(
            f"\nRepository {repository_id}"
            f" | {project_type}"
        )

        print(
            f"  Projects         : {projects}"
        )

        print(
            f"  Primary files    : "
            f"{primary_files or 0}"
        )

        print(
            f"  Extracted files  : "
            f"{extracted_files or 0}"
        )


def main() -> None:
    """
    Main entry point.
    """

    print("=" * 72)
    print(
        "SEEDING QDARCHIVE - "
        "PREPARE CLASSIFICATION INPUT"
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

    print("\nDownload folder:")
    print(DOWNLOAD_ROOT)

    if PDF_SUPPORT_AVAILABLE:
        print(
            "\nPDF text extraction: AVAILABLE"
        )
    else:
        print(
            "\nPDF text extraction: NOT AVAILABLE"
        )
        print(
            "Install with: "
            "python -m pip install pypdf"
        )

    print(
        f"\nMaximum filenames per project input: "
        f"{MAX_FILE_NAMES_PER_PROJECT}"
    )

    try:

        print(
            "\nIndexing local downloaded files..."
        )

        file_index = build_local_file_index()

        indexed_count = sum(
            len(paths)
            for paths in file_index.values()
        )

        print(
            f"Local files indexed: "
            f"{indexed_count}"
        )

        with sqlite3.connect(
            CLASSIFICATION_DB
        ) as conn:

            create_classification_inputs_table(
                conn
            )

            projects = conn.execute(
                """
                SELECT
                    id,
                    repository_id,
                    type,
                    title,
                    description,
                    language,
                    download_repository_folder,
                    download_project_folder,
                    download_version_folder
                FROM projects
                WHERE type IN (
                    'QDA_PROJECT',
                    'QD_PROJECT'
                )
                ORDER BY id
                """
            ).fetchall()

            print(
                f"\nRelevant projects found: "
                f"{len(projects)}"
            )

            # Remove old prepared inputs so no stale
            # classification evidence remains.
            conn.execute(
                """
                DELETE FROM classification_inputs
                """
            )

            for (
                project_id,
                repository_id,
                project_type,
                title,
                description,
                language,
                download_repository_folder,
                download_project_folder,
                download_version_folder,
            ) in projects:

                result = prepare_project_input(
                    conn=conn,
                    project_id=project_id,
                    repository_id=repository_id,
                    project_type=project_type,
                    title=title,
                    description=description,
                    language=language,
                    download_repository_folder=(
                        download_repository_folder
                    ),
                    download_project_folder=(
                        download_project_folder
                    ),
                    download_version_folder=(
                        download_version_folder
                    ),
                    file_index=file_index,
                )

                store_project_input(
                    conn,
                    result,
                )

                print(
                    f"Project {project_id:>3}"
                    f" | Repo {repository_id}"
                    f" | {project_type:<12}"
                    f" | Primary files: "
                    f"{result['primary_file_count']}"
                    f" | Names used: "
                    f"{result['selected_file_name_count']}"
                    f" | Extracted: "
                    f"{result['extracted_file_count']}"
                )

            conn.commit()

            verify_results(
                conn,
                len(projects),
            )

            show_summary(conn)

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
        "Classification input preparation completed."
    )
    print("=" * 72)


if __name__ == "__main__":
    main()
