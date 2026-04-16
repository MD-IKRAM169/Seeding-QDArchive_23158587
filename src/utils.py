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
        with requests.get(url, stream=True, timeout=timeout) as response:
            if response.status_code == 401 or response.status_code == 403:
                return False, None, None, f"Access denied: HTTP {response.status_code}"

            if response.status_code >= 400:
                return False, None, None, f"HTTP error: {response.status_code}"

            content_type = response.headers.get("Content-Type")
            content_length = response.headers.get("Content-Length")
            file_size = int(content_length) if content_length and content_length.isdigit() else None

            ensure_dir(destination.parent)

            with open(destination, "wb") as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)

            return True, content_type, file_size, None

    except requests.RequestException as exc:
        return False, None, None, str(exc)