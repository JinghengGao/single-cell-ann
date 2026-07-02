from __future__ import annotations

import re
from collections import Counter
from typing import Any

import numpy as np

from backend.services.data_service import DatasetSnapshot, data_service
from backend.services.index_service import index_service
from backend.services.llm_analysis_service import LlmAnalysisError, llm_analysis_service
from backend.services.search_service import search_service


METADATA_FIELDS = ("cell_type", "disease", "AgeGroup", "tissue")
FIELD_ALIASES = {
    "cell_type": {
        "hepatocyte": ("hepatocyte", "肝细胞"),
        "cholangiocyte": ("cholangiocyte", "胆管"),
        "macrophage": ("macrophage", "巨噬"),
        "t cell": ("t cell", "t细胞", "t 细胞"),
        "b cell": ("b cell", "b细胞", "b 细胞"),
    },
    "tissue": {
        "liver": ("liver", "肝", "肝脏"),
    },
    "disease": {
        "normal": ("normal", "healthy", "健康", "正常"),
        "tumor": ("tumor", "cancer", "肿瘤", "癌"),
    },
}


class RagQueryError(ValueError):
    """Raised when a natural-language query cannot be grounded in the data."""


class RagService:
    def answer_question(
        self,
        question: str,
        config: dict[str, Any],
        *,
        top_k: int,
        dataset_ids: list[str] | None = None,
        index_id: str | None = None,
        enable_thinking: bool | None = None,
    ) -> dict[str, Any]:
        clean_question = question.strip()
        if not clean_question:
            raise RagQueryError("question is required")

        registry_path = config["DATASET_REGISTRY_PATH"]
        resolved_dataset_ids = self._resolve_dataset_ids(dataset_ids)
        snapshots = [data_service.get_snapshot(dataset_id, registry_path=registry_path) for dataset_id in resolved_dataset_ids]
        filters = self._extract_metadata_filters(clean_question, snapshots)
        explicit_cell = self._extract_cell_id(clean_question, snapshots)
        retrieval_plan: dict[str, Any] = {
            "question": clean_question,
            "dataset_ids": resolved_dataset_ids,
            "index_id": index_id or index_service.snapshot.index_id,
            "top_k": top_k,
            "metadata_filters": filters,
            "strategy": "cell_id" if explicit_cell else "metadata_centroid",
        }

        if explicit_cell:
            snapshot, row_index = explicit_cell
            retrieval_plan.update({"cell_id": snapshot.cell_ids[row_index], "dataset_id": snapshot.dataset_id})
            search_result = search_service.search_by_cell_id(
                snapshot.cell_ids[row_index],
                top_k,
                config["LOG_DIR"],
                registry_path=registry_path,
                dataset_id=snapshot.dataset_id,
                index_id=index_id,
                metadata_filters=filters or None,
            )
        else:
            query_vector, representative_cell, match_summary = self._representative_vector(snapshots, filters)
            retrieval_plan.update(
                {
                    "representative_cell": representative_cell,
                    "matched_cells": match_summary["matched_cells"],
                    "matched_by_dataset": match_summary["matched_by_dataset"],
                }
            )
            search_result = search_service.search_by_vector(
                query_vector.tolist(),
                top_k,
                config["LOG_DIR"],
                registry_path=registry_path,
                index_id=index_id,
                metadata_filters=filters or None,
            )
            search_result["query_cell"] = representative_cell
            search_result["query"] = {
                **search_result.get("query", {}),
                "cell_id": representative_cell["cell_id"],
                "dataset_id": representative_cell["dataset_id"],
                "rag_strategy": "metadata_centroid",
                "metadata_filters": filters,
            }

        analysis = llm_analysis_service.analyze_search_result(
            search_result,
            config,
            user_question=(
                f"用户自然语言问题：{clean_question}\n"
                f"检索计划：{retrieval_plan}\n"
                "请先说明你使用了哪些检索证据，再回答问题。"
            ),
            enable_thinking=enable_thinking,
        )
        return {
            "question": clean_question,
            "retrieval_plan": retrieval_plan,
            "search_result": search_result,
            "answer": analysis["analysis"],
            "provider": analysis.get("provider"),
            "model": analysis.get("model"),
            "usage": analysis.get("usage") or {},
            "latency_ms": analysis.get("latency_ms"),
            "cached": analysis.get("cached", False),
            "attempts": analysis.get("attempts", 0),
        }

    @staticmethod
    def _resolve_dataset_ids(dataset_ids: list[str] | None) -> list[str]:
        clean = [str(item).strip() for item in (dataset_ids or []) if str(item).strip()]
        if clean:
            return clean
        active_index = index_service.snapshot
        if active_index.ready and active_index.dataset_ids:
            return active_index.dataset_ids
        active_snapshot = data_service.snapshot
        if active_snapshot.loaded:
            return [active_snapshot.dataset_id]
        raise RuntimeError("No loaded dataset or active index is available for RAG retrieval")

    @staticmethod
    def _extract_cell_id(question: str, snapshots: list[DatasetSnapshot]) -> tuple[DatasetSnapshot, int] | None:
        tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9_.:\-]{5,}", question)
        for token in tokens:
            for snapshot in snapshots:
                row_index = snapshot.cell_id_to_index.get(token)
                if row_index is not None:
                    return snapshot, int(row_index)
        return None

    def _extract_metadata_filters(self, question: str, snapshots: list[DatasetSnapshot]) -> dict[str, str]:
        normalized_question = question.casefold()
        filters: dict[str, str] = {}
        for field_name in METADATA_FIELDS:
            values = self._candidate_values(field_name, snapshots)
            alias_match = self._match_alias(field_name, normalized_question, values)
            if alias_match:
                filters[field_name] = alias_match
                continue
            for value in sorted(values, key=len, reverse=True):
                if len(value) < 2:
                    continue
                if value.casefold() in normalized_question:
                    filters[field_name] = value
                    break
        return filters

    @staticmethod
    def _candidate_values(field_name: str, snapshots: list[DatasetSnapshot]) -> set[str]:
        values: set[str] = set()
        for snapshot in snapshots:
            values.update(str(value) for value in snapshot.metadata.get(field_name, []) if str(value).strip())
        return values

    @staticmethod
    def _match_alias(field_name: str, normalized_question: str, values: set[str]) -> str | None:
        aliases = FIELD_ALIASES.get(field_name, {})
        for canonical, terms in aliases.items():
            if not any(term.casefold() in normalized_question for term in terms):
                continue
            for value in values:
                if value.casefold() == canonical.casefold() or canonical.casefold() in value.casefold():
                    return value
        return None

    def _representative_vector(
        self,
        snapshots: list[DatasetSnapshot],
        filters: dict[str, str],
    ) -> tuple[np.ndarray, dict[str, Any], dict[str, Any]]:
        if not filters:
            snapshot = snapshots[0]
            return snapshot.vectors[0], data_service.get_cell_metadata(0, dataset_id=snapshot.dataset_id), {
                "matched_cells": snapshot.cell_count,
                "matched_by_dataset": {snapshot.dataset_id: snapshot.cell_count},
            }

        vectors: list[np.ndarray] = []
        refs: list[tuple[DatasetSnapshot, int]] = []
        counts: Counter[str] = Counter()
        for snapshot in snapshots:
            mask = np.ones(snapshot.cell_count, dtype=bool)
            for field_name, expected in filters.items():
                values = np.asarray(snapshot.metadata.get(field_name, []), dtype=object)
                if values.size != snapshot.cell_count:
                    mask &= False
                    continue
                mask &= np.char.lower(values.astype(str)) == expected.casefold()
            row_indices = np.flatnonzero(mask)
            if row_indices.size:
                counts[snapshot.dataset_id] = int(row_indices.size)
                sample_indices = row_indices[: min(5000, row_indices.size)]
                vectors.append(snapshot.vectors[sample_indices].astype("float32", copy=False))
                refs.extend((snapshot, int(idx)) for idx in sample_indices[:200])

        if not vectors:
            raise RagQueryError(f"No cells matched extracted filters: {filters}")

        matrix = np.vstack(vectors)
        centroid = matrix.mean(axis=0).astype("float32", copy=False)
        representative_snapshot, representative_idx = self._closest_ref_to_centroid(refs, centroid)
        representative_cell = data_service.get_cell_metadata(
            representative_idx,
            dataset_id=representative_snapshot.dataset_id,
        )
        return centroid, representative_cell, {
            "matched_cells": int(sum(counts.values())),
            "matched_by_dataset": dict(counts),
        }

    @staticmethod
    def _closest_ref_to_centroid(refs: list[tuple[DatasetSnapshot, int]], centroid: np.ndarray) -> tuple[DatasetSnapshot, int]:
        best_ref = refs[0]
        best_distance = float("inf")
        for snapshot, row_index in refs:
            diff = snapshot.vectors[row_index].astype("float32", copy=False) - centroid
            distance = float(np.dot(diff, diff))
            if distance < best_distance:
                best_ref = (snapshot, row_index)
                best_distance = distance
        return best_ref


rag_service = RagService()
