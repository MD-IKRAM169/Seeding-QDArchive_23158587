from src.config import QDR_DIR
from src.utils import ensure_dir, slugify, get_extension

ensure_dir(QDR_DIR)

print("QDR folder exists:", QDR_DIR.exists())
print("Slug test:", slugify("My Interview Study: Version 1"))
print("Extension test:", get_extension("project.qdpx"))