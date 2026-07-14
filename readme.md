# QDArchive Seeding Project

## Author

* **Name:** Md Ikram Tareq
* **Student ID:** 23158587
* **University:** Friedrich-Alexander-Universität Erlangen-Nürnberg (FAU)
* **Supervisor:** Prof. Dr. Dirk Riehle

---

## Full Project Overview

This project implements a complete automated workflow for acquiring, organizing, classifying, and reporting qualitative research datasets as part of the Seeding QDArchive project.

The work is divided into two main parts:

**Part 1** — **Data Acquisition** focuses on automatically collecting project metadata and file information from the two assigned repositories: **the Qualitative Data Repository (QDR / Syracuse)** and the **CESSDA** Data Catalogue. The acquisition pipeline searches for qualitative and QDA-related projects, downloads publicly accessible files when available, records restricted or failed download attempts, extracts metadata such as titles, descriptions, keywords, people, roles, and license information, and stores the collected results in a structured SQLite database.

**Part 2** — **Classification** extends the acquired database by classifying every project into one of four project types: QDA_PROJECT, QD_PROJECT, OTHER_PROJECT, or NOT_A_PROJECT. Relevant QDA_PROJECT and QD_PROJECT records are then classified according to ISIC Rev. 5 at the division level using project metadata, keywords, file names, and available extractable file content. Primary data files are also classified individually when direct content is available, while files without sufficient independent content use a transparent project-class fallback.

The final workflow produces a complete set of outputs, including the classification SQLite database, an XLSX results file, repository- and project-type-specific statistics, vector-based classification histograms, ranked top-class tables, and a PDF report.

Overall, the project demonstrates an end-to-end pipeline covering **automated data acquisition, database construction, QDA project detection, project-type classification, ISIC Rev. 5 categorization, primary-file classification, validation, statistical analysis, and final result reporting.**


# Part1: Data Acquisition

This is part of the **Seeding QDArchive initiative**, aiming to build an automated pipeline for collecting qualitative research datasets from public repositories.

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
* Downloads dataset files and documentation

### CESSDA Pipeline

* Uses OAI-PMH (`ListRecords`)
* Extracts metadata (title, DOI, contributors, etc.)
* Enhances with HTML crawling and link extraction
* Attempts downloads from publisher pages

---

## Database Schema

SQLite Database: `23158587-seeding.db`

| Table         | Description                           |
| ------------- | ------------------------------------- |
| `projects`    | Dataset-level metadata                |
| `files`       | File-level metadata + download status |
| `keywords`    | Project keywords                      |
| `person_role` | Authors and contributors              |
| `licenses`    | License information                   |

### File Status

* `SUCCEEDED` → File successfully downloaded
* `FAILED_LOGIN_REQUIRED` → Access restricted (authentication required)
* `FAILED_SERVER_UNRESPONSIVE` → Broken link or server issue
* `FAILED_TOO_LARGE` → File too large to download

---

## Results

| Metric                 | Value |
| ---------------------- | ----- |
| **Projects processed** | 62    |
| **Files recorded**     | 4,087 |
| **Keywords extracted** | 352   |
| **Persons recorded**   | 156   |
| **Licenses recorded**  | 62    |

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
* Large portion marked as `FAILED_LOGIN_REQUIRED`

### 2. CESSDA Constraints

* Mainly provides metadata
* External links often require login or are not directly downloadable

### 3. Lack of QDA Files
* Indicates limited sharing of analysis-level data

### 4. High Failure Rate

* Only a small percentage of files successfully downloaded
* Most failures due to access restrictions

---

## Key Findings

* QDA files are **extremely rare** in public repositories
* Most accessible files are **documentation (PDF, text, metadata)**
* **Access restriction is the dominant barrier**
* Public datasets rarely include analysis-ready formats
* Metadata quality varies significantly

---

## Technical Challenges & Solutions

