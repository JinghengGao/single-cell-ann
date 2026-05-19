from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from backend.services.data_service import data_service


visualization_bp = Blueprint("visualization", __name__)


@visualization_bp.get("/cells")
def cells():
    raw_limit = request.args.get("limit", current_app.config["DEFAULT_VIS_LIMIT"])
    limit = min(int(raw_limit), current_app.config["DEFAULT_VIS_LIMIT"])
    dataset_ids = [item.strip() for item in request.args.getlist("dataset_id") if item.strip()]
    if not dataset_ids:
        csv_dataset_ids = request.args.get("dataset_ids", "")
        dataset_ids = [item.strip() for item in csv_dataset_ids.split(",") if item.strip()]

    try:
        if dataset_ids:
            return jsonify(
                data_service.sample_visualization_points_for_datasets(
                    dataset_ids,
                    limit,
                    registry_path=current_app.config["DATASET_REGISTRY_PATH"],
                )
            )
        return jsonify(data_service.sample_visualization_points(limit, registry_path=current_app.config["DATASET_REGISTRY_PATH"]))
    except KeyError as exc:
        return jsonify({"error": "unknown_dataset", "message": str(exc)}), 404
    except RuntimeError as exc:
        return jsonify({"error": "dataset_unavailable", "message": str(exc)}), 503
    except ValueError as exc:
        return jsonify({"error": "invalid_request", "message": str(exc)}), 400
