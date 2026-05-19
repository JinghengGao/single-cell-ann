from __future__ import annotations

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]


class Config:
    BASE_DIR = BASE_DIR
    DATA_DIR = Path(os.getenv("SCANN_DATA_DIR", BASE_DIR / "data"))
    DATA_PATH = Path(os.getenv("SCANN_DATA_PATH", BASE_DIR / "data" / "liver.h5ad"))
    DATASET_LIBRARY_DIR = Path(os.getenv("SCANN_DATASET_LIBRARY_DIR", BASE_DIR / "data" / "datasets"))
    UPLOAD_DIR = Path(os.getenv("SCANN_UPLOAD_DIR", BASE_DIR / "data" / "uploads"))
    DATASET_REGISTRY_PATH = Path(os.getenv("SCANN_DATASET_REGISTRY_PATH", BASE_DIR / "data" / "registry.json"))
    INDEX_DIR = Path(os.getenv("SCANN_INDEX_DIR", BASE_DIR / "indexes"))
    LOG_DIR = Path(os.getenv("SCANN_LOG_DIR", BASE_DIR / "logs"))
    RUNTIME_DIR = Path(os.getenv("SCANN_RUNTIME_DIR", BASE_DIR / "runtime"))
    USERS_PATH = Path(os.getenv("SCANN_USERS_PATH", RUNTIME_DIR / "users.json"))

    HOST = os.getenv("SCANN_HOST", "127.0.0.1")
    PORT = int(os.getenv("SCANN_PORT", "5000"))
    DEBUG = os.getenv("SCANN_DEBUG", "true").lower() in {"1", "true", "yes"}
    DEFAULT_CORS_ORIGINS = ",".join(
        [
            "http://127.0.0.1:5173",
            "http://127.0.0.1:5174",
            "http://127.0.0.1:5175",
            "http://127.0.0.1:5176",
            "http://localhost:5173",
            "http://localhost:5174",
            "http://localhost:5175",
            "http://localhost:5176",
        ]
    )
    CORS_ORIGINS = os.getenv("SCANN_CORS_ORIGINS", DEFAULT_CORS_ORIGINS).split(",")

    DEFAULT_TOP_K = int(os.getenv("SCANN_DEFAULT_TOP_K", "10"))
    MAX_TOP_K = int(os.getenv("SCANN_MAX_TOP_K", "100"))
    DEFAULT_VIS_LIMIT = int(os.getenv("SCANN_DEFAULT_VIS_LIMIT", "5000"))
    FAISS_NLIST = int(os.getenv("SCANN_FAISS_NLIST", "256"))
    FAISS_NPROBE = int(os.getenv("SCANN_FAISS_NPROBE", "16"))
