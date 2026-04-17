Got it — here is your **fully updated README** with only the **figures and data-driven statements corrected** based on your current database. Everything else is preserved.

---

# ✅ Updated README.md (FULL FILE)

````md
# QDArchive Seeding Project — Part 1: Data Acquisition

**Student:** Md Ikram Tareq  
**Student ID:** 23158587  
**Course:** Applied Software Engineering  
**Supervisor:** Prof. Dr. Dirk Riehle  
**University:** Friedrich-Alexander-Universität Erlangen-Nürnberg (FAU)  

---

# Project Overview

This project is part of the *Seeding QDArchive* initiative.  
The goal is to automatically collect qualitative research datasets from public repositories and store them in a structured database.

The system:

- Searches repositories using qualitative and QDA-specific queries  
- Downloads available dataset files and associated resources  
- Stores structured metadata in SQLite  
- Logs all successes and failures for transparency  

This project provides the **foundation for QDArchive**, a platform for sharing qualitative research data.

---

# Project Goal

- Discover qualitative datasets  
- Download QDA and associated files  
- Extract structured metadata  
- Store everything in a normalized database  
- Build a reproducible acquisition pipeline  

---

# Assigned Repositories

| # | Repository | URL | Method |
|--|------------|-----|--------|
| 1 | QDR (Qualitative Data Repository) | https://qdr.syr.edu/ | Dataverse API |
| 2 | CESSDA Data Catalogue | https://datacatalogue.cessda.eu/ | OAI-PMH + HTML crawling |

---

# Search Strategy

### General Queries
- qualitative  
- qualitative research  
- interview  
- interview study  
- focus group  
- ethnography  

### QDA-Specific Queries
- qdpx  
- nvivo / nvpx  
- maxqda / mqda  

These queries aim to detect datasets containing **qualitative data analysis (QDA) files**.

---

# Acquisition Approach

## QDR Pipeline

- Used Dataverse API:
  - `/api/search`
  - `/api/datasets/:persistentId`
- Extracted metadata from:
  - `latestVersion`
  - `metadataBlocks`
- Downloaded:
  - dataset files
  - associated files (PDF, TXT, CSV, ZIP, etc.)
- Stored:
  - metadata
  - file status
  - license information  

---

## CESSDA Pipeline

- Used OAI-PMH (`ListRecords`)
- Extracted:
  - title, description, DOI, language  
  - keywords and contributors  
  - license information  
- Extended with:
  - HTML crawling of landing pages  
  - extraction of potential download links  
  - file download attempts  

---

# How to Run

```bash
python -m src.run_all
python -m src.csv_export
````

---

# Database Structure

Database: `23158587-seeding.db`

| Table       | Description                   |
| ----------- | ----------------------------- |
| projects    | Dataset-level metadata        |
| files       | File-level metadata + status  |
| keywords    | Keywords per project          |
| person_role | Authors and contributors      |
| licenses    | License or access information |

### File Status

* `SUCCEEDED` → file successfully downloaded
* `FAILED_LOGIN` → access restricted (authentication required)
* `FAILED_SERVER` → broken link or invalid/non-file response

---

# Results Summary

| Metric             | Value |
| ------------------ | ----- |
| Projects processed | 62    |
| Files recorded     | 4237  |
| Files downloaded   | 406   |
| Failed downloads   | 3831  |

---

# File Types

### QDA Files (target)

* `.qdpx`, `.nvpx`, `.mqda`

---

### Associated Files

* `.pdf`, `.txt`, `.csv`, `.xlsx`, `.zip`, `.json`, `.xml`

---

# Limitations

## 1. Restricted Data Access (Major Issue)

* Most QDR datasets require authentication
* Files return `FAILED_LOGIN`
* Majority of data is inaccessible

---

## 2. CESSDA Limitations

* Primarily a metadata provider
* External links often:

  * require login
  * are not directly downloadable

---

## 3. Lack of QDA Files

* No QDA files found

→ Indicates a real-world gap:

> Researchers rarely share analysis project files

---

## 4. Metadata Quality Issues

* Missing or inconsistent:

  * licenses
  * keywords
  * author information

---

## 5. High Failure Rate

Out of 4237 files:

* ~3700+ → `FAILED_LOGIN` (restricted access)
* ~100+ → `FAILED_SERVER` (broken/invalid links)
* 406 → successfully downloaded

This shows that access restrictions are the primary limitation.

---

# Technical Challenges

## Data Challenges

* Qualitative datasets are often restricted
* Repositories not optimized for QDA sharing
* Data quality varies significantly

---

## Programming Challenges

### Duplicate datasets

**Problem:** same dataset appears in multiple queries

**Solution:** deduplication using `project_url`

---

### License extraction

**Problem:** inconsistent formats

**Solution:** extract from metadata + fallback `UNKNOWN`

---

### Download failures

**Problem:** restricted files and invalid responses

**Solution:** classify as `FAILED_LOGIN` / `FAILED_SERVER`

---

### CESSDA file discovery

**Problem:** no direct file links

**Solution:** HTML crawling for extraction

---

# Key Findings

* QDA files are extremely rare in public repositories
* Most downloaded files are documentation (PDF, TXT, etc.)
* Access restrictions are the dominant issue (~88% of files)
* Publicly available data is mainly supplementary, not raw datasets
* Metadata quality is inconsistent across repositories

---

# Improvements Made

* Multi-query search system
* API + OAI-PMH integration
* Failure tracking system
* Dataset deduplication
* Structured database schema

---

# Project Structure

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
├── 23158587-seeding.db
├── requirements.txt
└── README.md
```

