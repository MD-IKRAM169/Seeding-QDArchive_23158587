from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from src.prepare_classification_input import (
    PRIMARY_DATA_EXTENSIONS,
    build_local_file_index,
    build_project_folder_hints,
    clean_text,
    extract_file_text,
    find_local_file,
    is_metadata_only_file,
    normalize_extension,
)

from src.classify_isic_projects import (
    read_isic_division_profiles,
    remove_generic_academic_words,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent

CLASSIFICATION_DB = (
    PROJECT_ROOT / "23158587-sq26-classification.db"
)

FILE_CONTENT_WEIGHT = 0.70
FILE_NAME_WEIGHT = 0.20
PROJECT_CONTEXT_WEIGHT = 0.10

WORD_MODEL_WEIGHT = 0.80
CHAR_MODEL_WEIGHT = 0.20

MIN_SECONDARY_SCORE = 0.035
SECONDARY_RATIO = 0.82


LOW_ABSOLUTE_SCORE = 0.025
HIGH_ABSOLUTE_SCORE = 0.12

LOW_RELATIVE_MARGIN = 0.08
HIGH_RELATIVE_MARGIN = 0.25


def create_file_classification_table(
    conn: sqlite3.Connection,
) -> None:
    """
    Create the detailed file-classification audit table.
    """

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS file_classifications (
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


def get_project_keywords(
    conn: sqlite3.Connection,
    project_id: int,
) -> list[str]:
    """
    Return unique project keywords.
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
        value = clean_text(row[0])

        if value:
            keywords.append(value)

    return list(dict.fromkeys(keywords))


def build_project_context(
    conn: sqlite3.Connection,
    project_id: int,
    title: str | None,
    description: str | None,
) -> str:
    """
    Build supporting project context.
    """

    keywords = get_project_keywords(
        conn,
        project_id,
    )

    parts = []

    clean_title = clean_text(title)

    if clean_title:
        parts.append(clean_title)

    clean_description = clean_text(
        description
    )

    if clean_description:
        parts.append(clean_description)

    if keywords:
        parts.append(
            " ".join(keywords)
        )

    return remove_generic_academic_words(
        " ".join(parts)
    )


def load_primary_files(
    conn: sqlite3.Connection,
    file_index: dict[str, list[Path]],
) -> list[dict[str, object]]:
   
    rows = conn.execute(
        """
        SELECT
            f.id,
            f.project_id,
            f.file_name,
            f.file_type,
            f.status,

            p.repository_id,
            p.type,
            p.title,
            p.description,
            p.class,

            p.download_repository_folder,
            p.download_project_folder,
            p.download_version_folder

        FROM files AS f

        JOIN projects AS p
            ON p.id = f.project_id

        WHERE p.type IN (
            'QDA_PROJECT',
            'QD_PROJECT'
        )

        ORDER BY
            f.project_id,
            f.id
        """
    ).fetchall()

    prepared_files = []

    for (
        file_id,
        project_id,
        file_name,
        file_type,
        status,
        repository_id,
        project_type,
        project_title,
        project_description,
        project_class,
        download_repository_folder,
        download_project_folder,
        download_version_folder,
    ) in rows:

        extension = normalize_extension(
            file_name,
            file_type,
        )

        if extension not in PRIMARY_DATA_EXTENSIONS:
            continue

        if is_metadata_only_file(file_name):
            continue

        if not project_class:
            raise RuntimeError(
                f"Project {project_id} has no ISIC class. "
                "Run Step 6 first."
            )

        project_context = build_project_context(
            conn=conn,
            project_id=project_id,
            title=project_title,
            description=project_description,
        )

        cleaned_file_name = (
            remove_generic_academic_words(
                clean_text(file_name)
            )
        )

        file_content = ""

        if status == "SUCCEEDED":

            folder_hints = (
                build_project_folder_hints(
                    download_repository_folder,
                    download_project_folder,
                    download_version_folder,
                )
            )

            local_file = find_local_file(
                file_name=file_name,
                file_index=file_index,
                project_folder_hints=folder_hints,
            )

            if local_file is not None:

                extracted_text = extract_file_text(
                    local_file,
                    extension,
                )

                file_content = (
                    remove_generic_academic_words(
                        clean_text(
                            extracted_text
                        )
                    )
                )

        if file_content:
            evidence_mode = (
                "INDEPENDENT_CONTENT_CLASSIFICATION"
            )
        else:
            evidence_mode = (
                "PROJECT_CLASS_FALLBACK"
            )

        prepared_files.append(
            {
                "file_id": file_id,
                "project_id": project_id,
                "repository_id": repository_id,
                "project_type": project_type,

                "file_name": clean_text(
                    file_name
                ),

                "file_status": clean_text(
                    status
                ),

                "file_content": file_content,

                "file_name_text": (
                    cleaned_file_name
                ),

                "project_context": (
                    project_context
                ),

                "project_class": (
                    str(project_class).strip()
                ),

                "evidence_mode": (
                    evidence_mode
                ),
            }
        )

    return prepared_files

def calculate_similarity(
    evidence_texts: list[str],
    class_texts: list[str],
):
    """
    Calculate hybrid word + character TF-IDF similarity.
    """

    corpus = (
        class_texts
        + evidence_texts
    )

    word_vectorizer = TfidfVectorizer(
        lowercase=True,
        strip_accents="unicode",
        stop_words="english",
        ngram_range=(1, 2),
        min_df=1,
        sublinear_tf=True,
        max_features=60_000,
    )

    word_matrix = (
        word_vectorizer.fit_transform(
            corpus
        )
    )

    class_word_matrix = word_matrix[
        :len(class_texts)
    ]

    evidence_word_matrix = word_matrix[
        len(class_texts):
    ]

    word_similarity = cosine_similarity(
        evidence_word_matrix,
        class_word_matrix,
    )

    char_vectorizer = TfidfVectorizer(
        analyzer="char_wb",
        lowercase=True,
        strip_accents="unicode",
        ngram_range=(3, 5),
        min_df=1,
        sublinear_tf=True,
        max_features=60_000,
    )

    char_matrix = (
        char_vectorizer.fit_transform(
            corpus
        )
    )

    class_char_matrix = char_matrix[
        :len(class_texts)
    ]

    evidence_char_matrix = char_matrix[
        len(class_texts):
    ]

    char_similarity = cosine_similarity(
        evidence_char_matrix,
        class_char_matrix,
    )

    return (
        WORD_MODEL_WEIGHT
        * word_similarity
        +
        CHAR_MODEL_WEIGHT
        * char_similarity
    )

def build_content_file_similarity_matrix(
    class_profiles: list[dict[str, str]],
    content_files: list[dict[str, object]],
):
    
    class_texts = [
        profile["profile_text"]
        for profile in class_profiles
    ]

    fields = [
        (
            "file_content",
            FILE_CONTENT_WEIGHT,
        ),
        (
            "file_name_text",
            FILE_NAME_WEIGHT,
        ),
        (
            "project_context",
            PROJECT_CONTEXT_WEIGHT,
        ),
    ]

    similarities_by_field = {}

    print(
        "\nBuilding independent content-based "
        "file classification models..."
    )

    for field_name, weight in fields:

        texts = [
            str(
                item.get(
                    field_name,
                    "",
                )
            )
            for item in content_files
        ]

        nonempty_count = sum(
            1
            for text in texts
            if text.strip()
        )

        print(
            f"  {field_name:<16}"
            f" | weight={weight:.2f}"
            f" | non-empty files="
            f"{nonempty_count}"
        )

        similarities_by_field[
            field_name
        ] = calculate_similarity(
            texts,
            class_texts,
        )

    sample_matrix = next(
        iter(
            similarities_by_field.values()
        )
    )

    final_similarity = (
        sample_matrix * 0.0
    )

    for file_index, file_info in enumerate(
        content_files
    ):

        available_weight = 0.0

        for field_name, weight in fields:

            field_text = str(
                file_info.get(
                    field_name,
                    "",
                )
            ).strip()

            if not field_text:
                continue

            final_similarity[
                file_index
            ] += (
                weight
                * similarities_by_field[
                    field_name
                ][file_index]
            )

            available_weight += weight

        if available_weight > 0:

            final_similarity[
                file_index
            ] /= available_weight

    return final_similarity


def determine_confidence(
    primary_score: float,
    second_score: float,
) -> str:
    """
    Determine classification confidence.
    """

    if primary_score <= 0:
        return "LOW"

    margin = (
        primary_score - second_score
    )

    relative_margin = (
        margin / primary_score
    )

    if (
        primary_score
        >= HIGH_ABSOLUTE_SCORE
        and
        relative_margin
        >= HIGH_RELATIVE_MARGIN
    ):
        return "HIGH"

    if (
        primary_score
        < LOW_ABSOLUTE_SCORE
        or
        relative_margin
        < LOW_RELATIVE_MARGIN
    ):
        return "LOW"

    return "MEDIUM"


def choose_independent_classes(
    scores,
    class_profiles: list[dict[str, str]],
) -> dict[str, object]:
    """
    Select primary and optional secondary classes for
    content-available files.
    """

    ranked_indexes = sorted(
        range(len(scores)),
        key=lambda index: float(
            scores[index]
        ),
        reverse=True,
    )

    primary_index = ranked_indexes[0]

    second_index = ranked_indexes[1]

    primary_score = float(
        scores[primary_index]
    )

    second_score = float(
        scores[second_index]
    )

    primary_profile = (
        class_profiles[
            primary_index
        ]
    )

    second_profile = (
        class_profiles[
            second_index
        ]
    )

    score_margin = (
        primary_score - second_score
    )

    use_secondary = (
        second_score
        >= MIN_SECONDARY_SCORE

        and primary_score > 0

        and (
            second_score / primary_score
        ) >= SECONDARY_RATIO
    )

    confidence = determine_confidence(
        primary_score,
        second_score,
    )

    result = {
        "primary_class": (
            primary_profile["code"]
        ),

        "primary_title": (
            primary_profile["title"]
        ),

        "primary_score": (
            primary_score
        ),

        "secondary_class": None,
        "secondary_title": None,
        "secondary_score": None,

        "score_margin": (
            score_margin
        ),

        "confidence": (
            confidence
        ),
    }

    if use_secondary:

        result["secondary_class"] = (
            second_profile["code"]
        )

        result["secondary_title"] = (
            second_profile["title"]
        )

        result["secondary_score"] = (
            second_score
        )

    return result

def build_project_fallback_result(
    file_info: dict[str, object],
    class_lookup: dict[str, str],
) -> dict[str, object]:
    """
    Create a transparent fallback result based on the
    already assigned project class.

    No similarity score is invented.
    """

    project_class = str(
        file_info["project_class"]
    )

    if project_class not in class_lookup:
        raise RuntimeError(
            f"Unknown project ISIC class: "
            f"{project_class}"
        )

    return {
        "primary_class": (
            project_class
        ),

        "primary_title": (
            class_lookup[
                project_class
            ]
        ),

        "primary_score": None,

        "secondary_class": None,
        "secondary_title": None,
        "secondary_score": None,

        "score_margin": None,

        "confidence": (
            "INHERITED"
        ),
    }

def store_result(
    conn: sqlite3.Connection,
    file_info: dict[str, object],
    result: dict[str, object],
) -> None:
    """
    Store classification result and update files.class.
    """

    timestamp = datetime.now(
        timezone.utc
    ).isoformat()

    if (
        file_info["evidence_mode"]
        == "INDEPENDENT_CONTENT_CLASSIFICATION"
    ):
        method = (
            "weighted_content_file_hybrid_tfidf_v2_"
            "isic_rev5_division"
        )

    else:
        method = (
            "project_primary_class_fallback_v1"
        )

    input_characters = sum(
        len(
            str(
                file_info.get(
                    field,
                    "",
                )
            )
        )
        for field in (
            "file_content",
            "file_name_text",
            "project_context",
        )
    )

    conn.execute(
        """
        INSERT INTO file_classifications (
            file_id,
            project_id,
            repository_id,
            project_type,

            primary_class,
            primary_title,
            primary_score,

            secondary_class,
            secondary_title,
            secondary_score,

            score_margin,

            confidence,
            evidence_mode,

            input_characters,
            file_status,

            method,
            classified_at
        )

        VALUES (
            ?, ?, ?, ?,
            ?, ?, ?,
            ?, ?, ?,
            ?,
            ?, ?,
            ?, ?,
            ?, ?
        )

        ON CONFLICT(file_id) DO UPDATE SET
            project_id = excluded.project_id,
            repository_id = excluded.repository_id,
            project_type = excluded.project_type,

            primary_class = excluded.primary_class,
            primary_title = excluded.primary_title,
            primary_score = excluded.primary_score,

            secondary_class = excluded.secondary_class,
            secondary_title = excluded.secondary_title,
            secondary_score = excluded.secondary_score,

            score_margin = excluded.score_margin,

            confidence = excluded.confidence,
            evidence_mode = excluded.evidence_mode,

            input_characters = excluded.input_characters,
            file_status = excluded.file_status,

            method = excluded.method,
            classified_at = excluded.classified_at
        """,
        (
            file_info["file_id"],
            file_info["project_id"],
            file_info["repository_id"],
            file_info["project_type"],

            result["primary_class"],
            result["primary_title"],
            result["primary_score"],

            result["secondary_class"],
            result["secondary_title"],
            result["secondary_score"],

            result["score_margin"],

            result["confidence"],
            file_info["evidence_mode"],

            input_characters,
            file_info["file_status"],

            method,
            timestamp,
        ),
    )

    conn.execute(
        """
        UPDATE files
        SET class = ?
        WHERE id = ?
        """,
        (
            result["primary_class"],
            file_info["file_id"],
        ),
    )

def verify_results(
    conn: sqlite3.Connection,
    expected_count: int,
) -> None:
    """
    Verify all selected primary files received a class.
    """

    actual_count = conn.execute(
        """
        SELECT COUNT(*)
        FROM file_classifications
        """
    ).fetchone()[0]

    if actual_count != expected_count:

        raise RuntimeError(
            "File classification verification failed. "
            f"Expected {expected_count} results, "
            f"but found {actual_count}."
        )

    missing_class_count = conn.execute(
        """
        SELECT COUNT(*)

        FROM file_classifications AS fc

        JOIN files AS f
            ON f.id = fc.file_id

        WHERE
            f.class IS NULL
            OR TRIM(f.class) = ''
        """
    ).fetchone()[0]

    if missing_class_count != 0:

        raise RuntimeError(
            f"{missing_class_count} classified files "
            "have no files.class value."
        )

    print("\nVerification successful.")

    print(
        f"Classified primary files: "
        f"{actual_count}"
    )

    print(
        "Classified files without files.class: "
        f"{missing_class_count}"
    )


def show_summary(
    conn: sqlite3.Connection,
) -> None:
    """
    Show final file-classification statistics.
    """

    print("\n" + "=" * 78)
    print("FILE CLASSIFICATION SUMMARY")
    print("=" * 78)

    rows = conn.execute(
        """
        SELECT
            repository_id,
            project_type,
            COUNT(*)

        FROM file_classifications

        GROUP BY
            repository_id,
            project_type

        ORDER BY
            repository_id,
            project_type
        """
    ).fetchall()

    for (
        repository_id,
        project_type,
        count,
    ) in rows:

        print(
            f"Repository {repository_id}"
            f" | {project_type:<12}"
            f" | Files: {count}"
        )

    print("\nEvidence modes:")

    evidence_rows = conn.execute(
        """
        SELECT
            evidence_mode,
            COUNT(*)

        FROM file_classifications

        GROUP BY evidence_mode

        ORDER BY COUNT(*) DESC
        """
    ).fetchall()

    for evidence_mode, count in evidence_rows:

        print(
            f"  {evidence_mode:<38}"
            f": {count}"
        )

    print("\nConfidence levels:")

    confidence_rows = conn.execute(
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

    for confidence, count in confidence_rows:

        print(
            f"  {confidence:<10}: {count}"
        )

    print(
        "\nIndependent content-based "
        "classifications:"
    )

    independent_rows = conn.execute(
        """
        SELECT
            primary_class,
            primary_title,
            COUNT(*) AS class_count

        FROM file_classifications

        WHERE evidence_mode =
            'INDEPENDENT_CONTENT_CLASSIFICATION'

        GROUP BY
            primary_class,
            primary_title

        ORDER BY
            class_count DESC,
            primary_class

        LIMIT 20
        """
    ).fetchall()

    if not independent_rows:
        print(
            "  No independent content-based "
            "classifications found."
        )
    else:

        for (
            code,
            title,
            count,
        ) in independent_rows:

            print(
                f"  {code:<4}"
                f" | {count:>4}"
                f" | {title}"
            )

    print(
        "\nAll file classes including "
        "project fallback:"
    )

    all_rows = conn.execute(
        """
        SELECT
            primary_class,
            primary_title,
            COUNT(*) AS class_count

        FROM file_classifications

        GROUP BY
            primary_class,
            primary_title

        ORDER BY
            class_count DESC,
            primary_class

        LIMIT 20
        """
    ).fetchall()

    for (
        code,
        title,
        count,
    ) in all_rows:

        print(
            f"  {code:<4}"
            f" | {count:>5}"
            f" | {title}"
        )


def main() -> None:
    """
    Main entry point.
    """

    print("=" * 78)

    print(
        "SEEDING QDARCHIVE - "
        "IMPROVED ISIC REV. 5 PRIMARY FILE CLASSIFIER"
    )

    print("=" * 78)

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

        print(
            "\nReading ISIC Rev. 5 "
            "division profiles..."
        )

        class_profiles = (
            read_isic_division_profiles()
        )

        print(
            "ISIC division profiles loaded: "
            f"{len(class_profiles)}"
        )

        class_lookup = {
            profile["code"]:
            profile["title"]

            for profile
            in class_profiles
        }

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

            create_file_classification_table(
                conn
            )

            prepared_files = (
                load_primary_files(
                    conn,
                    file_index,
                )
            )

            print(
                "\nPrimary files to process: "
                f"{len(prepared_files)}"
            )

            if not prepared_files:

                raise RuntimeError(
                    "No primary files found."
                )

            content_files = [
                file_info

                for file_info
                in prepared_files

                if (
                    file_info[
                        "evidence_mode"
                    ]
                    ==
                    "INDEPENDENT_CONTENT_CLASSIFICATION"
                )
            ]

            fallback_files = [
                file_info

                for file_info
                in prepared_files

                if (
                    file_info[
                        "evidence_mode"
                    ]
                    ==
                    "PROJECT_CLASS_FALLBACK"
                )
            ]

            print(
                "Independent content files: "
                f"{len(content_files)}"
            )

            print(
                "Project-class fallback files: "
                f"{len(fallback_files)}"
            )

            content_similarities = None

            if content_files:

                content_similarities = (
                    build_content_file_similarity_matrix(
                        class_profiles,
                        content_files,
                    )
                )

            conn.execute(
                """
                DELETE FROM file_classifications
                """
            )

            conn.execute(
                """
                UPDATE files

                SET class = NULL

                WHERE project_id IN (
                    SELECT id
                    FROM projects
                    WHERE type IN (
                        'QDA_PROJECT',
                        'QD_PROJECT'
                    )
                )
                """
            )

            print(
                "\nClassifying files..."
            )

            independent_count = 0

            for index, file_info in enumerate(
                content_files
            ):

                result = (
                    choose_independent_classes(
                        content_similarities[
                            index
                        ],
                        class_profiles,
                    )
                )

                store_result(
                    conn,
                    file_info,
                    result,
                )

                independent_count += 1

            fallback_count = 0

            for file_info in fallback_files:

                result = (
                    build_project_fallback_result(
                        file_info,
                        class_lookup,
                    )
                )

                store_result(
                    conn,
                    file_info,
                    result,
                )

                fallback_count += 1

            conn.commit()

            print(
                f"  Independent classifications: "
                f"{independent_count}"
            )

            print(
                f"  Project-class fallbacks: "
                f"{fallback_count}"
            )

            verify_results(
                conn,
                len(prepared_files),
            )

            show_summary(conn)

    except (
        FileNotFoundError,
        RuntimeError,
        sqlite3.Error,
        OSError,
        ValueError,
    ) as error:

        print("\nERROR:")

        print(error)

        raise SystemExit(1) from error

    print("\n" + "=" * 78)

    print("SUCCESS")

    print(
        "Improved ISIC Rev. 5 primary file "
        "classification completed."
    )

    print("=" * 78)


if __name__ == "__main__":
    main()
