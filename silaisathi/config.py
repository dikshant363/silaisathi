"""Application configuration and environment settings for SilaiSathi.

Strictly local-first: loopback-only bindings, local SQLite persistence,
local Ollama inference, and no external tracking or telemetry.
"""

from __future__ import annotations

import os
from pathlib import Path

# Base Paths
USER_HOME = Path.home()
DEFAULT_DATA_DIR = USER_HOME / ".silaisathi"
DEFAULT_DB_PATH = DEFAULT_DATA_DIR / "silaisathi.db"
DEFAULT_BACKUP_DIR = DEFAULT_DATA_DIR / "backups"

# Resolve configured database path
DB_PATH = Path(os.getenv("SILAISATHI_DB_PATH", str(DEFAULT_DB_PATH))).expanduser().resolve()
BACKUP_DIR = (
    Path(os.getenv("SILAISATHI_BACKUP_DIR", str(DEFAULT_BACKUP_DIR))).expanduser().resolve()
)

# Ollama Local Inference Settings (strictly loopback)
OLLAMA_HOST = os.getenv("SILAISATHI_OLLAMA_HOST", "http://127.0.0.1:11434")
DEFAULT_MODEL = os.getenv("SILAISATHI_MODEL", "qwen3.5:4b")
FALLBACK_MODELS = ["qwen3.5:4b", "gemma4:e2b", "llama3.2:3b", "mistral:7b"]
INFERENCE_TIMEOUT_SECONDS = int(os.getenv("SILAISATHI_TIMEOUT", "60"))

# Deployment & Environment Settings
IS_CLOUD_DEPLOYMENT = os.getenv("SILAISATHI_CLOUD_DEPLOYMENT", "0").lower() in (
    "1",
    "true",
    "yes",
)
DEMO_MODE = os.getenv("SILAISATHI_DEMO_MODE", "1").lower() in ("1", "true", "yes")

# Provider Settings
DEFAULT_PROVIDER = os.getenv(
    "SILAISATHI_AI_PROVIDER",
    "gemma"
    if (IS_CLOUD_DEPLOYMENT and (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")))
    else "ollama",
)
GEMMA_DEFAULT_MODEL = os.getenv("SILAISATHI_GEMMA_MODEL", "gemma-4-26b-a4b-it")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
GEMMA_API_BASE = os.getenv(
    "SILAISATHI_GEMMA_API_BASE", "https://generativelanguage.googleapis.com/v1beta"
)

# Security Limits
MAX_INPUT_LENGTH = 2000  # Characters for customer request text
MAX_CUSTOMER_NAME_LENGTH = 100
MAX_PHONE_LENGTH = 20
MAX_SEARCH_RESULTS = 100

# Currency and Units
CURRENCY_CODE = "INR"
CURRENCY_SYMBOL = "₹"
DEFAULT_MEASUREMENT_UNIT = "in"  # inches (most common in Indian tailoring)

# Default Shop Profile (customizable in UI/Config)
DEFAULT_SHOP_NAME = os.getenv("SILAISATHI_SHOP_NAME", "SilaiSathi Boutique")
DEFAULT_SHOP_PHONE = os.getenv("SILAISATHI_SHOP_PHONE", "+91 98765 43210")
DEFAULT_SHOP_TAGLINE = "Custom Tailoring & Boutique Specialists"

# Standard Indian Tailoring Garment Types
GARMENT_TYPES = [
    "Kurti",
    "Blouse",
    "Salwar Suit",
    "Pant / Trouser",
    "Shirt",
    "Lehenga",
    "Anarkali",
    "Plazo Suit",
    "Sherwani",
    "Coat / Blazer",
    "Other",
]

# Standard Measurement Categories
COMMON_MEASUREMENTS = [
    ("length", "Length (लंबाई)"),
    ("chest", "Chest / Bust (सीना)"),
    ("waist", "Waist (कमर)"),
    ("hips", "Hips (हिप)"),
    ("shoulder", "Shoulder (तीरा)"),
    ("sleeves", "Sleeves (आस्तीन)"),
    ("collar", "Collar / Neck (गला)"),
    ("armhole", "Armhole (मुड्ढा)"),
    ("front_neck", "Front Neck Depth (आगे का गला)"),
    ("back_neck", "Back Neck Depth (पीछे का गला)"),
    ("inseam", "Inseam (अंदरूनी लंबाई)"),
    ("outseam", "Outseam (बाहरी लंबाई)"),
    ("bottom_opening", "Bottom / Mohri (मोहरी)"),
    ("thigh", "Thigh (जांघ)"),
]

# Standard Popular Measurement Keys (Top measurements for rapid workshop entry)
POPULAR_MEASUREMENTS: list[str] = [
    "length",
    "chest",
    "waist",
    "hips",
    "shoulder",
    "sleeves",
    "collar",
    "armhole",
]


def ensure_data_directories() -> None:
    """Ensure data and backup directories exist."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
