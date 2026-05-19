from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from backend.routes.permissions import require_roles
from backend.services.index_service import index_service


index_bp = Blueprint("index", __name__)


@index_bp.post("/build")
@require_roles("researcher", "data_manager", "admin")
def build_index():
    payload = request.get_json(silent=True) or {}
    nlist = int(payload.get("nlist") or current_app.config["FAISS_NLIST"])
    nprobe = int(payload.get("nprobe") or current_app.config["FAISS_NPROBE"])
    dataset_ids = payload.get("dataset_ids") or []
    if not isinstance(dataset_ids, list):
        return jsonify({"error": "invalid_request", "message": "dataset_ids must be a list"}), 400
    build_mode = str(payload.get("mode") or "combined")
    try:
        summary = index_service.build_ivf_flat(
            current_app.config["INDEX_DIR"],
            nlist=nlist,
            nprobe=nprobe,
            dataset_ids=[str(item) for item in dataset_ids],
            build_mode=build_mode,
            registry_path=current_app.config["DATASET_REGISTRY_PATH"],
        )
        return jsonify(summary)
    except ValueError as exc:
        return jsonify({"error": "invalid_index_request", "message": str(exc), **index_service.status()}), 400
    except RuntimeError as exc:
        return jsonify({"error": "index_build_failed", "message": str(exc), **index_service.status()}), 503
    except KeyError as exc:
        return jsonify({"error": "unknown_dataset", "message": str(exc), **index_service.status()}), 404


@index_bp.get("/status")
def index_status():
    return jsonify(index_service.status())


@index_bp.post("/switch")
@require_roles("researcher", "data_manager", "admin")
def switch_index():
    payload = request.get_json(silent=True) or {}
    index_id = str(payload.get("index_id") or "").strip()
    if not index_id:
        return jsonify({"error": "invalid_request", "message": "index_id is required"}), 400
    try:
        return jsonify(index_service.switch_index(index_id))
    except KeyError as exc:
        return jsonify({"error": "unknown_index", "message": str(exc)}), 404
