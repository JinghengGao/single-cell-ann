from __future__ import annotations

from pathlib import Path

from flask import Blueprint, current_app, jsonify, request

from backend.routes.permissions import require_roles
from backend.services.data_service import data_service


datasets_bp = Blueprint("datasets", __name__)


@datasets_bp.get("")
def list_datasets():
    return jsonify(data_service.list_datasets(current_app.config["DATASET_REGISTRY_PATH"]))


@datasets_bp.post("/scan")
@require_roles("data_manager", "admin")
def scan_datasets():
    return jsonify(
        data_service.scan_dataset_files(
            current_app.config["DATA_DIR"],
            current_app.config["DATASET_LIBRARY_DIR"],
            current_app.config["UPLOAD_DIR"],
            current_app.config["DATA_PATH"],
            current_app.config["DATASET_REGISTRY_PATH"],
        )
    )


@datasets_bp.post("/upload")
@require_roles("data_manager", "admin")
def upload_dataset():
    uploaded_file = request.files.get("file")
    if uploaded_file is None:
        return jsonify({"error": "missing_file", "message": "file is required"}), 400
    try:
        return jsonify(data_service.upload_dataset(uploaded_file, current_app.config["UPLOAD_DIR"], current_app.config["DATASET_REGISTRY_PATH"])), 201
    except ValueError as exc:
        return jsonify({"error": "invalid_upload", "message": str(exc)}), 400


@datasets_bp.post("/load")
@require_roles("researcher", "data_manager", "admin")
def load_dataset():
    payload = request.get_json(silent=True) or {}
    dataset_id = str(payload.get("dataset_id") or "").strip() or None
    data_path = Path(payload["path"]) if payload.get("path") else None
    if dataset_id is None and data_path is None:
        data_path = current_app.config["DATA_PATH"]

    try:
        summary = data_service.load_h5ad(
            data_path,
            dataset_id=dataset_id,
            registry_path=current_app.config["DATASET_REGISTRY_PATH"],
        )
        return jsonify(summary)
    except FileNotFoundError as exc:
        return jsonify({"error": "dataset_not_found", "message": str(exc)}), 404
    except KeyError as exc:
        return jsonify({"error": "unknown_dataset", "message": str(exc)}), 404
    except (TypeError, ValueError) as exc:
        return jsonify({"error": "invalid_dataset", "message": str(exc)}), 400


@datasets_bp.post("/validate")
@require_roles("data_manager", "admin")
def validate_datasets():
    payload = request.get_json(silent=True) or {}
    dataset_ids = payload.get("dataset_ids") or []
    if not isinstance(dataset_ids, list):
        return jsonify({"error": "invalid_request", "message": "dataset_ids must be a list"}), 400
    return jsonify(data_service.validate_datasets([str(item) for item in dataset_ids], current_app.config["DATASET_REGISTRY_PATH"]))


@datasets_bp.get("/current")
def current_dataset():
    return jsonify(data_service.snapshot.summary())


@datasets_bp.get("/<dataset_id>")
def dataset_detail(dataset_id: str):
    try:
        return jsonify(data_service.get_dataset(dataset_id, current_app.config["DATASET_REGISTRY_PATH"]))
    except KeyError as exc:
        return jsonify({"error": "unknown_dataset", "message": str(exc)}), 404


@datasets_bp.patch("/<dataset_id>/metadata")
@require_roles("data_manager", "admin")
def update_dataset_metadata(dataset_id: str):
    payload = request.get_json(silent=True) or {}
    try:
        return jsonify(
            data_service.update_dataset_metadata(
                dataset_id,
                current_app.config["DATASET_REGISTRY_PATH"],
                payload,
            )
        )
    except KeyError as exc:
        return jsonify({"error": "unknown_dataset", "message": str(exc)}), 404


@datasets_bp.post("/<dataset_id>/activate")
@require_roles("researcher", "data_manager", "admin")
def activate_dataset(dataset_id: str):
    try:
        return jsonify(data_service.activate_dataset(dataset_id, current_app.config["DATASET_REGISTRY_PATH"]))
    except KeyError as exc:
        return jsonify({"error": "unknown_dataset", "message": str(exc)}), 404
    except ValueError as exc:
        return jsonify({"error": "invalid_dataset", "message": str(exc)}), 400
    except RuntimeError as exc:
        return jsonify({"error": "dataset_unavailable", "message": str(exc)}), 503


@datasets_bp.post("/<dataset_id>/offline")
@require_roles("data_manager", "admin")
def offline_dataset(dataset_id: str):
    try:
        return jsonify(data_service.update_dataset_status(dataset_id, current_app.config["DATASET_REGISTRY_PATH"], "offline"))
    except KeyError as exc:
        return jsonify({"error": "unknown_dataset", "message": str(exc)}), 404
    except ValueError as exc:
        return jsonify({"error": "invalid_dataset", "message": str(exc)}), 400


@datasets_bp.post("/<dataset_id>/restore")
@require_roles("data_manager", "admin")
def restore_dataset(dataset_id: str):
    try:
        return jsonify(data_service.update_dataset_status(dataset_id, current_app.config["DATASET_REGISTRY_PATH"], "registered"))
    except KeyError as exc:
        return jsonify({"error": "unknown_dataset", "message": str(exc)}), 404
    except ValueError as exc:
        return jsonify({"error": "invalid_dataset", "message": str(exc)}), 400


@datasets_bp.delete("/<dataset_id>")
@require_roles("data_manager", "admin")
def delete_dataset(dataset_id: str):
    try:
        return jsonify({"deleted": data_service.delete_dataset(dataset_id, current_app.config["DATASET_REGISTRY_PATH"])})
    except KeyError as exc:
        return jsonify({"error": "unknown_dataset", "message": str(exc)}), 404


@datasets_bp.post("/<dataset_id>/validate")
@require_roles("data_manager", "admin")
def validate_dataset(dataset_id: str):
    try:
        return jsonify(data_service.validate_dataset(dataset_id, current_app.config["DATASET_REGISTRY_PATH"]))
    except FileNotFoundError as exc:
        return jsonify({"error": "dataset_not_found", "message": str(exc)}), 404
    except KeyError as exc:
        return jsonify({"error": "invalid_dataset", "message": str(exc)}), 400
    except (TypeError, ValueError) as exc:
        return jsonify({"error": "invalid_dataset", "message": str(exc)}), 400
