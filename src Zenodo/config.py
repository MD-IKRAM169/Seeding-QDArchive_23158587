from pathlib import Path

# Project root = folder that contains "src"
PROJECT_ROOT = Path(__file__).resolve().parent.parent

DOWNLOADS_ROOT = PROJECT_ROOT / "my_downloads"
ZENODO_DOWNLOADS = DOWNLOADS_ROOT / "zenodo"

DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "qda_archive.db"

EXPORTS_DIR = PROJECT_ROOT / "exports"

# QDA file types (extend anytime)
QDA_EXTS = {
    ".qdpx",   # REFI exchange
    ".qpdx",   # sometimes used by tools
    ".nvpx",   # NVivo
    ".nvp",    # NVivo (older)
    ".atlproj",# ATLAS.ti (example)
    ".atlas",  # generic
    ".mx", ".mx20", ".mex",  # MAXQDA-like
}