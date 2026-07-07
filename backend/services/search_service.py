from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.services.data_service import data_service
from backend.services.index_service import index_service


_METADATA_FILTER_FIELDS = ("cell_type", "disease", "AgeGroup", "tissue")


class SearchService:
    """封装检索业务逻辑，统一输出 Top-K 结果、评测指标和查询日志。"""

    # ------------------------------------------------------------------
    # ANN 检索
    # ------------------------------------------------------------------
    def search_by_cell_id(
        self,
        cell_id: str,
        top_k: int,
        log_dir: Path,
        *,
        registry_path: Path,
        dataset_id: str | None = None,
        index_id: str | None = None,
        metadata_filters: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        request_log: dict[str, Any] = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "query_type": "ANN",
            "query_object": cell_id,
            "dataset_id": dataset_id,
            "index_id": index_id,
            "top_k": top_k,
            "metadata_filters": metadata_filters or {},
            "status": "failed",
        }

        try:
            if not cell_id:
                raise ValueError("cell_id is required")
            if top_k <= 0:
                raise ValueError("top_k must be positive")

            target_index = self._resolve_search_index(index_id, dataset_id)

            query_snapshot, query_row_index = data_service.resolve_cell(
                cell_id,
                target_index.dataset_ids,
                registry_path=registry_path,
                dataset_id=dataset_id,
            )
            query_vector = query_snapshot.vectors[query_row_index]
            # 多取一批候选，避免条件过滤后 Top-K 数量不足。
            fetch_k = max(top_k * 3, top_k + 50)
            distances, indices, bundle = index_service.search(query_vector, fetch_k, index_id)

            hits, scanned = self._collect_hits(
                distances, indices, bundle, query_snapshot, cell_id, top_k,
                registry_path=registry_path,
                metadata_filters=metadata_filters,
            )
            elapsed_ms = (time.perf_counter() - started) * 1000

            result = {
                "query": {
                    "cell_id": cell_id,
                    "dataset_id": query_snapshot.dataset_id,
                    "index_id": bundle.snapshot.index_id,
                    "top_k": top_k,
                    "metadata_filters": metadata_filters or {},
                },
                "query_cell": data_service.get_cell_metadata(
                    query_row_index,
                    dataset_id=query_snapshot.dataset_id,
                    registry_path=registry_path,
                ),
                "query_time_ms": round(elapsed_ms, 3),
                "scanned_candidates": scanned,
                "index": bundle.snapshot.summary(),
                "result_count": len(hits),
                "hits": hits,
            }

            request_log.update(
                {
                    "status": "success",
                    "latency_ms": result["query_time_ms"],
                    "result_count": len(hits),
                    "scanned_candidates": scanned,
                    "index_id": bundle.snapshot.index_id,
                    "index_mode": bundle.snapshot.mode,
                }
            )
            return result
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - started) * 1000
            request_log.update(
                {
                    "latency_ms": round(elapsed_ms, 3),
                    "result_count": 0,
                    "error": str(exc),
                    "index_mode": index_service.snapshot.mode,
                }
            )
            raise
        finally:
            self._write_query_log(log_dir, request_log)

    # ------------------------------------------------------------------
    # 向量检索
    # ------------------------------------------------------------------
    def search_by_vector(
        self,
        query_vector_values: list[float],
        top_k: int,
        log_dir: Path,
        *,
        registry_path: Path,
        index_id: str | None = None,
        metadata_filters: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        request_log: dict[str, Any] = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "query_type": "ANN_VECTOR",
            "query_object": f"vector:{len(query_vector_values)}d",
            "dataset_id": None,
            "index_id": index_id,
            "top_k": top_k,
            "metadata_filters": metadata_filters or {},
            "status": "failed",
        }

        try:
            if top_k <= 0:
                raise ValueError("top_k must be positive")
            target_index = self._resolve_search_index(index_id)

            import numpy as np

            query_vector = np.asarray(query_vector_values, dtype="float32")
            if query_vector.ndim != 1 or query_vector.shape[0] != target_index.dimension:
                raise ValueError(f"query_vector dimension must be {target_index.dimension}")

            fetch_k = max(top_k * 3, top_k + 50)
            distances, indices, bundle = index_service.search(query_vector, fetch_k, index_id)
            hits, scanned = self._collect_hits(
                distances,
                indices,
                bundle,
                None,
                None,
                top_k,
                registry_path=registry_path,
                metadata_filters=metadata_filters,
            )
            elapsed_ms = (time.perf_counter() - started) * 1000
            result = {
                "query": {
                    "query_type": "vector",
                    "dimension": int(query_vector.shape[0]),
                    "index_id": bundle.snapshot.index_id,
                    "top_k": top_k,
                    "metadata_filters": metadata_filters or {},
                },
                "query_cell": None,
                "query_time_ms": round(elapsed_ms, 3),
                "scanned_candidates": scanned,
                "index": bundle.snapshot.summary(),
                "result_count": len(hits),
                "hits": hits,
            }
            request_log.update(
                {
                    "status": "success",
                    "latency_ms": result["query_time_ms"],
                    "result_count": len(hits),
                    "scanned_candidates": scanned,
                    "index_id": bundle.snapshot.index_id,
                    "index_mode": bundle.snapshot.mode,
                }
            )
            return result
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - started) * 1000
            request_log.update({"latency_ms": round(elapsed_ms, 3), "result_count": 0, "error": str(exc)})
            raise
        finally:
            self._write_query_log(log_dir, request_log)

    # ------------------------------------------------------------------
    # 精确检索 (暴力 L2)
    # ------------------------------------------------------------------
    def exact_search_by_cell_id(
        self,
        cell_id: str,
        top_k: int,
        log_dir: Path,
        *,
        registry_path: Path,
        dataset_id: str | None = None,
        index_id: str | None = None,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        request_log: dict[str, Any] = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "query_type": "exact",
            "query_object": cell_id,
            "dataset_id": dataset_id,
            "top_k": top_k,
            "status": "failed",
        }

        try:
            if not cell_id:
                raise ValueError("cell_id is required")
            if top_k <= 0:
                raise ValueError("top_k must be positive")
            target_index = self._resolve_search_index(index_id, dataset_id)

            import numpy as np

            query_snapshot, query_row_index = data_service.resolve_cell(
                cell_id,
                target_index.dataset_ids,
                registry_path=registry_path,
                dataset_id=dataset_id,
            )
            query_vector = query_snapshot.vectors[query_row_index].astype("float32", copy=False)

            # 收集目标索引覆盖的所有数据集向量，用作 ANN 结果的精确基准。
            all_vectors_parts = [query_snapshot.vectors.astype("float32", copy=False)]
            cell_refs = [(query_snapshot.dataset_id, i) for i in range(query_snapshot.cell_count)]
            for sid in target_index.dataset_ids:
                if sid == query_snapshot.dataset_id:
                    continue
                snap = data_service.get_snapshot(sid, registry_path=registry_path)
                all_vectors_parts.append(snap.vectors.astype("float32", copy=False))
                cell_refs.extend((sid, i) for i in range(snap.cell_count))

            all_vectors = np.concatenate(all_vectors_parts, axis=0)
            diffs = all_vectors - query_vector
            l2_distances = np.sqrt(np.sum(diffs * diffs, axis=1))
            # 排除查询细胞自身，因此多取少量候选防止结果不足。
            sorted_indices = np.argsort(l2_distances)[: top_k + 2]

            hits = []
            for idx in sorted_indices:
                sid, row = cell_refs[int(idx)]
                meta = data_service.get_cell_metadata(row, dataset_id=sid, registry_path=registry_path)
                if meta["dataset_id"] == query_snapshot.dataset_id and meta["cell_id"] == cell_id:
                    continue
                hits.append(self._make_hit(len(hits) + 1, meta, float(l2_distances[int(idx)])))
                if len(hits) >= top_k:
                    break

            elapsed_ms = (time.perf_counter() - started) * 1000
            result = {
                "query": {"cell_id": cell_id, "dataset_id": query_snapshot.dataset_id, "top_k": top_k},
                "query_cell": data_service.get_cell_metadata(query_row_index, dataset_id=query_snapshot.dataset_id, registry_path=registry_path),
                "query_time_ms": round(elapsed_ms, 3),
                "index": {"index_type": "exact_flat_l2", "metric": "l2"},
                "result_count": len(hits),
                "hits": hits,
            }
            request_log.update({"status": "success", "latency_ms": elapsed_ms, "result_count": len(hits)})
            return result
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - started) * 1000
            request_log.update({"latency_ms": round(elapsed_ms, 3), "result_count": 0, "error": str(exc)})
            raise
        finally:
            self._write_query_log(log_dir, request_log)

    # ------------------------------------------------------------------
    # ANN vs Exact 对比评测
    # ------------------------------------------------------------------
    def compare_search(
        self,
        cell_id: str,
        top_k: int,
        log_dir: Path,
        *,
        registry_path: Path,
        dataset_id: str | None = None,
        index_id: str | None = None,
    ) -> dict[str, Any]:
        """同时执行 ANN 和精确检索，返回 Recall、重叠结果和加速比。"""
        started = time.perf_counter()

        ann_result = self.search_by_cell_id(
            cell_id, top_k, log_dir,
            registry_path=registry_path,
            dataset_id=dataset_id,
            index_id=index_id,
        )
        exact_result = self.exact_search_by_cell_id(
            cell_id, top_k, log_dir,
            registry_path=registry_path,
            dataset_id=dataset_id,
            index_id=index_id,
        )

        ann_hit_ids = {h["cell_id"] for h in ann_result["hits"]}
        exact_hit_ids = {h["cell_id"] for h in exact_result["hits"]}
        overlap_ids = ann_hit_ids & exact_hit_ids
        recall = len(overlap_ids) / len(exact_hit_ids) if exact_hit_ids else 0

        # 按精确检索排名记录 ANN 命中位置，便于判断召回质量。
        exact_rank_map = {h["cell_id"]: h["rank"] for h in exact_result["hits"]}
        ann_overlap_ranks = sorted(exact_rank_map[cid] for cid in overlap_ids)

        elapsed_ms = (time.perf_counter() - started) * 1000
        result = {
            "query": ann_result["query"],
            "query_cell": ann_result["query_cell"],
            "total_elapsed_ms": round(elapsed_ms, 3),
            "ann": {
                "query_time_ms": ann_result["query_time_ms"],
                "result_count": ann_result["result_count"],
                "index": ann_result.get("index", {}),
                "hits": ann_result["hits"],
            },
            "exact": {
                "query_time_ms": exact_result["query_time_ms"],
                "result_count": exact_result["result_count"],
                "hits": exact_result["hits"],
            },
            "evaluation": {
                "recall": round(recall, 4),
                "overlap_count": len(overlap_ids),
                "ann_unique": len(ann_hit_ids - exact_hit_ids),
                "exact_unique": len(exact_hit_ids - ann_hit_ids),
                "ann_overlap_ranks": ann_overlap_ranks,
                "speedup": round(exact_result["query_time_ms"] / ann_result["query_time_ms"], 2) if ann_result["query_time_ms"] > 0 else 0,
            },
        }
        self._write_benchmark_log(
            log_dir,
            {
                "created_at": datetime.now(timezone.utc).isoformat(),
                "benchmark_type": "compare",
                "index_id": ann_result["query"].get("index_id"),
                "dataset_id": ann_result["query"].get("dataset_id"),
                "top_k": top_k,
                "recall": result["evaluation"]["recall"],
                "ann_latency_ms": ann_result["query_time_ms"],
                "exact_latency_ms": exact_result["query_time_ms"],
                "speedup": result["evaluation"]["speedup"],
            },
        )
        return result

    # ------------------------------------------------------------------
    # 批量检索
    # ------------------------------------------------------------------
    def batch_search(
        self,
        cell_ids: list[str],
        top_k: int,
        log_dir: Path,
        *,
        registry_path: Path,
        dataset_id: str | None = None,
        index_id: str | None = None,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        results = []
        errors = []
        total_hits = 0
        for cid in cell_ids:
            try:
                r = self.search_by_cell_id(
                    str(cid).strip(), top_k, log_dir,
                    registry_path=registry_path,
                    dataset_id=dataset_id,
                    index_id=index_id,
                )
                results.append(r)
                total_hits += r["result_count"]
            except Exception as exc:
                errors.append({"cell_id": cid, "error": str(exc)})

        elapsed_ms = (time.perf_counter() - started) * 1000
        qps = len(results) / (elapsed_ms / 1000) if elapsed_ms > 0 else 0
        latencies = [r["query_time_ms"] for r in results]
        sorted_lat = sorted(latencies) if latencies else [0]
        p50_idx = max(0, int(len(sorted_lat) * 0.5) - 1)
        p99_idx = max(0, int(len(sorted_lat) * 0.99) - 1)

        result = {
            "batch_query_time_ms": round(elapsed_ms, 3),
            "total_queries": len(cell_ids),
            "successful": len(results),
            "failed": len(errors),
            "total_hits": total_hits,
            "qps": round(qps, 2),
            "latency_avg_ms": round(sum(latencies) / len(latencies), 3) if latencies else 0,
            "latency_p50_ms": round(sorted_lat[p50_idx], 3),
            "latency_p99_ms": round(sorted_lat[p99_idx], 3),
            "latency_min_ms": round(min(latencies), 3) if latencies else 0,
            "latency_max_ms": round(max(latencies), 3) if latencies else 0,
            "results": results,
            "errors": errors,
        }
        self._write_benchmark_log(
            log_dir,
            {
                "created_at": datetime.now(timezone.utc).isoformat(),
                "benchmark_type": "batch",
                "index_id": index_id,
                "dataset_id": dataset_id,
                "top_k": top_k,
                "total_queries": len(cell_ids),
                "successful": len(results),
                "failed": len(errors),
                "qps": result["qps"],
                "latency_avg_ms": result["latency_avg_ms"],
                "latency_p50_ms": result["latency_p50_ms"],
                "latency_p99_ms": result["latency_p99_ms"],
            },
        )
        return result

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------
    def _resolve_search_index(self, index_id: str | None = None, dataset_id: str | None = None):
        target_index = index_service.snapshot_for(index_id)
        if not target_index.ready:
            raise RuntimeError("Index has not been built")
        if dataset_id and dataset_id not in target_index.dataset_ids:
            index_label = target_index.index_id or index_id or "active index"
            raise ValueError(f"dataset_id '{dataset_id}' is not included in index '{index_label}'")
        return target_index

    def _collect_hits(
        self,
        distances,
        indices,
        bundle,
        query_snapshot,
        cell_id: str | None,
        top_k: int,
        *,
        registry_path: Path,
        metadata_filters: dict[str, str] | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        hits = []
        scanned = 0
        for distance, idx in zip(distances.tolist(), indices.tolist()):
            if idx < 0:
                continue
            if int(idx) >= len(bundle.index_to_cell):
                continue
            scanned += 1
            cell_ref = bundle.index_to_cell[int(idx)]
            meta = data_service.get_cell_metadata(
                cell_ref.row_index,
                dataset_id=cell_ref.dataset_id,
                registry_path=registry_path,
            )
            if query_snapshot is not None and meta["dataset_id"] == query_snapshot.dataset_id and meta["cell_id"] == cell_id:
                continue
            if not self._match_filters(meta, metadata_filters):
                continue
            hits.append(self._make_hit(len(hits) + 1, meta, float(distance)))
            if len(hits) >= top_k:
                break
        return hits, scanned

    @staticmethod
    def _make_hit(rank: int, meta: dict[str, Any], distance: float) -> dict[str, Any]:
        return {
            "rank": rank,
            "dataset_id": meta["dataset_id"],
            "dataset_name": meta["dataset_name"],
            "cell_id": meta["cell_id"],
            "distance": distance,
            "similarity": float(1.0 / (1.0 + max(distance, 0.0))),
            "cell_type": meta.get("cell_type"),
            "disease": meta.get("disease"),
            "AgeGroup": meta.get("AgeGroup"),
            "tissue": meta.get("tissue"),
            "umap": meta.get("umap"),
        }

    @staticmethod
    def _match_filters(meta: dict[str, Any], filters: dict[str, str] | None) -> bool:
        if not filters:
            return True
        for field, expected in filters.items():
            actual = str(meta.get(field) or "").strip().lower()
            if actual != expected.strip().lower():
                return False
        return True

    @staticmethod
    def _write_query_log(log_dir: Path, record: dict[str, Any]) -> None:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "query_log.jsonl"
        with log_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")

    @staticmethod
    def _write_benchmark_log(log_dir: Path, record: dict[str, Any]) -> None:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "benchmark_results.jsonl"
        with log_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")


search_service = SearchService()
