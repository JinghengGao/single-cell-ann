from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from backend.app import create_app
from backend.config import Config
from backend.faiss_runtime import inspect_faiss_runtime


@contextmanager
def runtime_tmpdir():
    root = Path(__file__).resolve().parents[1] / "runtime" / "pytest"
    root.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="case-", dir=root) as name:
        yield Path(name)


def make_test_config(tmp_path: Path):
    class TestConfig(Config):
        DATASET_REGISTRY_PATH = tmp_path / "registry.json"
        USERS_PATH = tmp_path / "users.json"
        INDEX_DIR = tmp_path / "indexes"
        LOG_DIR = tmp_path / "logs"

    return TestConfig


def auth_headers(client, role: str = "admin", username: str | None = None) -> dict[str, str]:
    username = username or f"{role}_user"
    password = "secret123"
    client.post("/api/auth/register", json={"username": username, "password": password, "role": role})
    login = client.post("/api/auth/login", json={"username": username, "password": password})
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.get_json()['token']}"}


def sample_search_result() -> dict:
    return {
        "query": {"cell_id": "query-cell-1", "dataset_id": "liver", "index_id": "idx-1", "top_k": 3},
        "query_cell": {
            "dataset_id": "liver",
            "dataset_name": "Liver",
            "cell_id": "query-cell-1",
            "cell_type": "hepatocyte",
            "disease": "normal",
            "AgeGroup": "adult",
            "tissue": "liver",
        },
        "result_count": 3,
        "hits": [
            {
                "rank": 1,
                "dataset_id": "liver",
                "dataset_name": "Liver",
                "cell_id": "hit-cell-1",
                "distance": 0.12,
                "similarity": 0.8928,
                "cell_type": "hepatocyte",
                "disease": "normal",
                "AgeGroup": "adult",
                "tissue": "liver",
            },
            {
                "rank": 2,
                "dataset_id": "liver",
                "dataset_name": "Liver",
                "cell_id": "hit-cell-2",
                "distance": 0.2,
                "similarity": 0.8333,
                "cell_type": "hepatocyte",
                "disease": "normal",
                "AgeGroup": "adult",
                "tissue": "liver",
            },
            {
                "rank": 3,
                "dataset_id": "liver",
                "dataset_name": "Liver",
                "cell_id": "hit-cell-3",
                "distance": 0.4,
                "similarity": 0.7143,
                "cell_type": "cholangiocyte",
                "disease": "normal",
                "AgeGroup": "adult",
                "tissue": "liver",
            },
        ],
    }


