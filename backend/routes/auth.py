from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from backend.services.auth_service import auth_service


auth_bp = Blueprint("auth", __name__)


def _request_token() -> str | None:
    return auth_service.token_from_header(request.headers.get("Authorization"))


@auth_bp.post("/register")
def register():
    payload = request.get_json(silent=True) or {}
    try:
        result = auth_service.register(
            current_app.config["USERS_PATH"],
            str(payload.get("username") or ""),
            str(payload.get("password") or ""),
            str(payload.get("role") or "normal_user"),
        )
        return jsonify(result), 201
    except ValueError as exc:
        return jsonify({"error": "invalid_registration", "message": str(exc)}), 400


@auth_bp.post("/login")
def login():
    payload = request.get_json(silent=True) or {}
    try:
        return jsonify(
            auth_service.login(
                current_app.config["USERS_PATH"],
                str(payload.get("username") or ""),
                str(payload.get("password") or ""),
            )
        )
    except ValueError as exc:
        return jsonify({"error": "invalid_login", "message": str(exc)}), 401


@auth_bp.post("/logout")
def logout():
    return jsonify(auth_service.logout(_request_token()))


@auth_bp.get("/me")
def me():
    return jsonify(auth_service.current_user(current_app.config["USERS_PATH"], _request_token()))
