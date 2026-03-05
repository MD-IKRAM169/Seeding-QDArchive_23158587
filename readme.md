# Seeding QDArchive – Part 1 (Acquisition)

This project downloads QDA datasets from Zenodo into a local folder structure and stores required metadata in an SQLite database.

## Output Format v1 (required columns)
SQLite table `qda_files` contains at least:
- url (URL of QDA file)
- timestamp (last download timestamp)
- local_dir (name of local directory)
- local_filename (name of local downloaded QDA file)

## Run

### 1) Install
pip install -r requirements.txt

### 2) Download 10 datasets (1 folder per dataset)
python -m src.acquire_zenodo --limit_datasets 10

Downloads go to:
my_downloads/zenodo/<record_id>-<title>/

Database:
data/qda_archive.db

### 3) Export CSV (optional)
python -m src.export_csv