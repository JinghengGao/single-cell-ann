from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any

from flask import current_app, g, jsonify, request

from backend.services.auth_service import auth_service


ROLE_LABELS = {
    "normal_user": "普通用户",
    "researcher": "研究人员",
    "data_manager": "数据维护者",
    "admin": "管理员",
}


def require_roles(*allowed_roles: str) -> Callable:
    def decorator(view_func: Callable) -> Callable:
        @wraps(view_func)
        def wrapper(*args: Any, **kwargs: Any):
            token = auth_service.token_from_header(request.headers.get("Authorization"))
            current = auth_service.current_user(current_app.config["USERS_PATH"], token)
            if not current.get("authenticated"):
                return jsonify({"error": "auth_required", "message": "login is required"}), 401

            user = current["user"]
            if user["role"] not in allowed_roles:
                allowed = "、".join(ROLE_LABELS.get(role, role) for role in allowed_roles)
                return (
                    jsonify(
                        {
                            "error": "permission_denied",
                            "message": f"current role cannot perform this operation; required: {allowed}",
                            "required_roles": list(allowed_roles),
                            "current_role": user["role"],
                        }
                    ),
                    403,
                )

            g.current_user = user
            return view_func(*args, **kwargs)

        return wrapper

    return decorator