| Challenge                   | Solution                              |
| --------------------------- | ------------------------------------- |
| Duplicate datasets          | Deduplication using `project_url`     |
| Inconsistent licenses       | License normalization                 |
| Restricted files            | Classified as `FAILED_LOGIN_REQUIRED` |
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
├── validator/
├── schema-definition/
├── submission_precheck.py
├── check_submission.py
├── 23158587-seeding.db
├── validation_result.png
├── README.md
└── requirements.txt
```

---

## Data Availability

### SQLite Database

* `23158587-seeding.db` (included in repository root)

---

### Downloaded Files

The downloaded dataset files are **not stored in the repository** due to size constraints.

---

### External Access (FAUbox)

The downloaded dataset files are available here:

* FAUbox: https://faubox.rrze.uni-erlangen.de/getlink/fi8WYA43xBQzfHh3tJ5D6v/my_downloads

---

## ✅ SQ26 Validation Result

The SQLite database was validated using the official SQ26 submission validator.

**Command used:**

```bash
python check_submission.py --strict 23158587-seeding.db
```

**Validation Output:**

![Validation Result](./validation_result.png)

**Summary:**

* ✔ 10 checks passed
* ✔ 0 warnings
* ✔ 0 errors

This confirms that the database fully complies with the required SQ26 schema and validation rules.

---

# QDArchive Seeding Project — Part 2: Classification
## Classification Database

Part 2 uses a separate SQLite database: 23158587-sq26-classification.db

The classification database extends the acquired Part 1 data with classification information.

Important Part 2 fields include:
```
projects.type
projects.class
files.class
```

# Step 1 — Project Type Classification
Every project is assigned one of four project types:

```
QDA_PROJECT
QD_PROJECT
OTHER_PROJECT
NOT_A_PROJECT
```

The classification hierarchy is:
```
Known QDA file exists
        ↓
QDA_PROJECT

Otherwise, primary qualitative data exists
        ↓
QD_PROJECT

Otherwise, another valid project data file exists
        ↓
OTHER_PROJECT

Otherwise
        ↓
