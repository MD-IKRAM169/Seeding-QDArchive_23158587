import re
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import requests


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def slugify(text: str, max_length: int = 80) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^\w\s-]", "_", text)
    text = re.sub(r"[-\s]+", "_", text)
    text = text.strip("_")
    if not text:
        text = "item"
    return text[:max_length]


def get_extension(filename: str) -> str:
    return Path(filename).suffix.lower()


def filename_from_url(url: str, default: str = "downloaded_file") -> str:
    parsed = urlparse(url)
    name = Path(parsed.path).name
    return name if name else default


# ------------------------------
# NEW: Content validation helpers
# ------------------------------

def looks_like_html(content_type: Optional[str], first_chunk: bytes) -> bool:
    ctype = (content_type or "").lower()

    if "text/html" in ctype or "application/xhtml+xml" in ctype:
        return True

    sample = first_chunk[:1000].lower()

    return (
        sample.startswith(b"<!doctype html")
        or sample.startswith(b"<html")
        or b"<html" in sample
        or b"<body" in sample
        or b"login" in sample[:300]
        or b"sign in" in sample[:300]
    )


def looks_like_file(content_type: Optional[str], url: str) -> bool:
    ctype = (content_type or "").lower()
    path = urlparse(url.lower()).path

    # Known file content types
    if any(x in ctype for x in [
        "application/pdf",
        "application/zip",
        "application/octet-stream",
        "text/csv",
        "application/json",
        "application/xml",
        "text/plain",
        "image/",
        "audio/",
        "video/",
    ]):
        return True

    # File extension fallback
    if Path(path).suffix:
        return True

    return False


# ------------------------------
# FIXED download function
# ------------------------------

def download_file(
    url: str,
    destination: Path,
    timeout: int = 60,
    chunk_size: int = 8192,
) -> tuple[bool, Optional[str], Optional[int], Optional[str]]:
    """
    Returns:
        (success, mime_type, file_size_bytes, error_message)
    """
    try:
        with requests.get(url, stream=True, timeout=timeout, allow_redirects=True) as response:

            # --- STATUS CHECK ---
            if response.status_code in (401, 403):
                return False, None, None, f"Access denied: HTTP {response.status_code}"

            if response.status_code >= 400:
                return False, None, None, f"HTTP error: {response.status_code}"

            content_type = response.headers.get("Content-Type")
            content_length = response.headers.get("Content-Length")
            file_size = int(content_length) if content_length and content_length.isdigit() else None

            # --- READ FIRST CHUNK (IMPORTANT) ---
            first_chunk = b""
            chunks = []

            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    if not first_chunk:
                        first_chunk = chunk
                    chunks.append(chunk)
                    break

            # --- VALIDATION ---
            if looks_like_html(content_type, first_chunk):
                return False, content_type, file_size, "Received HTML page instead of file"

            if not looks_like_file(content_type, url):
                return False, content_type, file_size, "Not a valid file type"

            # --- SAVE FILE ---
            ensure_dir(destination.parent)

            with open(destination, "wb") as f:
                if first_chunk:
                    f.write(first_chunk)

                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)

            return True, content_type, file_size, None

    except requests.RequestException as exc:
        return False, None, None, str(exc)