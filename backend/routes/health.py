from __future__ import annotations

from flask import Blueprint, current_app, jsonify

from backend.faiss_runtime import inspect_faiss_runtime


health_bp = Blueprint("health", __name__)


@health_bp.get("/health")
def health():
    runtime = inspect_faiss_runtime()
    data_path = current_app.config["DATA_PATH"]
    return jsonify(
        {
            "status": "ok",
            "data_path": str(data_path),
            "data_exists": data_path.exists(),
            "faiss": {
                "available": runtime.available,
                "mode": runtime.mode,
                "version": runtime.version,
                "gpu_count": runtime.gpu_count,
                "error": runtime.error,
            },
        }
    )
