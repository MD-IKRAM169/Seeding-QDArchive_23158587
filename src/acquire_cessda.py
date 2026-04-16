import time
import re
import xml.etree.ElementTree as ET
from html import unescape
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests

from src.config import (
    REPOSITORIES,
    SEARCH_QUERIES,
    QDA_EXTENSIONS,
    PRIMARY_DATA_EXTENSIONS,
)
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
from src.utils import ensure_dir, slugify, get_extension, download_file, filename_from_url


OAI_BASE_URL = "https://datacatalogue.cessda.eu/oai-pmh/v0/oai"
REQUEST_DELAY = 1.0

NS_OAI = "http://www.openarchives.org/OAI/2.0/"
NS_DC = "http://purl.org/dc/elements/1.1/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (QDArchive project)",
    "Accept": "application/xml, text/xml, application/xhtml+xml, text/html;q=0.9,*/*;q=0.8",
}


def oai_list_records(
    query_keyword: Optional[str] = None,
    max_records: int = 10,
) -> list[ET.Element]:
    params = {
        "verb": "ListRecords",
        "metadataPrefix": "oai_dc",
    }

    records = []
    seen_ids = set()
    page_count = 0
    max_pages = 10

    while len(records) < max_records and page_count < max_pages:
        page_count += 1

        response = requests.get(
            OAI_BASE_URL,
            params=params,
            timeout=90,
            headers=HEADERS,
        )
        response.raise_for_status()

        root = ET.fromstring(response.content)

        for record in root.iter(f"{{{NS_OAI}}}record"):
            header = record.find(f"{{{NS_OAI}}}header")
            if header is not None and header.get("status") == "deleted":
                continue

            identifier_el = record.find(f".//{{{NS_OAI}}}identifier")
            rec_id = (
                identifier_el.text.strip()
                if identifier_el is not None and identifier_el.text
                else None
            )

            if rec_id and rec_id in seen_ids:
                continue
            if rec_id:
                seen_ids.add(rec_id)

            record_text = ET.tostring(record, encoding="unicode").lower()

            if query_keyword:
                q = query_keyword.lower().strip()
                q_words = q.split()

                if not any(word in record_text for word in q_words):
                    continue

            records.append(record)

            if len(records) >= max_records:
                break

        token_el = root.find(f".//{{{NS_OAI}}}resumptionToken")
        if token_el is None or not token_el.text or len(records) >= max_records:
            break

        params = {
            "verb": "ListRecords",
            "resumptionToken": token_el.text.strip(),
        }
        time.sleep(REQUEST_DELAY)

    return records


def first_dc(record: ET.Element, tag: str) -> Optional[str]:
    el = record.find(f".//{{{NS_DC}}}{tag}")
    if el is not None and el.text:
        return el.text.strip()
    return None


def all_dc(record: ET.Element, tag: str) -> list[str]:
    values = []
    for el in record.findall(f".//{{{NS_DC}}}{tag}"):
        if el.text:
            text = el.text.strip()
            if text:
                values.append(text)
    return values


def parse_study_from_oai(record: ET.Element) -> dict:
    oai_id_el = record.find(f".//{{{NS_OAI}}}identifier")
    oai_id = oai_id_el.text.strip() if oai_id_el is not None and oai_id_el.text else None

    title = first_dc(record, "title") or "CESSDA study"
    description = first_dc(record, "description")
    language = first_dc(record, "language")
    upload_date = first_dc(record, "date")
    rights_value = first_dc(record, "rights") or "UNKNOWN"

    identifiers = all_dc(record, "identifier")
    subjects = all_dc(record, "subject")
    creators = all_dc(record, "creator")
    contributors = all_dc(record, "contributor")

    doi = next((x for x in identifiers if "doi" in x.lower()), None)

    # Prefer a normal HTTP identifier as landing page
    url = next((x for x in identifiers if x.startswith("http")), None)
    study_url = url or (f"https://datacatalogue.cessda.eu/detail/{oai_id}" if oai_id else None)

    people = []
    for name in creators:
        if name.strip():
            people.append((name.strip(), "AUTHOR"))

    for name in contributors:
        if name.strip():
            people.append((name.strip(), "OTHER"))

    return {
        "study_id": oai_id,
        "study_url": study_url,
        "title": title,
        "description": description,
        "language": language,
        "doi": doi,
        "upload_date": upload_date,
        "license": rights_value,
        "keywords": subjects,
        "people": people,
        "identifiers": identifiers,
    }


def is_probable_download_link(url: str) -> bool:
    if not url:
        return False

    lowered = url.lower()
    path = urlparse(lowered).path

    all_exts = {ext.lower() for ext in QDA_EXTENSIONS.union(PRIMARY_DATA_EXTENSIONS)}

    # Direct file extension match
    for ext in all_exts:
        if path.endswith(ext):
            return True

    # Common download/file patterns
    download_markers = [
        "/download",
        "download=",
        "download?",
        "/file/",
        "/files/",
        "/bitstream/",
        "/media/",
        "api/access/datafile",
        "attachment",
    ]
    if any(marker in lowered for marker in download_markers):
        return True

    return False


