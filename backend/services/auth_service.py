from __future__ import annotations

import json
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any

from werkzeug.security import check_password_hash, generate_password_hash


ALLOWED_ROLES = {"normal_user", "researcher", "data_manager", "admin"}
DEFAULT_TOKEN_TTL_SECONDS = 86400  # 24 小时
DEFAULT_LOGIN_MAX_FAILURES = 5
DEFAULT_LOGIN_LOCKOUT_SECONDS = 900  # 15 分钟


@dataclass
class AuthUser:
    username: str
    role: str
    created_at: str

    def summary(self) -> dict[str, Any]:
        return {
            "username": self.username,
            "role": self.role,
            "created_at": self.created_at,
        }


class AuthService:
    def __init__(self) -> None:
        self._lock = RLock()
        self._tokens: dict[str, tuple[str, float]] = {}  # token -> (username, expires_at)
        self._login_failures: dict[str, tuple[int, float]] = {}  # username -> (count, first_failure_at)

    # ------------------------------------------------------------------
    # 公开 API
    # ------------------------------------------------------------------

    def register(self, users_path: Path, username: str, password: str, role: str = "researcher") -> dict[str, Any]:
        username = username.strip()
        role = role.strip() or "researcher"
        self._validate_credentials(username, password)
        if role not in ALLOWED_ROLES:
            raise ValueError(f"unsupported role: {role}")

        with self._lock:
            store = self._load_store(users_path)
            if username in store["users"]:
                raise ValueError("username already exists")

            user = {
                "username": username,
                "password_hash": generate_password_hash(password),
                "role": role,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            store["users"][username] = user
            self._save_store(users_path, store)
            return {"authenticated": True, "user": self._public_user(user)}

    def login(
        self,
        users_path: Path,
        username: str,
        password: str,
        *,
        token_ttl: int = DEFAULT_TOKEN_TTL_SECONDS,
        max_failures: int = DEFAULT_LOGIN_MAX_FAILURES,
        lockout_seconds: int = DEFAULT_LOGIN_LOCKOUT_SECONDS,
    ) -> dict[str, Any]:
        username = username.strip()
        with self._lock:
            self._check_login_lockout(username, max_failures, lockout_seconds)

            store = self._load_store(users_path)
            user = store["users"].get(username)
            if user is None or not check_password_hash(user["password_hash"], password):
                self._record_login_failure(username)
                raise ValueError("invalid username or password")

            self._clear_login_failures(username)
            self._clean_expired_tokens()
            token = secrets.token_urlsafe(32)
            self._tokens[token] = (username, time.monotonic() + token_ttl)
            return {"authenticated": True, "token": token, "user": self._public_user(user)}

    def logout(self, token: str | None) -> dict[str, Any]:
        with self._lock:
            if token:
                self._tokens.pop(token, None)
        return {"authenticated": False}

    def current_user(self, users_path: Path, token: str | None) -> dict[str, Any]:
        if not token:
            return {"authenticated": False, "user": None}

        with self._lock:
            entry = self._tokens.get(token)
            if entry is None:
                return {"authenticated": False, "user": None}
            username, expires_at = entry
            if time.monotonic() >= expires_at:
                self._tokens.pop(token, None)
                return {"authenticated": False, "user": None}

            store = self._load_store(users_path)
            user = store["users"].get(username)
            if user is None:
                self._tokens.pop(token, None)
                return {"authenticated": False, "user": None}
            return {"authenticated": True, "user": self._public_user(user)}

    # ------------------------------------------------------------------
    # Admin 管理方法
    # ------------------------------------------------------------------

    def list_users(self, users_path: Path) -> list[dict[str, Any]]:
        with self._lock:
            store = self._load_store(users_path)
            return sorted(
                [self._public_user(user) for user in store["users"].values()],
                key=lambda u: u["username"],
            )

    def update_user_role(self, users_path: Path, target_username: str, new_role: str) -> dict[str, Any]:
        target_username = target_username.strip()
        new_role = new_role.strip()
        if new_role not in ALLOWED_ROLES:
            raise ValueError(f"unsupported role: {new_role}")
        with self._lock:
            store = self._load_store(users_path)
            if target_username not in store["users"]:
                raise ValueError(f"user not found: {target_username}")
            store["users"][target_username]["role"] = new_role
            self._save_store(users_path, store)
            return self._public_user(store["users"][target_username])

    def delete_user(self, users_path: Path, target_username: str) -> dict[str, Any]:
        target_username = target_username.strip()
        with self._lock:
            store = self._load_store(users_path)
            if target_username not in store["users"]:
                raise ValueError(f"user not found: {target_username}")
            deleted = self._public_user(store["users"].pop(target_username))
            # 清理该用户的 token
            stale_tokens = [t for t, (u, _) in self._tokens.items() if u == target_username]
            for t in stale_tokens:
                self._tokens.pop(t, None)
            self._save_store(users_path, store)
            return deleted

    # ------------------------------------------------------------------
    # 工具方法
    # ------------------------------------------------------------------

    @staticmethod
    def token_from_header(authorization: str | None) -> str | None:
        if not authorization:
            return None
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            return None
        return token.strip()

    @staticmethod
    def _validate_credentials(username: str, password: str) -> None:
        if len(username) < 3:
            raise ValueError("username must be at least 3 characters")
        if len(password) < 6:
            raise ValueError("password must be at least 6 characters")

    @staticmethod
    def _load_store(users_path: Path) -> dict[str, Any]:
        if not users_path.exists():
            return {"users": {}}
        with users_path.open("r", encoding="utf-8") as file:
            store = json.load(file)
        if not isinstance(store.get("users"), dict):
            raise ValueError("invalid users store")
        return store

    @staticmethod
    def _save_store(users_path: Path, store: dict[str, Any]) -> None:
        users_path.parent.mkdir(parents=True, exist_ok=True)
        with users_path.open("w", encoding="utf-8") as file:
            json.dump(store, file, ensure_ascii=False, indent=2)

    @staticmethod
    def _public_user(user: dict[str, Any]) -> dict[str, Any]:
        return AuthUser(
            username=user["username"],
            role=user["role"],
            created_at=user["created_at"],
        ).summary()

    def _clean_expired_tokens(self) -> None:
        now = time.monotonic()
        expired = [t for t, (_, expires) in self._tokens.items() if now >= expires]
        for t in expired:
            self._tokens.pop(t, None)

    def _check_login_lockout(self, username: str, max_failures: int, lockout_seconds: int) -> None:
        entry = self._login_failures.get(username)
        if entry is None:
            return
        count, first_at = entry
        if count < max_failures:
            return
        elapsed = time.monotonic() - first_at
        if elapsed < lockout_seconds:
            remaining = int(lockout_seconds - elapsed)
            raise ValueError(f"account locked due to too many login failures; try again in {remaining}s")
        # 锁定期已过，清除记录
        self._login_failures.pop(username, None)

    def _record_login_failure(self, username: str) -> None:
        now = time.monotonic()
        entry = self._login_failures.get(username)
        if entry is None:
            self._login_failures[username] = (1, now)
            return
        count, first_at = entry
        if now - first_at > DEFAULT_LOGIN_LOCKOUT_SECONDS:
            self._login_failures[username] = (1, now)
        else:
            self._login_failures[username] = (count + 1, first_at)

    def _clear_login_failures(self, username: str) -> None:
        self._login_failures.pop(username, None)


auth_service = AuthService()
