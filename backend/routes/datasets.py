from __future__ import annotations

from pathlib import Path

from flask import Blueprint, current_app, jsonify, request

from backend.services.data_service import data_service


datasets_bp = Blueprint("datasets", __name__)


@datasets_bp.get("")
def list_datasets():
    return jsonify(data_service.list_datasets(current_app.config["DATASET_REGISTRY_PATH"]))


@datasets_bp.post("/scan")
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
def upload_dataset():
    uploaded_file = request.files.get("file")
    if uploaded_file is None:
        return jsonify({"error": "missing_file", "message": "file is required"}), 400
    try:
        return jsonify(data_service.upload_dataset(uploaded_file, current_app.config["UPLOAD_DIR"], current_app.config["DATASET_REGISTRY_PATH"])), 201
    except ValueError as exc:
        return jsonify({"error": "invalid_upload", "message": str(exc)}), 400


@datasets_bp.post("/load")
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


@datasets_bp.get("/current")
def current_dataset():
    return jsonify(data_service.snapshot.summary())


@datasets_bp.get("/<dataset_id>")
def dataset_detail(dataset_id: str):
    try:
        return jsonify(data_service.get_dataset(dataset_id, current_app.config["DATASET_REGISTRY_PATH"]))
    except KeyError as exc:
        return jsonify({"error": "unknown_dataset", "message": str(exc)}), 404


@datasets_bp.post("/<dataset_id>/validate")
def validate_dataset(dataset_id: str):
    try:
        return jsonify(data_service.validate_dataset(dataset_id, current_app.config["DATASET_REGISTRY_PATH"]))
    except FileNotFoundError as exc:
        return jsonify({"error": "dataset_not_found", "message": str(exc)}), 404
    except KeyError as exc:
        return jsonify({"error": "invalid_dataset", "message": str(exc)}), 400
    except (TypeError, ValueError) as exc:
        return jsonify({"error": "invalid_dataset", "message": str(exc)}), 400
