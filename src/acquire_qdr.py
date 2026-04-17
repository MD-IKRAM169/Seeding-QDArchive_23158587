import time
from typing import Optional

import requests

from src.config import REPOSITORIES, SEARCH_QUERIES
from src.db import (
    init_db,
    insert_project,
    insert_file,
    insert_keywords,
    insert_person_roles,
    insert_license,
    project_exists,
    get_project_id_by_url,
)
from src.utils import ensure_dir, slugify, get_extension, download_file


BASE_API = "https://data.qdr.syr.edu/api"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (QDArchive project)",
    "Accept": "application/json",
}

REQUEST_DELAY = 0.5


def search_qdr(query: str, limit: int = 10):
    url = f"{BASE_API}/search"
    params = {
        "q": query,
        "type": "dataset",
        "per_page": limit,
    }

    response = requests.get(url, params=params, timeout=60, headers=HEADERS)
    response.raise_for_status()

    data = response.json()
    return data.get("data", {}).get("items", [])


def get_dataset_details(global_id: str):
    url = f"{BASE_API}/datasets/:persistentId"
    params = {"persistentId": global_id}

    response = requests.get(url, params=params, timeout=60, headers=HEADERS)
    response.raise_for_status()

    return response.json().get("data", {})


def extract_field_value(field: dict) -> Optional[str]:
    value = field.get("value")

    if isinstance(value, str):
        return value.strip()

    if isinstance(value, dict):
        v = value.get("value")
        if isinstance(v, str):
            return v.strip()

    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, str):
                parts.append(item.strip())
            elif isinstance(item, dict):
                iv = item.get("value")
                if isinstance(iv, str):
                    parts.append(iv.strip())
        if parts:
            return "; ".join(parts)

    return None


def extract_qdr_license(details: dict) -> str:
    latest = details.get("latestVersion", {})

    license_obj = latest.get("license")
    if isinstance(license_obj, dict):
        name = license_obj.get("name")
        uri = license_obj.get("uri")

        if isinstance(name, str) and name.strip() and isinstance(uri, str) and uri.strip():
            return f"{name.strip()} | {uri.strip()}"
        if isinstance(name, str) and name.strip():
            return name.strip()
        if isinstance(uri, str) and uri.strip():
            return uri.strip()

    terms = latest.get("termsOfUse")
    if isinstance(terms, str) and terms.strip():
        return terms.strip()

    metadata_blocks = latest.get("metadataBlocks", {})
    for _, block in metadata_blocks.items():
        for field in block.get("fields", []):
            type_name = str(field.get("typeName", "")).lower()
            if "license" in type_name or "rights" in type_name:
                value = extract_field_value(field)
                if value:
                    return value

    return "UNKNOWN"


def extract_qdr_description(details: dict) -> Optional[str]:
    latest = details.get("latestVersion", {})
    metadata_blocks = latest.get("metadataBlocks", {})
    citation = metadata_blocks.get("citation", {})
    fields = citation.get("fields", [])

    for field in fields:
        if field.get("typeName") == "dsDescription":
            value = field.get("value")
            if isinstance(value, list) and value:
                first = value[0]
                if isinstance(first, dict):
                    ds_value = first.get("dsDescriptionValue", {})
                    if isinstance(ds_value, dict):
                        desc = ds_value.get("value")
                        if isinstance(desc, str):
                            return desc.strip()
    return None


def extract_qdr_language(details: dict) -> Optional[str]:
    latest = details.get("latestVersion", {})
    metadata_blocks = latest.get("metadataBlocks", {})
    citation = metadata_blocks.get("citation", {})
    fields = citation.get("fields", [])

    for field in fields:
        if str(field.get("typeName", "")).lower() in {"language", "datasetlanguage"}:
            value = extract_field_value(field)
            if value:
                return value
    return None


def extract_qdr_upload_date(details: dict) -> Optional[str]:
    latest = details.get("latestVersion", {})
    return latest.get("createTime") or latest.get("releaseTime")


def extract_qdr_keywords(details: dict) -> list[str]:
    latest = details.get("latestVersion", {})
    metadata_blocks = latest.get("metadataBlocks", {})
    citation = metadata_blocks.get("citation", {})
    fields = citation.get("fields", [])

    keywords = []

    for field in fields:
        if field.get("typeName") == "keyword":
            value = field.get("value")
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        kw = item.get("keywordValue", {})
                        if isinstance(kw, dict):
                            v = kw.get("value")
                            if isinstance(v, str) and v.strip():
                                keywords.append(v.strip())

    return keywords


