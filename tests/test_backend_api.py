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

        separate = client.post(
            "/api/index/build",
            json={"dataset_ids": ["liver"], "mode": "separate", "nlist": 64, "nprobe": 8},
            headers=researcher_headers,
        )
        assert separate.status_code == 200
        assert separate.get_json()["built_indexes"][0]["build_mode"] == "separate"


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

        monkeypatch.setattr("backend.services.llm_analysis_service.requests.post", fake_post)
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

        monkeypatch.setattr("backend.services.llm_analysis_service.requests.post", fake_post)
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
            LLM_API_URL = "https://api.siliconflow.cn/v1/chat/completions"
            LLM_API_KEY = "test-secret"

        def fake_post(url, *, headers, json, timeout):
            return FakeLlmResponse(status_code=429, payload={"error": {"message": "rate limit"}})

        monkeypatch.setattr("backend.services.llm_analysis_service.requests.post", fake_post)
        app = create_app(TestConfig)
        client = app.test_client()
        headers = auth_headers(client, "normal_user", "normal_for_llm_error")

        response = client.post("/api/search/analyze", json={"search_result": sample_search_result()}, headers=headers)

        assert response.status_code == 503
        payload = response.get_json()
        assert payload["error"] == "llm_unavailable"
        assert "429" in payload["message"]
        assert "test-secret" not in payload["message"]


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