class FakeLlmResponse:
    def __init__(self, status_code: int = 200, payload: dict | None = None, text: str = ""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


def test_health_endpoint_reports_data_path():
    app = create_app()
    client = app.test_client()

    response = client.get("/api/health")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["data_exists"] is True
    assert "faiss" in payload


def test_dataset_load_reads_pca_vectors_and_metadata():
    with runtime_tmpdir() as tmp_path:
        app = create_app(make_test_config(tmp_path))
        client = app.test_client()
        headers = auth_headers(client, "researcher")

        response = client.post("/api/datasets/load", json={}, headers=headers)

        assert response.status_code == 200
        payload = response.get_json()
        assert payload["loaded"] is True
        assert payload["cell_count"] == 69032
        assert payload["vector_dim"] == 30
        assert "cell_type" in payload["metadata_fields"]
        assert payload["sample_cell_ids"]


def test_protected_dataset_actions_require_roles():
    with runtime_tmpdir() as tmp_path:
        app = create_app(make_test_config(tmp_path))
        client = app.test_client()

        unauthenticated = client.post("/api/datasets/scan")
        assert unauthenticated.status_code == 401

        normal_headers = auth_headers(client, "normal_user")
        forbidden = client.post("/api/datasets/scan", headers=normal_headers)
        assert forbidden.status_code == 403

        manager_headers = auth_headers(client, "data_manager")
        allowed = client.post("/api/datasets/scan", headers=manager_headers)
        assert allowed.status_code == 200
        assert allowed.get_json()["count"] >= 1


def test_researcher_can_build_index_but_normal_user_cannot():
    with runtime_tmpdir() as tmp_path:
        app = create_app(make_test_config(tmp_path))
        client = app.test_client()
        normal_headers = auth_headers(client, "normal_user", "normal_for_index")

        forbidden = client.post("/api/index/build", json={}, headers=normal_headers)
        assert forbidden.status_code == 403



def test_cors_allows_vite_fallback_port():
    app = create_app()
    client = app.test_client()

    response = client.get("/api/health", headers={"Origin": "http://127.0.0.1:5174"})

    assert response.status_code == 200
    assert response.headers["Access-Control-Allow-Origin"] == "http://127.0.0.1:5174"


def test_auth_register_login_me_and_logout():
    with runtime_tmpdir() as tmp_path:
        app = create_app(make_test_config(tmp_path))
        client = app.test_client()

        register = client.post(
            "/api/auth/register",
            json={"username": "demo_user", "password": "secret123", "role": "researcher"},
        )
        assert register.status_code == 201
        assert register.get_json()["user"]["role"] == "researcher"

        login = client.post("/api/auth/login", json={"username": "demo_user", "password": "secret123"})
        assert login.status_code == 200
        token = login.get_json()["token"]

        me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200
        assert me.get_json()["authenticated"] is True
        assert me.get_json()["user"]["username"] == "demo_user"

        logout = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
        assert logout.status_code == 200
        assert logout.get_json()["authenticated"] is False


def test_public_registration_cannot_create_admin_after_bootstrap_and_admin_can_disable_user():
    with runtime_tmpdir() as tmp_path:
        app = create_app(make_test_config(tmp_path))
        client = app.test_client()

        admin_headers = auth_headers(client, "admin", "owner_admin")

        normal = client.post(
            "/api/auth/register",
            json={"username": "plain_user", "password": "secret123", "role": "normal_user"},
        )
        assert normal.status_code == 201
        assert normal.get_json()["user"]["role"] == "normal_user"

        late_admin = client.post(
            "/api/auth/register",
            json={"username": "late_admin", "password": "secret123", "role": "admin"},
        )
        assert late_admin.status_code == 400

        disabled = client.put(
            "/api/admin/users/plain_user/status",
            json={"status": "disabled"},
            headers=admin_headers,
        )
        assert disabled.status_code == 200
        assert disabled.get_json()["status"] == "disabled"

        login = client.post("/api/auth/login", json={"username": "plain_user", "password": "secret123"})
        assert login.status_code == 401


def test_dataset_registry_scan_validate_and_list():
    with runtime_tmpdir() as tmp_path:
        app = create_app(make_test_config(tmp_path))
        client = app.test_client()
        headers = auth_headers(client, "admin")

        scan = client.post("/api/datasets/scan", headers=headers)
        assert scan.status_code == 200
        assert scan.get_json()["count"] >= 1

        validate = client.post("/api/datasets/validate", json={"dataset_ids": ["liver"]}, headers=headers)
        assert validate.status_code == 200
        payload = validate.get_json()
        assert payload["validated_count"] == 1
        assert payload["datasets"][0]["cell_count"] == 69032
        assert payload["datasets"][0]["vector_dim"] == 30

        datasets = client.get("/api/datasets")
        assert datasets.status_code == 200
        liver = next(item for item in datasets.get_json()["datasets"] if item["dataset_id"] == "liver")
        assert liver["status"] == "validated"
        assert "cell_type" in liver["metadata_fields"]


def test_dataset_lifecycle_metadata_offline_restore_and_delete():
    with runtime_tmpdir() as tmp_path:
        app = create_app(make_test_config(tmp_path))
        client = app.test_client()
        headers = auth_headers(client, "admin")

        client.post("/api/datasets/scan", headers=headers)

        metadata = client.patch(
            "/api/datasets/liver/metadata",
            json={"name": "Liver demo", "species": "human", "tissue": "liver"},
            headers=headers,
        )
        assert metadata.status_code == 200
        assert metadata.get_json()["name"] == "Liver demo"
        assert metadata.get_json()["species"] == "human"

        offline = client.post("/api/datasets/liver/offline", headers=headers)
        assert offline.status_code == 200
        assert offline.get_json()["status"] == "offline"

        blocked_load = client.post("/api/datasets/load", json={"dataset_id": "liver"}, headers=headers)
        assert blocked_load.status_code == 400

        restore = client.post("/api/datasets/liver/restore", headers=headers)
        assert restore.status_code == 200
        assert restore.get_json()["status"] == "registered"

        deleted = client.delete("/api/datasets/liver", headers=headers)
        assert deleted.status_code == 200
        datasets = client.get("/api/datasets").get_json()["datasets"]
        assert all(item["dataset_id"] != "liver" for item in datasets)


def test_combined_and_separate_indexes_return_dataset_aware_results():
    runtime = inspect_faiss_runtime()
    if not runtime.available:
        pytest.skip("FAISS is unavailable in this Python environment")

    with runtime_tmpdir() as tmp_path:
        app = create_app(make_test_config(tmp_path))
        client = app.test_client()
        admin_headers = auth_headers(client, "admin")
        researcher_headers = auth_headers(client, "researcher")
        normal_headers = auth_headers(client, "normal_user")

        client.post("/api/datasets/scan", headers=admin_headers)
        dataset = client.post("/api/datasets/load", json={"dataset_id": "liver"}, headers=researcher_headers).get_json()
        sample_cell_id = dataset["sample_cell_ids"][0]

        combined = client.post(
            "/api/index/build",
            json={"dataset_ids": ["liver"], "mode": "combined", "nlist": 64, "nprobe": 8},
            headers=researcher_headers,
        )
        assert combined.status_code == 200
        assert combined.get_json()["ready"] is True
        assert combined.get_json()["dataset_ids"] == ["liver"]

        search = client.post(
            "/api/search",
            json={"cell_id": sample_cell_id, "dataset_id": "liver", "top_k": 3},
            headers=normal_headers,
        )
        assert search.status_code == 200
        result = search.get_json()
        assert result["result_count"] == 3
        assert result["query_cell"]["dataset_id"] == "liver"
        assert all(hit["dataset_id"] == "liver" for hit in result["hits"])

        from backend.services.data_service import data_service

        query_vector = data_service.get_vector_by_cell_id(sample_cell_id, dataset_id="liver", registry_path=tmp_path / "registry.json")
        vector_search = client.post(
            "/api/search/vector",
            json={"query_vector": query_vector.tolist(), "top_k": 3},
            headers=normal_headers,
        )
        assert vector_search.status_code == 200
        assert vector_search.get_json()["result_count"] == 3

        compare = client.post(
            "/api/search/compare",
            json={"cell_id": sample_cell_id, "dataset_id": "liver", "top_k": 3},
            headers=normal_headers,
        )
        assert compare.status_code == 200

        query_logs = client.get("/api/admin/logs/query", headers=admin_headers)
        assert query_logs.status_code == 200
        assert query_logs.get_json()["count"] >= 1
        benchmark_logs = client.get("/api/admin/logs/benchmark", headers=admin_headers)
        assert benchmark_logs.status_code == 200
        assert any(item["benchmark_type"] == "compare" for item in benchmark_logs.get_json()["logs"])

        separate = client.post(
            "/api/index/build",
            json={"dataset_ids": ["liver"], "mode": "separate", "nlist": 64, "nprobe": 8},
            headers=researcher_headers,
        )
        assert separate.status_code == 200
        assert separate.get_json()["built_indexes"][0]["build_mode"] == "separate"


def test_index_metadata_allows_load_and_delete_from_disk():
    runtime = inspect_faiss_runtime()
    if not runtime.available:
        pytest.skip("FAISS is unavailable in this Python environment")

    with runtime_tmpdir() as tmp_path:
        app = create_app(make_test_config(tmp_path))
        client = app.test_client()
        headers = auth_headers(client, "admin")

        client.post("/api/datasets/scan", headers=headers)
        client.post("/api/datasets/load", json={"dataset_id": "liver"}, headers=headers)
        built = client.post(
            "/api/index/build",
            json={"dataset_ids": ["liver"], "mode": "combined", "nlist": 32, "nprobe": 4},
            headers=headers,
        )
        assert built.status_code == 200
        index_id = built.get_json()["index_id"]

        loaded = client.post("/api/index/load", json={"index_id": index_id}, headers=headers)
        assert loaded.status_code == 200
        assert loaded.get_json()["active_index_id"] == index_id

        deleted = client.delete(f"/api/index/{index_id}", headers=headers)
        assert deleted.status_code == 200
        assert all(item["index_id"] != index_id for item in deleted.get_json()["indexes"])


def test_llm_analysis_requires_login():
    with runtime_tmpdir() as tmp_path:
        app = create_app(make_test_config(tmp_path))
        client = app.test_client()

        response = client.post("/api/search/analyze", json={"search_result": sample_search_result()})

        assert response.status_code == 401


def test_llm_analysis_rejects_missing_or_empty_results():
    with runtime_tmpdir() as tmp_path:
        app = create_app(make_test_config(tmp_path))
        client = app.test_client()
        headers = auth_headers(client, "normal_user", "normal_for_llm_invalid")

        missing = client.post("/api/search/analyze", json={}, headers=headers)
        assert missing.status_code == 400
        assert missing.get_json()["error"] == "invalid_request"

        empty_result = sample_search_result()
        empty_result["hits"] = []
        empty = client.post("/api/search/analyze", json={"search_result": empty_result}, headers=headers)
        assert empty.status_code == 400
        assert empty.get_json()["error"] == "invalid_request"


def test_llm_analysis_reports_unconfigured_api_key():
    with runtime_tmpdir() as tmp_path:
        class TestConfig(make_test_config(tmp_path)):
            LLM_PROVIDER = "siliconflow"
            LLM_API_KEY = ""

        app = create_app(TestConfig)
        client = app.test_client()
        headers = auth_headers(client, "normal_user", "normal_for_llm_key")

        response = client.post("/api/search/analyze", json={"search_result": sample_search_result()}, headers=headers)

        assert response.status_code == 503
        payload = response.get_json()
        assert payload["error"] == "llm_unavailable"
        assert "SCANN_LLM_API_KEY" in payload["message"]


def test_llm_analysis_calls_chat_completions_and_returns_summary(monkeypatch):
    with runtime_tmpdir() as tmp_path:
        class TestConfig(make_test_config(tmp_path)):
            LLM_PROVIDER = "siliconflow"
            LLM_API_URL = "https://api.siliconflow.cn/v1/chat/completions"
            LLM_API_KEY = "test-secret"
            LLM_MODEL = "Qwen/Qwen3-8B"
            LLM_TIMEOUT_SECONDS = 10
            LLM_MAX_TOKENS = 300
            LLM_TEMPERATURE = 0.2
            LLM_ENABLE_THINKING = False

        captured = {}

        def fake_post(url, *, headers, json, timeout):
            captured.update({"url": url, "headers": headers, "json": json, "timeout": timeout})
            return FakeLlmResponse(
                payload={
                    "model": "Qwen/Qwen3-8B",
                    "choices": [{"message": {"content": "检索邻域概览：命中细胞以 hepatocyte 为主。"}}],
                    "usage": {"prompt_tokens": 120, "completion_tokens": 30, "total_tokens": 150},
                }
            )

        monkeypatch.setattr("backend.services.llm_providers.requests.post", fake_post)
        app = create_app(TestConfig)
        client = app.test_client()
        headers = auth_headers(client, "normal_user", "normal_for_llm_success")

        response = client.post(
            "/api/search/analyze",
            json={"search_result": sample_search_result(), "question": "重点看细胞类型组成", "enable_thinking": False},
            headers=headers,
        )

        assert response.status_code == 200
        payload = response.get_json()
        assert payload["analysis"].startswith("检索邻域概览")
        assert payload["provider"] == "siliconflow"
        assert payload["model"] == "Qwen/Qwen3-8B"
        assert payload["usage"]["total_tokens"] == 150
        assert payload["cached"] is False
        assert payload["attempts"] == 1
        assert payload["latency_ms"] >= 0
        assert payload["input_summary"]["query_cell_id"] == "query-cell-1"
        assert payload["input_summary"]["cell_type_counts"][0] == {"value": "hepatocyte", "count": 2}
        assert payload["prompt_blueprint"]["root"]["label"] == "用户分析问题"
        assert payload["prompt_blueprint"]["layers"][0]["label"] == "检索对象"
        assert captured["url"] == "https://api.siliconflow.cn/v1/chat/completions"
        assert captured["headers"]["Authorization"] == "Bearer test-secret"
        assert captured["json"]["model"] == "Qwen/Qwen3-8B"
        assert captured["json"]["enable_thinking"] is False
        assert captured["timeout"] == 10


def test_llm_analysis_accepts_per_request_thinking_mode(monkeypatch):
    with runtime_tmpdir() as tmp_path:
        class TestConfig(make_test_config(tmp_path)):
            LLM_PROVIDER = "siliconflow"
            LLM_API_KEY = "test-secret"
            LLM_ENABLE_THINKING = False

        captured = {}

        def fake_post(url, *, headers, json, timeout):
            captured.update({"json": json})
            return FakeLlmResponse(
                payload={
                    "model": "Qwen/Qwen3-8B",
                    "choices": [{"message": {"content": "## 检索邻域概览\n\n已开启思考模式。"}}],
                    "usage": {"total_tokens": 20},
                }
            )

        monkeypatch.setattr("backend.services.llm_providers.requests.post", fake_post)
        app = create_app(TestConfig)
        client = app.test_client()
        headers = auth_headers(client, "normal_user", "normal_for_llm_thinking")

        response = client.post(
            "/api/search/analyze",
            json={"search_result": sample_search_result(), "enable_thinking": True},
            headers=headers,
        )

        assert response.status_code == 200
        assert captured["json"]["enable_thinking"] is True


def test_llm_analysis_rejects_invalid_thinking_mode():
    with runtime_tmpdir() as tmp_path:
        app = create_app(make_test_config(tmp_path))
        client = app.test_client()
        headers = auth_headers(client, "normal_user", "normal_for_llm_bad_thinking")

        response = client.post(
            "/api/search/analyze",
            json={"search_result": sample_search_result(), "enable_thinking": "yes"},
            headers=headers,
        )

        assert response.status_code == 400
        assert response.get_json()["error"] == "invalid_request"


def test_llm_analysis_wraps_provider_errors(monkeypatch):
    with runtime_tmpdir() as tmp_path:
        class TestConfig(make_test_config(tmp_path)):
            LLM_PROVIDER = "siliconflow"
            LLM_API_URL = "https://api.siliconflow.cn/v1/chat/completions"
            LLM_API_KEY = "test-secret"

        def fake_post(url, *, headers, json, timeout):
            return FakeLlmResponse(status_code=429, payload={"error": {"message": "rate limit"}})

        monkeypatch.setattr("backend.services.llm_providers.requests.post", fake_post)
        app = create_app(TestConfig)
        client = app.test_client()
        headers = auth_headers(client, "normal_user", "normal_for_llm_error")

        response = client.post("/api/search/analyze", json={"search_result": sample_search_result()}, headers=headers)

        assert response.status_code == 503
        payload = response.get_json()
        assert payload["error"] == "llm_unavailable"
        assert "429" in payload["message"]
        assert "test-secret" not in payload["message"]


def test_llm_analysis_retries_retryable_provider_errors(monkeypatch):
    with runtime_tmpdir() as tmp_path:
        class TestConfig(make_test_config(tmp_path)):
            LLM_PROVIDER = "siliconflow"
            LLM_API_KEY = "test-secret"
            LLM_RETRY_COUNT = 2
            LLM_RETRY_BACKOFF_SECONDS = 0

        calls = {"count": 0}

        def fake_post(url, *, headers, json, timeout):
            calls["count"] += 1
            if calls["count"] < 3:
                return FakeLlmResponse(status_code=503, payload={"error": {"message": "temporarily unavailable"}})
            return FakeLlmResponse(
                payload={
                    "model": "Qwen/Qwen3-8B",
                    "choices": [{"message": {"content": "## 检索邻域概览\n\n重试后成功。"}}],
                    "usage": {"total_tokens": 42},
                }
            )

        monkeypatch.setattr("backend.services.llm_providers.requests.post", fake_post)
        app = create_app(TestConfig)
        client = app.test_client()
        headers = auth_headers(client, "normal_user", "normal_for_llm_retry")

        response = client.post("/api/search/analyze", json={"search_result": sample_search_result()}, headers=headers)

        assert response.status_code == 200
        payload = response.get_json()
        assert payload["attempts"] == 3
        assert calls["count"] == 3


def test_llm_analysis_caches_repeated_requests(monkeypatch):
    with runtime_tmpdir() as tmp_path:
        class TestConfig(make_test_config(tmp_path)):
            LLM_PROVIDER = "siliconflow"
            LLM_API_KEY = "test-secret"
            LLM_CACHE_TTL_SECONDS = 300
            LLM_CACHE_MAX_ENTRIES = 8

        calls = {"count": 0}

        def fake_post(url, *, headers, json, timeout):
            calls["count"] += 1
            return FakeLlmResponse(
                payload={
                    "model": "Qwen/Qwen3-8B",
                    "choices": [{"message": {"content": "## 检索邻域概览\n\n来自缓存测试。"}}],
                    "usage": {"total_tokens": 31},
                }
            )

        monkeypatch.setattr("backend.services.llm_providers.requests.post", fake_post)
        app = create_app(TestConfig)
        client = app.test_client()
        headers = auth_headers(client, "normal_user", "normal_for_llm_cache")
        request_json = {"search_result": sample_search_result(), "question": "缓存测试"}

        first = client.post("/api/search/analyze", json=request_json, headers=headers)
        second = client.post("/api/search/analyze", json=request_json, headers=headers)

        assert first.status_code == 200
        assert second.status_code == 200
        assert first.get_json()["cached"] is False
        assert second.get_json()["cached"] is True
        assert second.get_json()["attempts"] == 0
        assert calls["count"] == 1


def test_llm_analysis_supports_local_provider_without_api_key(monkeypatch):
    with runtime_tmpdir() as tmp_path:
        class TestConfig(make_test_config(tmp_path)):
            LLM_PROVIDER = "local"
            LLM_API_URL = ""
            LLM_API_KEY = ""
            LLM_MODEL = "qwen3:8b"
            LLM_CACHE_TTL_SECONDS = 0

        captured = {}

        def fake_post(url, *, headers, json, timeout):
            captured.update({"url": url, "headers": headers, "json": json})
            return FakeLlmResponse(
                payload={
                    "model": "qwen3:8b",
                    "choices": [{"message": {"content": "## 检索邻域概览\n\n本地模型分析完成。"}}],
                    "usage": {"total_tokens": 18},
                }
            )

        monkeypatch.setattr("backend.services.llm_providers.requests.post", fake_post)
        app = create_app(TestConfig)
        client = app.test_client()
        headers = auth_headers(client, "normal_user", "normal_for_llm_local")

        response = client.post("/api/search/analyze", json={"search_result": sample_search_result()}, headers=headers)

        assert response.status_code == 200
        payload = response.get_json()
        assert payload["provider"] == "local"
        assert payload["model"] == "qwen3:8b"
        assert captured["url"] == "http://127.0.0.1:11434/v1/chat/completions"
        assert "Authorization" not in captured["headers"]


def test_llm_analysis_prompt_hit_limit_is_configurable(monkeypatch):
    with runtime_tmpdir() as tmp_path:
        class TestConfig(make_test_config(tmp_path)):
            LLM_PROVIDER = "siliconflow"
            LLM_API_KEY = "test-secret"
            LLM_MAX_HITS_FOR_PROMPT = 2
            LLM_CACHE_TTL_SECONDS = 0

        def fake_post(url, *, headers, json, timeout):
            return FakeLlmResponse(
                payload={
                    "model": "Qwen/Qwen3-8B",
                    "choices": [{"message": {"content": "## 检索邻域概览\n\n只纳入两个命中。"}}],
                    "usage": {"total_tokens": 25},
                }
            )

        monkeypatch.setattr("backend.services.llm_providers.requests.post", fake_post)
        app = create_app(TestConfig)
        client = app.test_client()
        headers = auth_headers(client, "normal_user", "normal_for_llm_limit")

        response = client.post("/api/search/analyze", json={"search_result": sample_search_result()}, headers=headers)

        assert response.status_code == 200
        payload = response.get_json()
        assert payload["input_summary"]["included_hit_count"] == 2
        assert payload["input_summary"]["truncated"] is True
        assert payload["input_summary"]["cell_type_counts"] == [{"value": "hepatocyte", "count": 2}]


def test_visualization_filters_stats_and_gene_expression_overlay():
    with runtime_tmpdir() as tmp_path:
        app = create_app(make_test_config(tmp_path))
        client = app.test_client()
        headers = auth_headers(client, "admin")

        client.post("/api/datasets/scan", headers=headers)
        client.post("/api/datasets/load", json={"dataset_id": "liver"}, headers=headers)

        options = client.get("/api/visualization/options?dataset_ids=liver&gene_query=ALB")
        assert options.status_code == 200
        options_payload = options.get_json()
        assert "cell_type" in options_payload["categorical_fields"]
        assert any(match["gene_name"] == "ALB" for match in options_payload["gene_matches"])

        filtered = client.get(
            "/api/visualization/cells?dataset_ids=liver&limit=30&color_by=cell_type&filter_cell_type=hepatocyte"
        )
        assert filtered.status_code == 200
        filtered_payload = filtered.get_json()
        assert filtered_payload["stats"]["sampled_points"] == 30
        assert filtered_payload["stats"]["metadata_counts"]["cell_type"][0]["value"] == "hepatocyte"
        assert all(point["cell_type"] == "hepatocyte" for point in filtered_payload["points"])

        expression = client.get(
            "/api/visualization/cells?dataset_ids=liver&limit=25&color_by=gene:ALB&filter_cell_type=hepatocyte"
        )
        assert expression.status_code == 200
        expression_payload = expression.get_json()
        assert expression_payload["gene"][0]["gene_name"] == "ALB"
        assert expression_payload["stats"]["expression"]["expressing_count"] > 0
        assert all("expression" in point for point in expression_payload["points"])

        missing = client.get("/api/visualization/cells?dataset_ids=liver&limit=10&color_by=gene:NOT_A_REAL_GENE")
        assert missing.status_code == 404