def extract_links_from_html(html: str, base_url: str) -> list[str]:
    html = unescape(html)
    hrefs = re.findall(r'href=["\']([^"\']+)["\']', html, flags=re.IGNORECASE)

    links = []
    seen = set()

    for href in hrefs:
        absolute = urljoin(base_url, href.strip())
        if absolute in seen:
            continue
        seen.add(absolute)
        links.append(absolute)

    return links


def find_candidate_file_links(study_url: str, identifiers: list[str]) -> list[str]:
    candidates = []

    # 1) identifier URLs that look like direct file links
    for ident in identifiers:
        if ident.startswith("http") and is_probable_download_link(ident):
            candidates.append(ident)

    # 2) crawl landing page links
    try:
        response = requests.get(study_url, timeout=60, headers=HEADERS)
        response.raise_for_status()

        page_links = extract_links_from_html(response.text, study_url)

        for link in page_links:
            if is_probable_download_link(link):
                candidates.append(link)

    except requests.RequestException:
        pass

    # Deduplicate, keep order
    unique = []
    seen = set()
    for link in candidates:
        if link not in seen:
            seen.add(link)
            unique.append(link)

    return unique


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


def store_study(study_meta: dict, query: str) -> None:
    repo = REPOSITORIES["cessda"]

    study_url = study_meta.get("study_url")
    if not study_url:
        return

    title = study_meta.get("title") or "CESSDA study"
    description = study_meta.get("description")
    language = study_meta.get("language")
    doi = study_meta.get("doi")
    upload_date = study_meta.get("upload_date")
    license_value = study_meta.get("license") or "UNKNOWN"
    keywords = study_meta.get("keywords", [])
    people = study_meta.get("people", [])
    identifiers = study_meta.get("identifiers", [])

    project_folder = slugify(title)
    project_dir = repo["download_folder"] / project_folder
    ensure_dir(project_dir)

    if project_exists(study_url):
        project_id = get_project_id_by_url(study_url)
        if project_id is None:
            return
        print(f"  Already stored: {title[:80]}")
        return

    project_id = insert_project(
        query_string=query,
        repository_id=repo["id"],
        repository_url=repo["url"],
        project_url=study_url,
        version=None,
        title=title,
        description=description,
        language=language,
        doi=doi,
        upload_date=upload_date,
        download_repository_folder="cessda",
        download_project_folder=project_folder,
        download_version_folder=None,
        download_method="OAI-PMH+HTML",
    )

    insert_keywords(project_id, keywords)
    insert_person_roles(project_id, people if people else [("UNKNOWN", "UNKNOWN")])
    insert_license(project_id, license_value)

    # Try to find public file links
    candidate_links = find_candidate_file_links(study_url, identifiers)

    if not candidate_links:
        insert_file(
            project_id=project_id,
            file_name="metadata_only",
            file_type="metadata",
            status="FAILED_SERVER",
        )
        print(f"  Stored metadata only: {title[:80]}")
        return

    success_count = 0

    for link in candidate_links:
        file_name = filename_from_url(link, default="downloaded_file")
        ext = get_extension(file_name)

        # If no extension from URL, keep generic but still try
        if not file_name or file_name == "downloaded_file":
            parsed_path = urlparse(link).path
            guessed_name = parsed_path.rstrip("/").split("/")[-1]
            file_name = guessed_name if guessed_name else "downloaded_file"

        local_path = project_dir / file_name

        success, _, _, error = download_file(link, local_path)

        if success:
            status = "SUCCEEDED"
            success_count += 1
        else:
            status = classify_download_error(error)

        insert_file(
            project_id=project_id,
            file_name=file_name,
            file_type=ext or "unknown",
            status=status,
        )

        time.sleep(0.3)

    if success_count == 0:
        # keep one clear metadata marker if nothing downloaded successfully
        insert_file(
            project_id=project_id,
            file_name="metadata_only",
            file_type="metadata",
            status="FAILED_SERVER",
        )

    print(f"  Stored: {title[:80]} | downloaded={success_count} file(s)")


def run_cessda(max_per_query: int = 10) -> None:
    repo = REPOSITORIES["cessda"]
    ensure_dir(repo["download_folder"])

    for query in SEARCH_QUERIES:
        print(f"\n{'=' * 60}")
        print(f"Searching CESSDA for: {query!r}")
        print(f"{'=' * 60}")

        try:
            records = oai_list_records(query_keyword=query, max_records=max_per_query)
            print(f"  OAI-PMH returned {len(records)} matching record(s).")

            for record in records:
                try:
                    meta = parse_study_from_oai(record)
                    store_study(meta, query)
                    time.sleep(REQUEST_DELAY)
                except Exception as e:
                    print(f"  Record error: {e}")

        except Exception as exc:
            print(f"  CESSDA error: {exc}")


if __name__ == "__main__":
    init_db()
    run_cessda(max_per_query=10)