from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.app import create_app


def assert_ok(response, label: str):
    if response.status_code >= 400:
        print(f"[FAIL] {label}: {response.status_code} {response.get_json()}")
        sys.exit(1)
    print(f"[OK] {label}: {response.status_code}")
    return response.get_json()


def auth_headers(client) -> dict[str, str]:
    username = "smoke_admin"
    password = "secret123"
    client.post("/api/auth/register", json={"username": username, "password": password, "role": "admin"})
    login = assert_ok(client.post("/api/auth/login", json={"username": username, "password": password}), "login")
    return {"Authorization": f"Bearer {login['token']}"}


def main() -> None:
    app = create_app()
    client = app.test_client()

    health = assert_ok(client.get("/api/health"), "health")
    print("FAISS:", health["faiss"])
    headers = auth_headers(client)

    dataset = assert_ok(client.post("/api/datasets/load", json={}, headers=headers), "load dataset")
    print("Dataset:", dataset["cell_count"], "cells,", dataset["vector_dim"], "dimensions")

    vis = assert_ok(client.get("/api/visualization/cells?limit=10"), "visualization sample")
    print("Visualization points:", len(vis["points"]))
    vis_options = assert_ok(client.get("/api/visualization/options?dataset_ids=liver&gene_query=ALB"), "visualization options")
    print("Gene matches:", len(vis_options["gene_matches"]))
    gene_vis = assert_ok(
        client.get("/api/visualization/cells?dataset_ids=liver&limit=10&color_by=gene:ALB"),
        "visualization gene overlay",
    )
    print("Expression summary:", gene_vis["stats"]["expression"])

    if not health["faiss"]["available"]:
        print("[SKIP] index/search: FAISS is unavailable in this Python environment")
        return

    index = assert_ok(client.post("/api/index/build", json={}, headers=headers), "build index")
    print("Index:", index["index_type"], index["mode"], index["vector_count"], "vectors")

    sample_cell_id = dataset["sample_cell_ids"][0]
    result = assert_ok(client.post("/api/search", json={"cell_id": sample_cell_id, "top_k": 5}, headers=headers), "search")
    print("Query:", sample_cell_id)
    print("Result count:", result["result_count"])
    print("Query time:", result["query_time_ms"], "ms")
    if result["result_count"] <= 0:
        print("[FAIL] search returned no hits")
        sys.exit(1)


if __name__ == "__main__":
    main()
