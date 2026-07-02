from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from backend.routes.permissions import require_roles
from backend.services.index_service import index_service


index_bp = Blueprint("index", __name__)


@index_bp.post("/build")
@require_roles("researcher", "data_manager", "admin")
def build_index():
    payload = request.get_json(silent=True) or {}
    index_type = str(payload.get("index_type") or "ivf_flat").lower()
    nlist = int(payload.get("nlist") or current_app.config["FAISS_NLIST"])
    nprobe = int(payload.get("nprobe") or current_app.config["FAISS_NPROBE"])
    metric = str(payload.get("metric") or "l2").lower()
    dataset_ids = payload.get("dataset_ids") or []
    if not isinstance(dataset_ids, list):
        return jsonify({"error": "invalid_request", "message": "dataset_ids must be a list"}), 400
    build_mode = str(payload.get("mode") or "combined")
    try:
        if index_type == "hnsw":
            M = int(payload.get("M") or 32)
            ef_construction = int(payload.get("ef_construction") or 200)
            ef_search = int(payload.get("ef_search") or 64)
            summary = index_service.build_hnsw(
                current_app.config["INDEX_DIR"],
                dataset_ids=[str(item) for item in dataset_ids],
                build_mode=build_mode,
                metric=metric,
                M=M,
                ef_construction=ef_construction,
                ef_search=ef_search,
                registry_path=current_app.config["DATASET_REGISTRY_PATH"],
            )
        else:
            summary = index_service.build_ivf_flat(
                current_app.config["INDEX_DIR"],
                nlist=nlist,
                nprobe=nprobe,
                dataset_ids=[str(item) for item in dataset_ids],
                build_mode=build_mode,
                metric=metric,
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


@index_bp.post("/load")
@require_roles("researcher", "data_manager", "admin")
def load_index():
    payload = request.get_json(silent=True) or {}
    index_id = str(payload.get("index_id") or "").strip()
    if not index_id:
        return jsonify({"error": "invalid_request", "message": "index_id is required"}), 400
    try:
        return jsonify(index_service.load_index(current_app.config["INDEX_DIR"], index_id))
    except FileNotFoundError as exc:
        return jsonify({"error": "index_not_found", "message": str(exc)}), 404
    except RuntimeError as exc:
        return jsonify({"error": "index_load_failed", "message": str(exc)}), 503
    except ValueError as exc:
        return jsonify({"error": "invalid_index", "message": str(exc)}), 400


@index_bp.delete("/<index_id>")
@require_roles("data_manager", "admin")
def delete_index(index_id: str):
    try:
        return jsonify(index_service.delete_index(current_app.config["INDEX_DIR"], index_id))
    except ValueError as exc:
        return jsonify({"error": "invalid_index", "message": str(exc)}), 400
