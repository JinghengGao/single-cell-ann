from __future__ import annotations

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]


class Config:
    BASE_DIR = BASE_DIR
    DATA_PATH = Path(os.getenv("SCANN_DATA_PATH", BASE_DIR / "data" / "liver.h5ad"))
    INDEX_DIR = Path(os.getenv("SCANN_INDEX_DIR", BASE_DIR / "indexes"))
    LOG_DIR = Path(os.getenv("SCANN_LOG_DIR", BASE_DIR / "logs"))

    HOST = os.getenv("SCANN_HOST", "127.0.0.1")
    PORT = int(os.getenv("SCANN_PORT", "5000"))
    DEBUG = os.getenv("SCANN_DEBUG", "true").lower() in {"1", "true", "yes"}
    CORS_ORIGINS = os.getenv("SCANN_CORS_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173").split(",")

    DEFAULT_TOP_K = int(os.getenv("SCANN_DEFAULT_TOP_K", "10"))
    MAX_TOP_K = int(os.getenv("SCANN_MAX_TOP_K", "100"))
    DEFAULT_VIS_LIMIT = int(os.getenv("SCANN_DEFAULT_VIS_LIMIT", "5000"))
