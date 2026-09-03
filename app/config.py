import os
from pathlib import Path

# Base project directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Storage directory for serving HTML files
DEFAULT_STORAGE_DIR = BASE_DIR / "html_storage"
STORAGE_DIR_STR = os.getenv("HTML_STORAGE_DIR", str(DEFAULT_STORAGE_DIR))
STORAGE_DIR = Path(STORAGE_DIR_STR).resolve()

# App configuration
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "5000"))

# Static and template directories
TEMPLATES_DIR = BASE_DIR / "app" / "templates"
STATIC_DIR = BASE_DIR / "app" / "static"

# Data and database configuration
DATA_DIR = BASE_DIR / "data"
DB_PATH = Path(os.getenv("HTML_DB_PATH", str(DATA_DIR / "users.db"))).resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Ensure storage directory exists
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

