from __future__ import annotations

import os
from pathlib import Path

def _load_env_file_fallback(env_path: Path, *, override: bool) -> None:
    """python-dotenv 不可用时的最小 .env 解析器。"""
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        if not override and key in os.environ:
            continue
        os.environ[key] = value.strip()


try:
    from dotenv import load_dotenv

    _ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
    if _ENV_PATH.exists():
        load_dotenv(_ENV_PATH, override=True)
except ImportError:  # pragma: no cover — python-dotenv 未安装时回退到系统环境变量
    _ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
    if _ENV_PATH.exists():
        _load_env_file_fallback(_ENV_PATH, override=True)


BASE_DIR = Path(__file__).resolve().parents[1]


class Config:
    # 路径配置统一从 .env 覆盖，便于演示时切换数据集、索引和运行日志目录。
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
    DEBUG = os.getenv("SCANN_DEBUG", "false").lower() in {"1", "true", "yes"}
    # 开发环境下 Vite 端口可能自动递增，因此默认允许 5173-5176。
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

    # LLM 配置同时兼容云端 OpenAI-compatible 服务和本地 Ollama 服务。
    LLM_PROVIDER = os.getenv("SCANN_LLM_PROVIDER", "siliconflow")
    LLM_API_URL = os.getenv("SCANN_LLM_API_URL", "")
    LLM_API_KEY = os.getenv("SCANN_LLM_API_KEY", "")
    LLM_MODEL = os.getenv("SCANN_LLM_MODEL", "")
    LLM_TIMEOUT_SECONDS = int(os.getenv("SCANN_LLM_TIMEOUT_SECONDS", "60"))
    LLM_MAX_TOKENS = int(os.getenv("SCANN_LLM_MAX_TOKENS", "512"))
    LLM_TEMPERATURE = float(os.getenv("SCANN_LLM_TEMPERATURE", "0.2"))
    LLM_ENABLE_THINKING = os.getenv("SCANN_LLM_ENABLE_THINKING", "false").lower() in {"1", "true", "yes"}
    LLM_MAX_HITS_FOR_PROMPT = int(os.getenv("SCANN_LLM_MAX_HITS_FOR_PROMPT", "5"))
    LLM_RETRY_COUNT = int(os.getenv("SCANN_LLM_RETRY_COUNT", "0"))
    LLM_RETRY_BACKOFF_SECONDS = float(os.getenv("SCANN_LLM_RETRY_BACKOFF_SECONDS", "1"))
    LLM_CACHE_TTL_SECONDS = int(os.getenv("SCANN_LLM_CACHE_TTL_SECONDS", "300"))
    LLM_CACHE_MAX_ENTRIES = int(os.getenv("SCANN_LLM_CACHE_MAX_ENTRIES", "128"))
