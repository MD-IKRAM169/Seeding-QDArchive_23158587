import time
import re
import xml.etree.ElementTree as ET
from collections import deque
from html import unescape
from pathlib import Path
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
from src.utils import ensure_dir, slugify, get_extension, filename_from_url


OAI_BASE_URL = "https://datacatalogue.cessda.eu/oai-pmh/v0/oai"
REQUEST_DELAY = 1.0

NS_OAI = "http://www.openarchives.org/OAI/2.0/"
NS_DC = "http://purl.org/dc/elements/1.1/"
NS_DATACITE = {
    "oai": "http://www.openarchives.org/OAI/2.0/",
    "oai_datacite": "http://schema.datacite.org/oai/oai-1.1/",
    "dcite": "http://datacite.org/schema/kernel-4",
}
NS_DDI25 = {
    "oai": "http://www.openarchives.org/OAI/2.0/",
    "codeBook": "http://www.icpsr.umich.edu/DDI",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (QDArchive project)",
    "Accept": "application/xml, text/xml, application/xhtml+xml, text/html;q=0.9,*/*;q=0.8",
}

HTML_HEADERS = {
    "User-Agent": "Mozilla/5.0 (QDArchive project)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

BINARY_HEADERS = {
    "User-Agent": "Mozilla/5.0 (QDArchive project)",
    "Accept": "*/*",
}

ALL_EXTS = {ext.lower() for ext in QDA_EXTENSIONS.union(PRIMARY_DATA_EXTENSIONS)}

DIRECT_FILE_EXTS = {
    ".zip", ".pdf", ".txt", ".rtf", ".doc", ".docx", ".odt",
    ".csv", ".xlsx", ".xls", ".xml", ".json",
    ".jpg", ".jpeg", ".png", ".gif", ".tif", ".tiff",
    ".mp3", ".wav", ".m4a", ".mp4", ".avi", ".mov",
    ".qdpx", ".qdc", ".ppj", ".ppx", ".qlt", ".nvp", ".nvpx",
    ".mqda", ".mqbac", ".mqtc", ".mqex", ".mqmtr", ".mx24",
    ".mx24bac", ".mc24", ".mex24", ".mx22", ".mx20", ".mx18",
    ".mx12", ".mx11", ".mx5", ".mx4", ".mx3", ".mx2", ".m2k",
    ".loa", ".sea", ".mtr", ".mod", ".mex22", ".f4p",
}

HTML_LIKE_CONTENT_TYPES = {
    "text/html",
    "application/xhtml+xml",
}

FILE_LIKE_CONTENT_TYPES = (
    "application/pdf",
    "application/zip",
    "application/octet-stream",
    "application/json",
    "application/xml",
    "text/plain",
    "text/csv",
    "audio/",
    "video/",
    "image/",
)

DOWNLOAD_TEXT_HINTS = [
    "download",
    "access data",
    "data files",
    "file",
    "dataset",
    "attachments",
    "supplementary",
    "material",
    "documentation",
    "codebook",
]

PAGE_PATH_HINTS = [
    "download",
    "file",
    "files",
    "bitstream",
    "attachment",
    "media",
    "document",
    "datafile",
    "dataset",
    "resource",
    "access",
]


def request_xml(params: dict) -> ET.Element:
    response = requests.get(
        OAI_BASE_URL,
        params=params,
        timeout=90,
        headers=HEADERS,
    )
    response.raise_for_status()
    return ET.fromstring(response.content)


def oai_list_records(
    query_keyword: Optional[str] = None,
    max_records: int = 20,
    metadata_prefix: str = "oai_dc",
) -> list[ET.Element]:
    params = {
        "verb": "ListRecords",
        "metadataPrefix": metadata_prefix,
    }

    records: list[ET.Element] = []
    seen_ids: set[str] = set()
    page_count = 0
    max_pages = 30

    while len(records) < max_records and page_count < max_pages:
        page_count += 1
        root = request_xml(params)

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
                q_words = [w for w in re.split(r"\s+", q) if w]
                if q_words and not any(word in record_text for word in q_words):
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


def oai_get_record(oai_identifier: str, metadata_prefix: str) -> Optional[ET.Element]:
    try:
        root = request_xml(
            {
                "verb": "GetRecord",
                "identifier": oai_identifier,
                "metadataPrefix": metadata_prefix,
            }
        )
        return root.find(f".//{{{NS_OAI}}}record")
    except Exception:
        return None


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


def extract_urls_from_text(text: str) -> list[str]:
    if not text:
        return []

    urls = re.findall(r"https?://[^\s<>\"]+", text)
    clean = []
    seen = set()

    for url in urls:
        url = url.rstrip(").,;]")
        if url not in seen:
            seen.add(url)
            clean.append(url)

    return clean


def extract_urls_from_xml(record: Optional[ET.Element]) -> list[str]:
    if record is None:
        return []

    xml_text = ET.tostring(record, encoding="unicode")
    return extract_urls_from_text(xml_text)


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
    parsed = urlparse(lowered)
    path = parsed.path

    for ext in ALL_EXTS:
        if path.endswith(ext):
            return True

    if any(marker in lowered for marker in [
        "/download",
        "download=",
        "download?",
        "/file/",
        "/files/",
        "/bitstream/",
        "/media/",
        "/attachment/",
        "/attachments/",
        "/document/",
        "/documents/",
        "api/access/datafile",
        "content-disposition=attachment",
        "format=download",
        "export=",
    ]):
        return True

    return False


def is_probable_dataset_page(url: str) -> bool:
    if not url:
        return False

    lowered = url.lower()
    return any(hint in lowered for hint in PAGE_PATH_HINTS)


def extract_links_from_html(html: str, base_url: str) -> list[tuple[str, str]]:
    html = unescape(html)

    href_matches = re.findall(
        r"<a\b[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>",
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )

    links = []
    seen = set()

    for href, anchor_html in href_matches:
        absolute = urljoin(base_url, href.strip())
        if absolute in seen:
            continue
        seen.add(absolute)

        anchor_text = re.sub(r"<[^>]+>", " ", anchor_html)
        anchor_text = re.sub(r"\s+", " ", anchor_text).strip()
        links.append((absolute, anchor_text))

    return links


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
        or "register" in lowered
    ):
        return "FAILED_LOGIN"

    return "FAILED_SERVER"


