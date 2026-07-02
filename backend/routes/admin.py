from __future__ import annotations

import json
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request

from backend.routes.permissions import require_roles
from backend.faiss_runtime import inspect_faiss_runtime
from backend.services.auth_service import auth_service
from backend.services.data_service import data_service
from backend.services.index_service import index_service


admin_bp = Blueprint("admin", __name__)


def _tail_jsonl(path: Path, limit: int) -> list[dict]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    records = []
    for line in lines[-limit:]:
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            records.append({"raw": line})
    return records


@admin_bp.get("/users")
@require_roles("admin")
def list_users():
    try:
        users = auth_service.list_users(current_app.config["USERS_PATH"])
        return jsonify({"count": len(users), "users": users})
    except ValueError as exc:
        return jsonify({"error": "invalid_request", "message": str(exc)}), 400


@admin_bp.put("/users/<username>/role")
@require_roles("admin")
def update_user_role(username: str):
    payload = request.get_json(silent=True) or {}
    new_role = str(payload.get("role") or "").strip()
    if not new_role:
        return jsonify({"error": "invalid_request", "message": "role is required"}), 400
    try:
        user = auth_service.update_user_role(current_app.config["USERS_PATH"], username, new_role)
        return jsonify(user)
    except ValueError as exc:
        return jsonify({"error": "invalid_request", "message": str(exc)}), 400


@admin_bp.put("/users/<username>/status")
@require_roles("admin")
def update_user_status(username: str):
    payload = request.get_json(silent=True) or {}
    new_status = str(payload.get("status") or "").strip()
    if not new_status:
        return jsonify({"error": "invalid_request", "message": "status is required"}), 400
    try:
        user = auth_service.update_user_status(current_app.config["USERS_PATH"], username, new_status)
        return jsonify(user)
    except ValueError as exc:
        return jsonify({"error": "invalid_request", "message": str(exc)}), 400


@admin_bp.delete("/users/<username>")
@require_roles("admin")
def delete_user(username: str):
    try:
        user = auth_service.delete_user(current_app.config["USERS_PATH"], username)
        return jsonify({"deleted": user})
    except ValueError as exc:
        return jsonify({"error": "invalid_request", "message": str(exc)}), 400


@admin_bp.get("/logs/query")
@require_roles("admin")
def query_logs():
    limit = min(int(request.args.get("limit", 100)), 500)
    records = _tail_jsonl(current_app.config["LOG_DIR"] / "query_log.jsonl", limit)
    return jsonify({"count": len(records), "logs": records})


@admin_bp.get("/logs/benchmark")
@require_roles("admin")
def benchmark_logs():
    limit = min(int(request.args.get("limit", 100)), 500)
    records = _tail_jsonl(current_app.config["LOG_DIR"] / "benchmark_results.jsonl", limit)
    return jsonify({"count": len(records), "logs": records})


@admin_bp.get("/system/status")
@require_roles("admin")
def system_status():
    runtime = inspect_faiss_runtime()
    return jsonify(
        {
            "faiss": {
                "available": runtime.available,
                "mode": runtime.mode,
                "version": runtime.version,
                "gpu_count": runtime.gpu_count,
                "error": runtime.error,
            },
            "dataset": data_service.snapshot.summary(),
            "index": index_service.status(),
        }
    )
