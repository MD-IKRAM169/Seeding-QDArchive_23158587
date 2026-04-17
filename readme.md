# QDArchive Seeding Project — Part 1: Data Acquisition

## Author

* **Name:** Md Ikram Tareq
* **Student ID:** 23158587
* **University:** Friedrich-Alexander-Universität Erlangen-Nürnberg (FAU)
* **Supervisor:** Prof. Dr. Dirk Riehle

---

## Project Overview

This project is part of the **Seeding QDArchive initiative**, aiming to build an automated pipeline for collecting qualitative research datasets from public repositories.

The system:

* Searches repositories using qualitative and QDA-specific queries
* Downloads publicly available dataset files
* Extracts structured metadata
* Stores all data in a normalized SQLite database
* Logs all download outcomes (success + failure)

This serves as a **foundation for QDArchive**, a future platform for qualitative data sharing.

---

## Data Sources

| # | Repository                        | URL                              | Method                  |
| - | --------------------------------- | -------------------------------- | ----------------------- |
| 1 | QDR (Qualitative Data Repository) | https://qdr.syr.edu/             | Dataverse API           |
| 2 | CESSDA Data Catalogue             | https://datacatalogue.cessda.eu/ | OAI-PMH + HTML crawling |

---

## Search Strategy

### General Queries

* qualitative
* qualitative research
* interview
* focus group
* ethnography

### QDA-Specific Queries

* qdpx
* nvivo / nvpx
* maxqda / mqda

These queries aim to identify datasets containing **qualitative data analysis (QDA) files**.

---

## Pipeline Architecture

### QDR Pipeline

* Uses Dataverse API (`/search`, `/datasets`)
* Extracts metadata from `latestVersion`
* Downloads:

  * dataset files
  * documentation (PDF, TXT, CSV, ZIP, etc.)

### CESSDA Pipeline

* Uses OAI-PMH (`ListRecords`)
* Extracts metadata (title, DOI, contributors, etc.)
* Enhances with:

  * HTML crawling
  * link extraction
  * download attempts from publisher pages

---

## Database Schema

SQLite Database: `23158587-seeding.db`

| Table         | Description                           |
| ------------- | ------------------------------------- |
| `projects`    | Dataset-level metadata                |
| `files`       | File-level metadata + download status |
| `keywords`    | Project keywords                      |
| `person_role` | Authors and contributors              |
| `licenses`    | License/access information            |

### File Status

* `SUCCEEDED` → File successfully downloaded
* `FAILED_LOGIN` → Access restricted (authentication required)
* `FAILED_SERVER` → Broken link or invalid response

---

## Results

| Metric                 | Value |
| ---------------------- | ----- |
| **Projects processed** | 62    |
| **Files recorded**     | 4,237 |
| **Files downloaded**   | 406   |
| **Failed downloads**   | 3,831 |

---

## File Types

### Target QDA Files

* `.qdpx`, `.nvpx`

### Downloaded Data Types

* `.pdf`, `.txt`, `.csv`, `.xlsx`, `.zip`, `.json`, `.xml`

---

## Key Limitations

### 1. Restricted Data Access

* Majority of files require authentication
* ~3700+ files marked as `FAILED_LOGIN`

### 2. CESSDA Constraints

* Mainly provides metadata
* External links often:

  * require login
  * are not directly downloadable

### 3. Lack of QDA Files

* No QDA project files found
* Indicates limited sharing of analysis-level data

### 4. High Failure Rate

* Only **406 / 4237 files (~9.6%)** successfully downloaded
* Most failures due to access restrictions

---

## Key Findings

* QDA files are **extremely rare** in public repositories
* Most accessible files are **documentation (PDF, text, metadata)**
* **Access restriction is the dominant barrier (~88%)**
* Public datasets rarely include analysis-ready formats
* Metadata quality varies significantly

---

## Technical Challenges & Solutions

| Challenge                   | Solution                              |
| --------------------------- | ------------------------------------- |
| Duplicate datasets          | Deduplication using `project_url`     |
| Inconsistent licenses       | Metadata parsing + fallback           |
| Restricted files            | Classified as `FAILED_LOGIN`          |
| Missing file links (CESSDA) | HTML crawling + link extraction       |
| Invalid downloads           | Content validation (avoid HTML pages) |

---

## How to Run

```bash
# Run full pipeline
python -m src.run_all

# Export results to CSV
python -m src.csv_export
```

---

## Project Structure

```
QDArchive/
│
├── src/
│   ├── acquire_qdr.py
│   ├── acquire_cessda.py
│   ├── db.py
│   ├── config.py
│   ├── utils.py
│   ├── run_all.py
│   └── csv_export.py
│
├── my_downloads/
│   ├── qdr/
│   └── cessda/
│
├── exports/
├── 23158587-seeding.db
├── requirements.txt
└── README.md
```
## 📦 Data Availability

### SQLite Database
- `23158587-seeding.db` (included in repository root)

---

### Downloaded Files

The downloaded dataset files are also included in this repository under:

- `my_downloads/`

---

### External Access (FAUbox)

For submission purposes, the downloaded dataset files are additionally provided via FAUbox:

- FAUbox: https://faubox.rrze.uni-erlangen.de/getlink/fi8WYA43xBQzfHh3tJ5D6v/my_downloads

---

## Conclusion

This project demonstrates:

* A working **data acquisition pipeline** for qualitative research
* Integration of **API + OAI-PMH sources**
* Structured storage of metadata and files
* Transparent handling of access limitations

Despite constraints, it provides a **solid foundation for building QDArchive**.