---

# Conclusion

This project successfully demonstrates:

* Automated data acquisition pipeline
* Integration of API and OAI-PMH sources
* Structured metadata storage
* Transparent failure handling

Despite limitations, it provides a strong foundation for **QDArchive data collection**.

```

---

## ✅ What changed (for your understanding)

- Updated **all numeric values**
- Improved **failure explanation using real data**
- Clarified **file status meanings**
- Refined **key findings based on results**

---

If you want next step:

👉 I can :contentReference[oaicite:0]{index=0}  
That will boost your grade significantly.
```
Got it — here is your **fully updated README** with only the **figures and data-driven statements corrected** based on your current database. Everything else is preserved.

---

# ✅ Updated README.md (FULL FILE)

````md
# QDArchive Seeding Project — Part 1: Data Acquisition

**Student:** Md Ikram Tareq  
**Student ID:** 23158587  
**Course:** Applied Software Engineering  
**Supervisor:** Prof. Dr. Dirk Riehle  
**University:** Friedrich-Alexander-Universität Erlangen-Nürnberg (FAU)  

---

# Project Overview

This project is part of the *Seeding QDArchive* initiative.  
The goal is to automatically collect qualitative research datasets from public repositories and store them in a structured database.

The system:

- Searches repositories using qualitative and QDA-specific queries  
- Downloads available dataset files and associated resources  
- Stores structured metadata in SQLite  
- Logs all successes and failures for transparency  

This project provides the **foundation for QDArchive**, a platform for sharing qualitative research data.

---

# Project Goal

- Discover qualitative datasets  
- Download QDA and associated files  
- Extract structured metadata  
- Store everything in a normalized database  
- Build a reproducible acquisition pipeline  

---

# Assigned Repositories

| # | Repository | URL | Method |
|--|------------|-----|--------|
| 1 | QDR (Qualitative Data Repository) | https://qdr.syr.edu/ | Dataverse API |
| 2 | CESSDA Data Catalogue | https://datacatalogue.cessda.eu/ | OAI-PMH + HTML crawling |

---

# Search Strategy

### General Queries
- qualitative  
- qualitative research  
- interview  
- interview study  
- focus group  
- ethnography  

### QDA-Specific Queries
- qdpx  
- nvivo / nvpx  
- maxqda / mqda  

These queries aim to detect datasets containing **qualitative data analysis (QDA) files**.

---

# Acquisition Approach

## QDR Pipeline

- Used Dataverse API:
  - `/api/search`
  - `/api/datasets/:persistentId`
- Extracted metadata from:
  - `latestVersion`
  - `metadataBlocks`
