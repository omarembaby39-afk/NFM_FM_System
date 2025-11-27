import os
import json
from pathlib import Path

# -------------------------------------------------
# Base directory (root of the app)
# -------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent

# -------------------------------------------------
# Settings file (allows overriding local paths)
# -------------------------------------------------
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")

# Default OneDrive folder for exports, invoices & backups
DEFAULT_LOCAL_DATA_DIR = r"C:\Users\acer\OneDrive\NilepsHR_Database\RO-UMQASR"

# Load override from settings.json if exists
LOCAL_DATA_DIR = DEFAULT_LOCAL_DATA_DIR
if os.path.exists(SETTINGS_FILE):
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        override_path = data.get("local_data_dir")
        if override_path:
            LOCAL_DATA_DIR = override_path
    except Exception:
        pass  # If file corrupted → ignore and use default

# Make sure directory exists
os.makedirs(LOCAL_DATA_DIR, exist_ok=True)

# -------------------------------------------------
# Assets folder (logos, templates)
# -------------------------------------------------
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
os.makedirs(ASSETS_DIR, exist_ok=True)

# Default logo paths (optional, they can be replaced anytime)
NFM_LOGO = os.path.join(ASSETS_DIR, "nfm_logo.png")
CLIENT_LOGO = os.path.join(ASSETS_DIR, "client_logo.png")

# -------------------------------------------------
# Photos folders (LOCAL)
# -------------------------------------------------
PHOTO_DIR = os.path.join(BASE_DIR, "photos")
os.makedirs(PHOTO_DIR, exist_ok=True)

WORKER_PHOTO_DIR = os.path.join(PHOTO_DIR, "workers")
os.makedirs(WORKER_PHOTO_DIR, exist_ok=True)

BUILDING_PHOTO_DIR = os.path.join(PHOTO_DIR, "buildings")
os.makedirs(BUILDING_PHOTO_DIR, exist_ok=True)

WC_PHOTO_DIR = os.path.join(PHOTO_DIR, "wc")
os.makedirs(WC_PHOTO_DIR, exist_ok=True)

FLEET_PHOTO_DIR = os.path.join(PHOTO_DIR, "fleet")
os.makedirs(FLEET_PHOTO_DIR, exist_ok=True)

# -------------------------------------------------
# Invoice PDF storage (inside OneDrive folder)
# -------------------------------------------------
INVOICE_FILES_DIR = os.path.join(LOCAL_DATA_DIR, "invoices")
os.makedirs(INVOICE_FILES_DIR, exist_ok=True)

# -------------------------------------------------
# App Information
# -------------------------------------------------
APP_TITLE = "Nile Facility Management – Um Qasr Welcome Yard"

THEME = {
    "primary": "#2E86C1",
    "secondary": "#1B4F72",
    "accent": "#117A65",
    "sidebar_color": "#D6EAF8",
}

# -------------------------------------------------
# Neon PostgreSQL URL (with fallback to environment variable)
# -------------------------------------------------
NEON_DB_URL = (
    "postgresql://neondb_owner:"
    "npg_C4ghxK1yUcfw@"
    "ep-billowing-fog-agxbr2fc-pooler.c-2.eu-central-1.aws.neon.tech/"
    "neondb?sslmode=require&channel_binding=require"
)

# Allow override from server environment
NEON_DB_URL = os.getenv("NEON_DB_URL", NEON_DB_URL)

# -------------------------------------------------
# Upload limits
# -------------------------------------------------
ALLOWED_PHOTO_TYPES = ["png", "jpg", "jpeg"]
MAX_UPLOAD_MB = 15