def extract_qdr_authors(details: dict) -> list[tuple[str, str]]:
    latest = details.get("latestVersion", {})
    metadata_blocks = latest.get("metadataBlocks", {})
    citation = metadata_blocks.get("citation", {})
    fields = citation.get("fields", [])

    people = []

    for field in fields:
        type_name = field.get("typeName")

        if type_name == "author":
            value = field.get("value")
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        author_name = item.get("authorName", {})
                        if isinstance(author_name, dict):
                            name = author_name.get("value")
                            if isinstance(name, str) and name.strip():
                                people.append((name.strip(), "AUTHOR"))

        elif type_name == "datasetContact":
            value = field.get("value")
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        contact_name = item.get("datasetContactName", {})
                        if isinstance(contact_name, dict):
                            name = contact_name.get("value")
                            if isinstance(name, str) and name.strip():
                                people.append((name.strip(), "OWNER"))

    return people


def file_is_restricted(file_record: dict) -> bool:
    file_info = file_record.get("dataFile", {})
    restricted = file_record.get("restricted")
    if restricted is None:
        restricted = file_info.get("restricted")
    return restricted is True


def dataset_is_fully_restricted(details: dict) -> bool:
    latest = details.get("latestVersion", {})
    files = latest.get("files", [])

    if not files:
        return False

    unrestricted_found = False
    restricted_found = False

    for f in files:
        if file_is_restricted(f):
            restricted_found = True
        else:
            unrestricted_found = True

    return restricted_found and not unrestricted_found


def get_file_categories(file_record: dict) -> list[str]:
    categories = []

    for key in ("categories", "dataFileCategories"):
        value = file_record.get(key)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str) and item.strip():
                    categories.append(item.strip())

    file_metadata = file_record.get("fileMetadata", {})
    if isinstance(file_metadata, dict):
        value = file_metadata.get("categories")
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str) and item.strip():
                    categories.append(item.strip())

    # deduplicate
    clean = []
    seen = set()
    for c in categories:
        lc = c.lower()
        if lc not in seen:
            seen.add(lc)
            clean.append(c)
    return clean


