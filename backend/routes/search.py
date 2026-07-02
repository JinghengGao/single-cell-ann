from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from backend.routes.permissions import require_roles
from backend.services.llm_analysis_service import LlmAnalysisError, llm_analysis_service
from backend.services.search_service import search_service


search_bp = Blueprint("search", __name__)


def _parse_metadata_filters(payload: dict) -> dict[str, str] | None:
    """从请求体中提取元数据过滤条件。"""
    filters: dict[str, str] = {}
    for field in ("cell_type", "disease", "AgeGroup", "tissue"):
        value = str(payload.get(field) or "").strip()
        if value:
            filters[field] = value
    return filters or None


@search_bp.post("/search")
@require_roles("normal_user", "researcher", "data_manager", "admin")
def search():
    payload = request.get_json(silent=True) or {}
    cell_id = str(payload.get("cell_id") or "").strip()
    dataset_id = str(payload.get("dataset_id") or "").strip() or None
    index_id = str(payload.get("index_id") or "").strip() or None
    top_k = int(payload.get("top_k") or current_app.config["DEFAULT_TOP_K"])
    top_k = min(top_k, current_app.config["MAX_TOP_K"])
    metadata_filters = _parse_metadata_filters(payload)

    try:
        result = search_service.search_by_cell_id(
            cell_id,
            top_k,
            current_app.config["LOG_DIR"],
            registry_path=current_app.config["DATASET_REGISTRY_PATH"],
            dataset_id=dataset_id,
            index_id=index_id,
            metadata_filters=metadata_filters,
        )
        return jsonify(result)
    except KeyError as exc:
        return jsonify({"error": "unknown_cell", "message": str(exc)}), 404
    except ValueError as exc:
        return jsonify({"error": "invalid_request", "message": str(exc)}), 400
    except RuntimeError as exc:
        return jsonify({"error": "search_unavailable", "message": str(exc)}), 503


@search_bp.post("/search/exact")
@require_roles("normal_user", "researcher", "data_manager", "admin")
def exact_search():
    payload = request.get_json(silent=True) or {}
    cell_id = str(payload.get("cell_id") or "").strip()
    dataset_id = str(payload.get("dataset_id") or "").strip() or None
    top_k = int(payload.get("top_k") or current_app.config["DEFAULT_TOP_K"])
    top_k = min(top_k, current_app.config["MAX_TOP_K"])

    try:
        result = search_service.exact_search_by_cell_id(
            cell_id,
            top_k,
            current_app.config["LOG_DIR"],
            registry_path=current_app.config["DATASET_REGISTRY_PATH"],
            dataset_id=dataset_id,
        )
        return jsonify(result)
    except KeyError as exc:
        return jsonify({"error": "unknown_cell", "message": str(exc)}), 404
    except ValueError as exc:
        return jsonify({"error": "invalid_request", "message": str(exc)}), 400
    except RuntimeError as exc:
        return jsonify({"error": "search_unavailable", "message": str(exc)}), 503


@search_bp.post("/search/vector")
@require_roles("normal_user", "researcher", "data_manager", "admin")
def vector_search():
    payload = request.get_json(silent=True) or {}
    query_vector = payload.get("query_vector")
    if not isinstance(query_vector, list):
        return jsonify({"error": "invalid_request", "message": "query_vector must be a list of numbers"}), 400
    index_id = str(payload.get("index_id") or "").strip() or None
    top_k = int(payload.get("top_k") or current_app.config["DEFAULT_TOP_K"])
    top_k = min(top_k, current_app.config["MAX_TOP_K"])
    metadata_filters = _parse_metadata_filters(payload)

    try:
        result = search_service.search_by_vector(
            [float(value) for value in query_vector],
            top_k,
            current_app.config["LOG_DIR"],
            registry_path=current_app.config["DATASET_REGISTRY_PATH"],
            index_id=index_id,
            metadata_filters=metadata_filters,
        )
        return jsonify(result)
    except ValueError as exc:
        return jsonify({"error": "invalid_request", "message": str(exc)}), 400
    except RuntimeError as exc:
        return jsonify({"error": "search_unavailable", "message": str(exc)}), 503


