from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from backend.routes.permissions import require_roles
from backend.services.auth_service import auth_service


admin_bp = Blueprint("admin", __name__)


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


@admin_bp.delete("/users/<username>")
@require_roles("admin")
def delete_user(username: str):
    try:
        user = auth_service.delete_user(current_app.config["USERS_PATH"], username)
        return jsonify({"deleted": user})
    except ValueError as exc:
        return jsonify({"error": "invalid_request", "message": str(exc)}), 400