def file_is_documentation(file_record: dict) -> bool:
    file_info = file_record.get("dataFile", {})
    filename = (file_info.get("filename") or "").lower()
    content_type = (file_info.get("contentType") or "").lower()
    categories = [c.lower() for c in get_file_categories(file_record)]

    doc_name_markers = [
        "readme", "codebook", "documentation", "appendix",
        "metadata", "questionnaire", "instrument", "transcript",
        "interview guide", "methods", "protocol"
    ]

    if any(marker in filename for marker in doc_name_markers):
        return True

    if any("documentation" in c or "codebook" in c or "readme" in c for c in categories):
        return True

    if content_type in {
        "application/pdf",
        "text/plain",
        "text/rtf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }:
        return True

    return False


def get_file_label(file_record: dict) -> str:
    file_info = file_record.get("dataFile", {})
    return file_info.get("filename") or "unknown_file"


def get_file_id(file_record: dict) -> Optional[int]:
    file_info = file_record.get("dataFile", {})
    file_id = file_info.get("id")
    return int(file_id) if file_id is not None else None


def get_file_type(file_record: dict) -> str:
    filename = get_file_label(file_record)
    return get_extension(filename) or "unknown"


def classify_download_error(error: Optional[str]) -> str:
    if not error:
        return "FAILED_SERVER"

    lowered = error.lower()
    if (
        "access denied" in lowered
        or "401" in lowered
        or "403" in lowered
        or "forbidden" in lowered
        or "unauthorized" in lowered
        or "login" in lowered
        or "sign in" in lowered
    ):
        return "FAILED_LOGIN"

    return "FAILED_SERVER"


def is_open_license_text(text: Optional[str]) -> bool:
    if not text:
        return False

    lowered = text.lower()
    open_markers = [
        "creative commons",
        "cc-by",
        "cc by",
        "cc-by-sa",
        "cc by-sa",
        "cc0",
        "public domain",
        "open data commons",
    ]
    return any(marker in lowered for marker in open_markers)


def sort_files_for_download(files: list[dict]) -> list[dict]:
    def score(file_record: dict) -> tuple[int, int, str]:
        restricted_score = 1 if file_is_restricted(file_record) else 0
        documentation_score = 0 if file_is_documentation(file_record) else 1
        name = get_file_label(file_record).lower()
        return (restricted_score, documentation_score, name)

    return sorted(files, key=score)


def process_dataset(item, query):
    repo = REPOSITORIES["qdr"]

    global_id = item.get("global_id")
    title = item.get("name") or "QDR dataset"

    if not global_id:
        return

    details = get_dataset_details(global_id)
    latest = details.get("latestVersion", {})
    files = latest.get("files", [])

    license_value = extract_qdr_license(details)
    description = extract_qdr_description(details)
    language = extract_qdr_language(details)
    upload_date = extract_qdr_upload_date(details)
    keywords = extract_qdr_keywords(details)
    people = extract_qdr_authors(details)

    project_url = global_id
    project_folder_name = slugify(global_id.replace(":", "_"))
    project_dir = repo["download_folder"] / project_folder_name
    ensure_dir(project_dir)

    # Important: avoid duplicate file rows on rerun
    if project_exists(project_url):
        print(f"  Already stored: {title[:80]}")
        return

    # Better download method label
    if is_open_license_text(license_value):
        download_method = "API_PUBLIC_OPEN"
    else:
        download_method = "API_PUBLIC_OR_RESTRICTED"

    project_id = insert_project(
        query_string=query,
        repository_id=repo["id"],
        repository_url=repo["url"],
        project_url=project_url,
        version=None,
        title=title,
        description=description,
        language=language,
        doi=global_id,
        upload_date=upload_date,
        download_repository_folder="qdr",
        download_project_folder=project_folder_name,
        download_version_folder=None,
        download_method=download_method,
    )

    insert_keywords(project_id, keywords)
    insert_person_roles(project_id, people if people else [("UNKNOWN", "UNKNOWN")])
    insert_license(project_id, license_value if license_value else "UNKNOWN")

    if not files:
        insert_file(
            project_id=project_id,
            file_name="no_files_listed",
            file_type="unknown",
            status="FAILED_SERVER",
        )
        return

    if dataset_is_fully_restricted(details):
        for f in files:
            filename = get_file_label(f)
            insert_file(
                project_id=project_id,
                file_name=filename,
                file_type=get_file_type(f),
                status="FAILED_LOGIN",
            )
        return

    success_count = 0
    sorted_files = sort_files_for_download(files)

    for f in sorted_files:
        file_id = get_file_id(f)
        filename = get_file_label(f)

        if not file_id or not filename:
            continue

        # Respect explicit restriction flags
        if file_is_restricted(f):
            insert_file(
                project_id=project_id,
                file_name=filename,
                file_type=get_file_type(f),
                status="FAILED_LOGIN",
            )
            continue

        download_url = f"{BASE_API}/access/datafile/{file_id}"
        local_path = project_dir / filename

        success, _, _, error = download_file(download_url, local_path)

        status = "SUCCEEDED" if success else classify_download_error(error)

        insert_file(
            project_id=project_id,
            file_name=filename,
            file_type=get_file_type(f),
            status=status,
        )

        if success:
            success_count += 1

        time.sleep(REQUEST_DELAY)

    if success_count == 0:
        insert_file(
            project_id=project_id,
            file_name="metadata_only",
            file_type="metadata",
            status="FAILED_SERVER",
        )


def run_qdr(limit_per_query=20):
    repo = REPOSITORIES["qdr"]
    ensure_dir(repo["download_folder"])

    for query in SEARCH_QUERIES:
        print(f"\nSearching QDR for: {query}")

        try:
            items = search_qdr(query, limit=limit_per_query)
            print(f"  Found {len(items)} dataset(s)")

            for item in items:
                try:
                    process_dataset(item, query)
                    print(f"  Processed dataset: {item.get('name')}")
                except Exception as e:
                    print(f"  Error processing dataset: {e}")

        except Exception as e:
            print(f"Search error for query '{query}': {e}")


if __name__ == "__main__":
    init_db()
    run_qdr(limit_per_query=20)