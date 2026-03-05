# Seeding QDArchive – Part 1 (Acquisition)

## Project Overview
This project implements the **data acquisition pipeline** for the QDArchive system.  
The objective of this phase is to automatically download qualitative research datasets from the **Zenodo repository**, organize them into a structured local archive, and store required metadata in an **SQLite database**.

The pipeline demonstrates how qualitative research datasets can be systematically collected and prepared for future classification and analysis.

## Main Features
- Automated dataset acquisition from **Zenodo**
- Each dataset stored in a **separate folder**
- Metadata stored in an **SQLite database**
- Reproducible acquisition pipeline
- Organized project structure for scalability
  
## Project Structure
Qda Project_Ikram
│
├── src/
│ ├── acquire_zenodo.py # Zenodo acquisition script
│ ├── db.py # SQLite database schema
│ ├── config.py # Configuration settings
│ └── csv_export.py # Metadata export utility (optional)
│
├── my_downloads/
│ └── zenodo/
│ ├── <dataset folders> # One folder per dataset
│
├── data/
│ └── qda_archive.db # SQLite metadata database
│
├── requirements.txt
└── README.md

## Acquisition Output Format

Metadata is stored in an SQLite database:


The database table **qda_files** contains the required Phase-1 metadata fields:

| Column | Description |
|--------|------------|
| url | URL of the downloaded QDA file |
| timestamp | Download timestamp |
| local_dir | Local directory containing the dataset |
| local_filename | Name of downloaded file |

These fields follow the required **Output Format v1** for the acquisition stage.

## Downloaded Datasets

The acquisition pipeline was executed successfully and downloaded:

### **10 datasets from Zenodo**

However, due to **GitHub file size limitations**, only:

### **7 datasets are included in this repository**

Some datasets contained very large files that exceeded GitHub’s upload limits.  
The full set of datasets can be reproduced locally by re-running the acquisition script.

This ensures the repository remains lightweight while preserving reproducibility.


## How to Run the Acquisition Pipeline

### 1️⃣ Install dependencies
pip install -r requirements.txt

### 2️⃣ Download datasets
python -m src.acquire_zenodo --limit_datasets 10

This command will:

1. Query Zenodo records
2. Download dataset files
3. Create one folder per dataset
4. Store metadata in SQLite
   
Downloaded files are stored in:
my_downloads/zenodo/

## Reproducibility

The entire acquisition process is reproducible.  
Running the script again will rebuild the local archive and metadata database.

## Technologies Used
- Python
- Zenodo REST API
- SQLite
- Git & GitHub

## Author
Md Ikram Tareq
QDArchive Project – Phase 1: Acquisition