@search_bp.post("/search/compare")
@require_roles("normal_user", "researcher", "data_manager", "admin")
def compare_search():
    """ANN vs 精确检索对比评测"""
    payload = request.get_json(silent=True) or {}
    cell_id = str(payload.get("cell_id") or "").strip()
    dataset_id = str(payload.get("dataset_id") or "").strip() or None
    index_id = str(payload.get("index_id") or "").strip() or None
    top_k = int(payload.get("top_k") or current_app.config["DEFAULT_TOP_K"])
    top_k = min(top_k, current_app.config["MAX_TOP_K"])

    try:
        result = search_service.compare_search(
            cell_id,
            top_k,
            current_app.config["LOG_DIR"],
            registry_path=current_app.config["DATASET_REGISTRY_PATH"],
            dataset_id=dataset_id,
            index_id=index_id,
        )
        return jsonify(result)
    except KeyError as exc:
        return jsonify({"error": "unknown_cell", "message": str(exc)}), 404
    except ValueError as exc:
        return jsonify({"error": "invalid_request", "message": str(exc)}), 400
    except RuntimeError as exc:
        return jsonify({"error": "search_unavailable", "message": str(exc)}), 503


@search_bp.post("/search/batch")
@require_roles("normal_user", "researcher", "data_manager", "admin")
def batch_search():
    payload = request.get_json(silent=True) or {}
    cell_ids = payload.get("cell_ids")
    if not isinstance(cell_ids, list) or not cell_ids:
        return jsonify({"error": "invalid_request", "message": "cell_ids must be a non-empty list"}), 400
    dataset_id = str(payload.get("dataset_id") or "").strip() or None
    index_id = str(payload.get("index_id") or "").strip() or None
    top_k = int(payload.get("top_k") or current_app.config["DEFAULT_TOP_K"])
    top_k = min(top_k, current_app.config["MAX_TOP_K"])
    try:
        result = search_service.batch_search(
            [str(cid).strip() for cid in cell_ids],
            top_k,
            current_app.config["LOG_DIR"],
            registry_path=current_app.config["DATASET_REGISTRY_PATH"],
            dataset_id=dataset_id,
            index_id=index_id,
        )
        return jsonify(result)
    except RuntimeError as exc:
        return jsonify({"error": "search_unavailable", "message": str(exc)}), 503


@search_bp.post("/search/analyze")
@require_roles("normal_user", "researcher", "data_manager", "admin")
def analyze_search():
    payload = request.get_json(silent=True) or {}
    search_result = payload.get("search_result")
    question = str(payload.get("question") or "").strip() or None
    enable_thinking = payload.get("enable_thinking")
    if enable_thinking is not None and not isinstance(enable_thinking, bool):
        return jsonify({"error": "invalid_request", "message": "enable_thinking must be a boolean"}), 400

    try:
        result = llm_analysis_service.analyze_search_result(
            search_result,
            current_app.config,
            user_question=question,
            enable_thinking=enable_thinking,
        )
        return jsonify(result)
    except ValueError as exc:
        return jsonify({"error": "invalid_request", "message": str(exc)}), 400
    except LlmAnalysisError as exc:
        return jsonify({"error": "llm_unavailable", "message": str(exc)}), 503


# -- 访客 Demo 检索（无需登录） --

@search_bp.get("/demo/search")
def demo_search():
    """免登录示例检索：使用预置 Demo 细胞返回示例结果。"""
    from backend.services.data_service import data_service as ds

    registry_path = current_app.config["DATASET_REGISTRY_PATH"]
    cell_id = request.args.get("cell_id", "").strip()
    top_k = min(int(request.args.get("top_k", 5)), 10)

    # 取数据集中的前几个 cell_id 作为 Demo 候选项
    datasets = ds.list_datasets(registry_path).get("datasets", [])
    demo_cells: list[dict[str, str]] = []
    for d in datasets:
        for cid in (d.get("sample_cell_ids") or [])[:3]:
            demo_cells.append({"cell_id": cid, "dataset_id": d["dataset_id"], "dataset_name": d["name"]})

    if not cell_id and demo_cells:
        cell_id = demo_cells[0]["cell_id"]

    if not cell_id:
        return jsonify({"demo_cells": demo_cells, "message": "no demo cells available"})

    try:
        result = search_service.search_by_cell_id(
            cell_id, top_k,
            current_app.config["LOG_DIR"],
            registry_path=registry_path,
        )
        result["demo_cells"] = demo_cells
        return jsonify(result)
    except Exception as exc:
        return jsonify({"error": "demo_search_failed", "message": str(exc), "demo_cells": demo_cells}), 503
