from pathlib import Path

# Project root folder
BASE_DIR = Path(__file__).resolve().parent.parent

# Database file must be in the repository root
DB_PATH = BASE_DIR / "23158587-seeding.db"

# Download folders
DOWNLOADS_DIR = BASE_DIR / "my_downloads"
QDR_DIR = DOWNLOADS_DIR / "qdr"
CESSDA_DIR = DOWNLOADS_DIR / "cessda"

# Repository configuration
REPOSITORIES = {
    "qdr": {
        "id": 1,
        "name": "QDR",
        "url": "https://qdr.syr.edu/",
        "download_folder": QDR_DIR,
    },
    "cessda": {
        "id": 2,
        "name": "CESSDA",
        "url": "https://www.cessda.eu/Tools/Data-Catalogue",
        "download_folder": CESSDA_DIR,
    },
}

# Broader query list based on your project notes and uploaded file-extension sheets
SEARCH_QUERIES = [
    # broad qualitative search terms
    "qualitative",
    "qualitative research",
    "qualitative data",
    "interview",
    "interview study",
    "focus group",
    "ethnography",

    # REFI / general QDA
    "qdpx",
    "qdc",

    # QDA Miner
    "qda miner",
    "ppj",
    "ppx",
    "qlt",

    # NVivo
    "nvivo",
    "nvp",
    "nvpx",

    # MAXQDA
    "maxqda",
    "mqda",
    "mqbac",
    "mqtc",
    "mqex",
    "mqmtr",
    "mx24",
    "mx24bac",
    "mc24",
    "mex24",
    "mx22",
    "mx20",
    "mx18",
    "mx12",
    "mx11",
    "mx5",
    "mx4",
    "mx3",
    "mx2",
    "m2k",
    "loa",
    "sea",
    "mtr",
    "mod",
    "mex22",
]

# Known QDA-related file extensions from your uploaded sheets
QDA_EXTENSIONS = {
    # REFI / QDAcity
    ".qdpx", ".qdc",

    # QDA Miner
    ".ppj", ".ppx", ".qlt",

    # NVivo
    ".nvp", ".nvpx",

    # MAXQDA
    ".mqda", ".mqbac", ".mqtc", ".mqex", ".mqmtr",
    ".mx24", ".mx24bac", ".mc24", ".mex24",
    ".mx22", ".mx20", ".mx18", ".mx12", ".mx11",
    ".mx5", ".mx4", ".mx3", ".mx2", ".m2k",
    ".loa", ".sea", ".mtr", ".mod", ".mex22",

    # Other from your sheet
    ".f4p",
}

# Primary qualitative data / supporting file extensions
PRIMARY_DATA_EXTENSIONS = {
    ".pdf", ".txt", ".rtf", ".doc", ".docx", ".odt",
    ".csv", ".xlsx", ".xls",
    ".jpg", ".jpeg", ".png", ".gif", ".tif", ".tiff",
    ".mp3", ".wav", ".m4a", ".mp4", ".avi", ".mov",
    ".xml", ".json", ".zip"
}

# Download result values based on your uploaded schema screenshot
DOWNLOAD_RESULTS = {
    "SUCCEEDED",
    "FAILED_SERVER",
    "FAILED_LOGIN",
    "FAILED_TOO_LARGE",
}

# Person role values based on your uploaded schema screenshot
PERSON_ROLES = {
    "UPLOADER",
    "AUTHOR",
    "OWNER",
    "OTHER",
    "UNKNOWN",
}