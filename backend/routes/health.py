from __future__ import annotations

from flask import Blueprint, current_app, jsonify

from backend.faiss_runtime import inspect_faiss_runtime


health_bp = Blueprint("health", __name__)


@health_bp.get("/health")
def health():
    runtime = inspect_faiss_runtime()
    data_path = current_app.config["DATA_PATH"]
    base_dir = current_app.config["BASE_DIR"]
    try:
        display_data_path = data_path.relative_to(base_dir).as_posix()
    except ValueError:
        display_data_path = str(data_path)
    return jsonify(
        {
            "status": "ok",
            "data_path": display_data_path,
            "data_exists": data_path.exists(),
            "llm": {
                "provider": current_app.config.get("LLM_PROVIDER"),
                "api_url": current_app.config.get("LLM_API_URL"),
                "model": current_app.config.get("LLM_MODEL"),
                "api_key_configured": bool(str(current_app.config.get("LLM_API_KEY") or "").strip()),
            },
            "faiss": {
                "available": runtime.available,
                "mode": runtime.mode,
                "version": runtime.version,
                "gpu_count": runtime.gpu_count,
                "error": runtime.error,
            },
        }
    )