def response_looks_like_html(content_type: Optional[str], first_chunk: bytes) -> bool:
    ctype = (content_type or "").lower()

    if any(x in ctype for x in HTML_LIKE_CONTENT_TYPES):
        return True

    sample = first_chunk[:1000].strip().lower()
    return (
        sample.startswith(b"<!doctype html")
        or sample.startswith(b"<html")
        or b"<html" in sample
        or b"<body" in sample
        or b"<form" in sample
        or b"login" in sample[:300]
        or b"sign in" in sample[:300]
    )


def response_looks_like_file(content_type: Optional[str], url: str) -> bool:
    ctype = (content_type or "").lower()
    path = urlparse(url.lower()).path

    if any(ctype.startswith(prefix) for prefix in FILE_LIKE_CONTENT_TYPES):
        return True

    if Path(path).suffix.lower() in DIRECT_FILE_EXTS:
        return True

    disposition_file_markers = [
        ".pdf", ".zip", ".csv", ".xlsx", ".xls", ".xml", ".json", ".txt",
        ".doc", ".docx", ".odt", ".jpg", ".jpeg", ".png", ".gif", ".tif",
        ".tiff", ".mp3", ".wav", ".m4a", ".mp4", ".avi", ".mov",
    ]
    return any(path.endswith(ext) for ext in disposition_file_markers)


def safe_get(url: str, timeout: int = 60, allow_redirects: bool = True) -> Optional[requests.Response]:
    try:
        response = requests.get(
            url,
            timeout=timeout,
            headers=HTML_HEADERS,
            allow_redirects=allow_redirects,
        )
        return response
    except requests.RequestException:
        return None