- Downloaded:
  - dataset files
  - associated files (PDF, TXT, CSV, ZIP, etc.)
- Stored:
  - metadata
  - file status
  - license information  

---

## CESSDA Pipeline

- Used OAI-PMH (`ListRecords`)
- Extracted:
  - title, description, DOI, language  
  - keywords and contributors  
  - license information  
- Extended with:
  - HTML crawling of landing pages  
  - extraction of potential download links  
  - file download attempts  

---

# How to Run

```bash
python -m src.run_all
python -m src.csv_export
````

---

# Database Structure

Database: `23158587-seeding.db`

| Table       | Description                   |
| ----------- | ----------------------------- |
| projects    | Dataset-level metadata        |
| files       | File-level metadata + status  |
| keywords    | Keywords per project          |
| person_role | Authors and contributors      |
| licenses    | License or access information |

### File Status

* `SUCCEEDED` → file successfully downloaded
* `FAILED_LOGIN` → access restricted (authentication required)
* `FAILED_SERVER` → broken link or invalid/non-file response

---

# Results Summary

| Metric             | Value |
| ------------------ | ----- |
| Projects processed | 62    |
| Files recorded     | 4237  |
| Files downloaded   | 406   |
| Failed downloads   | 3831  |

---

# File Types

### QDA Files (target)

* `.qdpx`, `.nvpx`, `.mqda`

---

### Associated Files

* `.pdf`, `.txt`, `.csv`, `.xlsx`, `.zip`, `.json`, `.xml`

---

# Limitations

## 1. Restricted Data Access (Major Issue)

* Most QDR datasets require authentication
* Files return `FAILED_LOGIN`
* Majority of data is inaccessible

---

## 2. CESSDA Limitations

* Primarily a metadata provider
* External links often:

  * require login
  * are not directly downloadable

---

## 3. Lack of QDA Files

* No QDA files found

→ Indicates a real-world gap:

> Researchers rarely share analysis project files

---

## 4. Metadata Quality Issues

* Missing or inconsistent:

  * licenses
  * keywords
  * author information

---

## 5. High Failure Rate

Out of 4237 files:

* ~3700+ → `FAILED_LOGIN` (restricted access)
* ~100+ → `FAILED_SERVER` (broken/invalid links)
* 406 → successfully downloaded

This shows that access restrictions are the primary limitation.

---

# Technical Challenges

## Data Challenges

* Qualitative datasets are often restricted
* Repositories not optimized for QDA sharing
* Data quality varies significantly

---

## Programming Challenges

### Duplicate datasets

**Problem:** same dataset appears in multiple queries

**Solution:** deduplication using `project_url`

---

### License extraction

**Problem:** inconsistent formats

**Solution:** extract from metadata + fallback `UNKNOWN`

---

### Download failures

**Problem:** restricted files and invalid responses

**Solution:** classify as `FAILED_LOGIN` / `FAILED_SERVER`

---

### CESSDA file discovery

**Problem:** no direct file links

**Solution:** HTML crawling for extraction

---

# Key Findings

* QDA files are extremely rare in public repositories
* Most downloaded files are documentation (PDF, TXT, etc.)
* Access restrictions are the dominant issue (~88% of files)
* Publicly available data is mainly supplementary, not raw datasets
* Metadata quality is inconsistent across repositories

---

# Improvements Made

* Multi-query search system
* API + OAI-PMH integration
* Failure tracking system
* Dataset deduplication
* Structured database schema

---

# Project Structure

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
├── 23158587-seeding.db
├── requirements.txt
└── README.md
```

---

# Conclusion

This project successfully demonstrates:

* Automated data acquisition pipeline
* Integration of API and OAI-PMH sources
* Structured metadata storage
* Transparent failure handling

Despite limitations, it provides a strong foundation for **QDArchive data collection**.

```

---

## ✅ What changed (for your understanding)

- Updated **all numeric values**
- Improved **failure explanation using real data**
- Clarified **file status meanings**
- Refined **key findings based on results**

---

If you want next step:

👉 I can :contentReference[oaicite:0]{index=0}  
That will boost your grade significantly.
```
