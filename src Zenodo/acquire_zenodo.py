import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Tuple

import requests

from src.config import ZENODO_DOWNLOADS, QDA_EXTS
from src.db import init_db, insert_row

ZENODO_API = "https://zenodo.org/api/records"

def safe_name(s: str) -> str:
    s = s or "untitled"
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in s)[:120]

def sha256_file(path: Path, chunk=1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()

def search_zenodo(query: str, size: int, page: int) -> Dict[str, Any]:
    params = {"q": query, "size": size, "page": page, "sort": "mostrecent"}
    r = requests.get(ZENODO_API, params=params, timeout=60)
    r.raise_for_status()
    return r.json()

def download_file(url: str, outpath: Path) -> int:
    outpath.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        total = 0
        with outpath.open("wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 256):
                if chunk:
                    f.write(chunk)
                    total += len(chunk)
    return total

def find_qda_files(files: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return file-metadata objects that look like QDA files based on extension."""
    qda = []
    for f in files or []:
        key = (f.get("key") or "").strip()
        ext = Path(key).suffix.lower()
        if ext in QDA_EXTS:
            qda.append(f)
    return qda

def normalize_license(meta: Dict[str, Any]) -> str:
    lic = meta.get("license")
    if isinstance(lic, dict):
        return lic.get("id") or lic.get("title") or ""
    if isinstance(lic, str):
        return lic
    return ""

def acquire(query: str, limit_datasets: int, page_size: int, sleep_s: float) -> None:
    init_db()
    ZENODO_DOWNLOADS.mkdir(parents=True, exist_ok=True)

    collected = 0
    page = 1

    while collected < limit_datasets:
        data = search_zenodo(query=query, size=page_size, page=page)
        hits = data.get("hits", {}).get("hits", [])
        if not hits:
            break

        for rec in hits:
            if collected >= limit_datasets:
                break

            rec_id = str(rec.get("id"))
            meta = rec.get("metadata") or {}
            title = meta.get("title") or "untitled"
            description = meta.get("description") or ""
            doi = meta.get("doi") or rec.get("doi") or ""
            license_id = normalize_license(meta)

            dataset_url = (rec.get("links") or {}).get("html") or ""
            files = rec.get("files") or []

            if not files:
                continue

            qda_files = find_qda_files(files)
            if not qda_files:
                # Professor wants QDA file URL in table v1
                continue

            # Create 1 folder per dataset
            dataset_folder = ZENODO_DOWNLOADS / safe_name(f"{rec_id}-{title}")
            dataset_folder.mkdir(parents=True, exist_ok=True)

            # Save record metadata for traceability
            (dataset_folder / "record.json").write_text(json.dumps(rec, indent=2), encoding="utf-8")

            # Download ALL files for the dataset (QDA + associated)
            for fmeta in files:
                file_url = (fmeta.get("links") or {}).get("self")
                key = fmeta.get("key") or "file.bin"
                local_path = dataset_folder / safe_name(key)

                try:
                    download_file(file_url, local_path)
                except Exception:
                    # skip broken file but keep dataset
                    continue

            # Insert rows ONLY for QDA files (matches "URL of QDA file" requirement)
            # Required columns: url, timestamp, local_dir, local_filename
            ts = datetime.now(timezone.utc).isoformat()

            for qf in qda_files:
                q_url = (qf.get("links") or {}).get("self") or ""
                q_key = qf.get("key") or "qda_file.bin"
                q_local = dataset_folder / safe_name(q_key)

                # q_local should exist if download succeeded; hash only if present
                size_bytes = q_local.stat().st_size if q_local.exists() else None
                sha = sha256_file(q_local) if q_local.exists() else None

                row = {
                    "url": q_url,
                    "timestamp": ts,
                    "local_dir": str(dataset_folder),
                    "local_filename": q_local.name,

                    "repository": "Zenodo",
                    "dataset_url": dataset_url,
                    "dataset_id": rec_id,
                    "title": title,
                    "description": description,
                    "license": license_id,
                    "doi": doi,
                    "file_type": q_local.suffix.lower().lstrip("."),
                    "size_bytes": size_bytes,
                    "sha256": sha,
                    "uploader_name": "",
                    "uploader_email": "",
                }
                insert_row(row)

            collected += 1
            time.sleep(sleep_s)

        page += 1

    print(f"✅ Done. Downloaded {collected} datasets into: {ZENODO_DOWNLOADS}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--query", default='qdpx OR qpdx OR NVivo OR "atlas.ti" OR MAXQDA',
                    help="Zenodo search query")
    ap.add_argument("--limit_datasets", type=int, default=10,
                    help="How many datasets (records) to download (1 folder each)")
    ap.add_argument("--page_size", type=int, default=25)
    ap.add_argument("--sleep", type=float, default=0.2)
    args = ap.parse_args()

    acquire(
        query=args.query,
        limit_datasets=args.limit_datasets,
        page_size=args.page_size,
        sleep_s=args.sleep,
    )

if __name__ == "__main__":
    main()