def probe_download_url(url: str) -> tuple[bool, Optional[str], Optional[str]]:
    """
    Returns:
        (is_downloadable_file, error_status, content_type)
    """
    try:
        with requests.get(
            url,
            stream=True,
            timeout=60,
            headers=BINARY_HEADERS,
            allow_redirects=True,
        ) as response:
            if response.status_code in (401, 403):
                return False, "FAILED_LOGIN", response.headers.get("Content-Type")

            if response.status_code >= 400:
                return False, "FAILED_SERVER", response.headers.get("Content-Type")

            content_type = response.headers.get("Content-Type", "")
            first_chunk = b""
            try:
                for chunk in response.iter_content(chunk_size=2048):
                    if chunk:
                        first_chunk = chunk
                        break
            except requests.RequestException:
                return False, "FAILED_SERVER", content_type

            if response_looks_like_html(content_type, first_chunk):
                return False, "FAILED_SERVER", content_type

            if response_looks_like_file(content_type, url):
                return True, None, content_type

            return False, "FAILED_SERVER", content_type

    except requests.RequestException:
        return False, "FAILED_SERVER", None


def download_binary_file(url: str, destination: Path) -> tuple[bool, Optional[str], Optional[int], Optional[str]]:
    try:
        with requests.get(
            url,
            stream=True,
            timeout=90,
            headers=BINARY_HEADERS,
            allow_redirects=True,
        ) as response:
            if response.status_code in (401, 403):
                return False, None, None, f"Access denied: HTTP {response.status_code}"

            if response.status_code >= 400:
                return False, None, None, f"HTTP error: {response.status_code}"

            content_type = response.headers.get("Content-Type", "")
            content_length = response.headers.get("Content-Length")
            file_size = int(content_length) if content_length and content_length.isdigit() else None

            first_chunk = b""
            chunks = []

            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    if not first_chunk:
                        first_chunk = chunk
                    chunks.append(chunk)
                    if len(chunks) >= 1:
                        break

            if response_looks_like_html(content_type, first_chunk):
                return False, content_type, file_size, "Downloaded HTML instead of a file"

            ensure_dir(destination.parent)

            with open(destination, "wb") as f:
                if first_chunk:
                    f.write(first_chunk)

                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            return True, content_type, file_size, None

    except requests.RequestException as exc:
        return False, None, None, str(exc)


def normalize_candidate_name(url: str, content_type: Optional[str]) -> str:
    name = filename_from_url(url, default="downloaded_file")
    suffix = Path(urlparse(url).path).suffix.lower()

    if suffix:
        return name

    ctype = (content_type or "").lower()
    if "application/pdf" in ctype:
        return f"{name}.pdf"
    if "application/zip" in ctype:
        return f"{name}.zip"
    if "text/csv" in ctype:
        return f"{name}.csv"
    if "application/json" in ctype:
        return f"{name}.json"
    if "application/xml" in ctype or "text/xml" in ctype:
        return f"{name}.xml"
    if "text/plain" in ctype:
        return f"{name}.txt"

    return name


def collect_seed_urls(study_url: str, identifiers: list[str], doi: Optional[str], oai_id: Optional[str]) -> list[str]:
    seeds = []

    for ident in identifiers:
        if ident.startswith("http"):
            seeds.append(ident)

    if doi and doi.startswith("10."):
        seeds.append(f"https://doi.org/{doi}")

    if study_url:
        seeds.append(study_url)

    if oai_id:
        seeds.append(f"https://datacatalogue.cessda.eu/detail/{oai_id}")

    unique = []
    seen = set()
    for url in seeds:
        if url and url not in seen:
            seen.add(url)
            unique.append(url)
    return unique


def crawl_for_candidate_links(seed_urls: list[str], max_pages: int = 12, max_depth: int = 2) -> list[str]:
    candidates: list[str] = []
    seen_urls: set[str] = set()
    queued: set[str] = set()
    queue = deque()

    for seed in seed_urls:
        queue.append((seed, 0))
        queued.add(seed)

    while queue and len(seen_urls) < max_pages:
        current_url, depth = queue.popleft()

        if current_url in seen_urls:
            continue
        seen_urls.add(current_url)

        response = safe_get(current_url)
        if response is None:
            continue

        if response.status_code in (401, 403):
            candidates.append(current_url)
            continue

        if response.status_code >= 400:
            continue

        content_type = (response.headers.get("Content-Type") or "").lower()

        if response_looks_like_file(content_type, current_url):
            candidates.append(current_url)
            continue

        html = response.text or ""
        page_links = extract_links_from_html(html, current_url)

        for link, anchor_text in page_links:
            lowered_anchor = anchor_text.lower()
            lowered_link = link.lower()

            if is_probable_download_link(link):
                candidates.append(link)
                continue

            if any(hint in lowered_anchor for hint in DOWNLOAD_TEXT_HINTS):
                candidates.append(link)
                continue

            if depth < max_depth and (
                is_probable_dataset_page(link)
                or any(hint in lowered_anchor for hint in ["access", "data", "files", "download", "dataset", "publisher"])
            ):
                if link not in queued:
                    queue.append((link, depth + 1))
                    queued.add(link)

        time.sleep(0.3)

    unique = []
    seen = set()
    for link in candidates:
        if link not in seen:
            seen.add(link)
            unique.append(link)

    return unique