NOT_A_PROJECT
```
# Project Type Results
# Repository 1 — QDR
| Project Type  | Count |
| ------------- | ----: |
| `QDA_PROJECT` |     2 |
| `QD_PROJECT`  |    14 |

# Repository 2 — CESSDA
| Project Type    | Count |
| --------------- | ----: |
| `QD_PROJECT`    |    16 |
| `OTHER_PROJECT` |    21 |
| `NOT_A_PROJECT` |     9 |

Total: 62 projects classified by PROJECT_TYPE

# ISIC Rev. 5 Classification
## Taxonomy
The project classifier uses: ISIC Rev. 5 at the division level.

A total of: 87 ISIC Rev. 5 divisions were imported from the professor-provided ISIC workbook.

# Classification Input
For every QDA_PROJECT and QD_PROJECT, classification input is prepared from:
```
project title;
project description;
keywords;
selected useful primary file names;
extractable content from successfully downloaded primary files.
```

The prepared input is stored in the classification database.

Relevant projects classified: 32

Breakdown:
| Repository | Project Type  | Projects |
| ---------- | ------------- | -------: |
| QDR        | `QDA_PROJECT` |        2 |
| QDR        | `QD_PROJECT`  |       14 |
| CESSDA     | `QD_PROJECT`  |       16 |

# Project-Level ISIC Classifier
The project-level classifier uses a weighted hybrid TF-IDF approach.

Evidence fields include:
```
title;
description;
keywords;
extracted file content;
useful file names.
```

Generic academic words such as research, study, data, and analysis are reduced as classification evidence so that the classifier focuses more strongly on the actual domain of the project.

The classifier combines:

- word-level TF-IDF similarity;
- character-level TF-IDF similarity.

The final project-level classification result is stored in: projects.class
Detailed results are stored in: project_classifications

# Project Classification Results
All relevant projects received an ISIC Rev. 5 division:
- Classified projects: 32
- Relevant projects without class: 0

Project confidence:
| Confidence | Count |
| ---------- | ----: |
| `MEDIUM`   |    16 |
| `LOW`      |    16 |
No artificial confidence inflation is applied. Ambiguous results remain explicitly marked as low confidence.

## Examples of Frequent Project Classes

Examples of identified ISIC divisions include:

- `R86` — Human health activities
- `O78` — Employment activities
- `Q85` — Education
- `G47` — Retail trade
- `R87` — Residential care activities
- `T94` — Activities of membership organizations

The classification distribution is intentionally diverse and no longer dominated by generic `N72 — Scientific research and development` assignments.

# Primary File Classification
A total of: 3,724 primary file records were processed.
The final strategy distinguishes between two evidence modes.
# 1. Independent Content Classification
When actual extractable file content is available: INDEPENDENT_CONTENT_CLASSIFICATION

The classifier uses:

- actual file content;
- filename;
- project context.

Number of independently classified files: 87

# 2. Project Class Fallback
When actual file content is unavailable: PROJECT_CLASS_FALLBACK.

Number of fallback classifications:3,637

This prevents weak filenames or inaccessible files from receiving misleading independent classifications.

Detailed file classification information is stored in: file_classifications.

The primary class is also stored in: files.class

# File Classification Results
- Primary files processed: 3,724
- Independent content classifications: 87
- Project-class fallbacks: 3,637
- Classified files without files.class: 0

# Classification Validation
- Total projects: 62
- Relevant classified projects: 32
- Project classification rows: 32
- Primary file classifications: 3724
- ISIC Rev. 5 divisions: 87

# Required Classification Deliverables
## SQLite Database: 
23158587-sq26-classification.db

## XLSX Results: 
exports/23158587-sq26-classification-results.xlsx

## PDF Classification Report: 
exports/23158587-sq26-classification-report.pdf

# Important Classification Findings
## QDR — QDA_PROJECT
- 2 projects
- 2 distinct primary ISIC classes

## QDR — QD_PROJECT
- 14 projects
- 12 distinct primary ISIC classes
most frequent class: R86 — Human health activities

## CESSDA — QD_PROJECT
- 16 projects
- 12 distinct primary ISIC classes
most frequent classes include:
- O78 — Employment activities
- Q85 — Education

The results indicate considerable domain diversity across the collected qualitative research projects.

# Project Structure
## Project Structure

```
Seeding-QDArchive_23158587/
|
|── src/
|   |── acquire_qdr.py
|   |── acquire_cessda.py
|   |── run_all.py
|   |── csv_export.py
|   |── prepare_classification_db.py
|   |── add_classification_columns.py
|   |── classify_project_types.py
|   |── import_isic_taxonomy.py
|   |── prepare_classification_input.py
|   |── classify_isic_projects.py
|   |── classify_isic_files.py
|   |── fix_file_classification_schema.py
|   |── validate_classification_results.py
|   |── export_classification_xlsx.py
|   └── generate_classification_report.py
|
|── exports/
|   |── projects.csv
|   |── files.csv
|   |── keywords.csv
|   |── person_role.csv
|   |── licenses.csv
|   |── 23158587-sq26-classification-results.xlsx
|   └── 23158587-sq26-classification-report.pdf
|
|── my_downloads/
|
|── schema-definition/
|── validator/
|
|── 23158587-seeding.db
|── 23158587-sq26-classification.db
|── ISIC5_Exp_Notes_11Mar2024.xlsx
|── README.md
|── requirements.txt
└── LICENSE
```

## Key Findings

- QDA file records were found, including `.qdpx` and `.nvpx`.
- QDA projects are relatively rare compared with the full collected dataset.
- Access restrictions are a major barrier to downloading qualitative research files.
- QDR contains both QDA and qualitative-data projects.
- CESSDA provides useful metadata but many records do not expose directly usable files.
- 32 projects were classified with ISIC Rev. 5 at division level.
- 3,724 primary file records were processed for file-level classification.
- Only 87 files had sufficient extractable content for independent classification.
- 3,637 files use transparent project-class fallback rather than unreliable filename-based guesses.
- The final report includes three repository/project-type distributions.

## Limitations

The main limitations are:

- many QDR files require authentication;
- some CESSDA records are metadata-oriented;
- not every file can be downloaded;
- not every successful download contains extractable text;
- project and file classifications can be uncertain when metadata or content is limited;
- low-confidence classifications should be interpreted cautiously;
- fallback file classifications are inherited from the project and are explicitly marked as such.

---

## Conclusion

This project demonstrates a complete automated workflow for:

- qualitative research data acquisition;
- structured SQLite metadata storage;
- QDA project identification;
- project-type classification;
- ISIC Rev. 5 project classification;
- primary file classification;
- repository-specific statistics;
- XLSX export;
- PDF report generation.