def build_candidate_links(
    study_url: str,
    identifiers: list[str],
    doi: Optional[str],
    oai_id: Optional[str],
    datacite_record: Optional[ET.Element],
    ddi_record: Optional[ET.Element],
) -> list[str]:
    candidates = []

    # 1) direct URLs from identifiers and richer XML
    for ident in identifiers:
        if ident.startswith("http"):
            candidates.append(ident)

    for url in extract_urls_from_xml(datacite_record):
        candidates.append(url)

    for url in extract_urls_from_xml(ddi_record):
        candidates.append(url)

    # 2) crawl seed pages
    seed_urls = collect_seed_urls(study_url, identifiers, doi, oai_id)
    crawled = crawl_for_candidate_links(seed_urls=seed_urls, max_pages=12, max_depth=2)
    candidates.extend(crawled)

    # 3) keep unique order
    unique = []
    seen = set()
    for link in candidates:
        if link and link not in seen:
            seen.add(link)
            unique.append(link)

    return unique


def store_study(study_meta: dict, query: str, datacite_record: Optional[ET.Element], ddi_record: Optional[ET.Element]) -> None:
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
    oai_id = study_meta.get("study_id")

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
        download_method="OAI-PMH+deep-html",
    )

    insert_keywords(project_id, keywords)
    insert_person_roles(project_id, people if people else [("UNKNOWN", "UNKNOWN")])
    insert_license(project_id, license_value)

    candidate_links = build_candidate_links(
        study_url=study_url,
        identifiers=identifiers,
        doi=doi,
        oai_id=oai_id,
        datacite_record=datacite_record,
        ddi_record=ddi_record,
    )

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
    tried_any_download_like_url = False

    for link in candidate_links:
        downloadable, probe_error, content_type = probe_download_url(link)

        if not downloadable:
            if is_probable_download_link(link):
                tried_any_download_like_url = True
                insert_file(
                    project_id=project_id,
                    file_name=filename_from_url(link, default="downloaded_file"),
                    file_type=get_extension(filename_from_url(link, default="downloaded_file")) or "unknown",
                    status=probe_error or "FAILED_SERVER",
                )
            continue

        tried_any_download_like_url = True

        file_name = normalize_candidate_name(link, content_type)
        ext = get_extension(file_name) or "unknown"
        local_path = project_dir / file_name

        success, _, _, error = download_binary_file(link, local_path)

        status = "SUCCEEDED" if success else classify_download_error(error)

        insert_file(
            project_id=project_id,
            file_name=file_name,
            file_type=ext,
            status=status,
        )

        if success:
            success_count += 1

        time.sleep(0.3)

    if success_count == 0:
        insert_file(
            project_id=project_id,
            file_name="metadata_only",
            file_type="metadata",
            status="FAILED_SERVER" if tried_any_download_like_url else "FAILED_SERVER",
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
            records = oai_list_records(
                query_keyword=query,
                max_records=max_per_query,
                metadata_prefix="oai_dc",
            )
            print(f"  OAI-PMH returned {len(records)} matching record(s).")

            for record in records:
                try:
                    meta = parse_study_from_oai(record)
                    oai_id = meta.get("study_id")

                    datacite_record = oai_get_record(oai_id, "oai_datacite") if oai_id else None
                    ddi_record = oai_get_record(oai_id, "oai_ddi25") if oai_id else None

                    store_study(meta, query, datacite_record, ddi_record)
                    time.sleep(REQUEST_DELAY)

                except Exception as e:
                    print(f"  Record error: {e}")

        except Exception as exc:
            print(f"  CESSDA error: {exc}")


if __name__ == "__main__":
    init_db()
    run_cessda(max_per_query=10)