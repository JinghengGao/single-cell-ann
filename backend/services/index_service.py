from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from threading import RLock
from typing import Any

import numpy as np

from backend.faiss_runtime import inspect_faiss_runtime
from backend.services.data_service import DatasetSnapshot, data_service


@dataclass(frozen=True)
class CellRef:
    dataset_id: str
    row_index: int

    def summary(self) -> dict[str, Any]:
        return {"dataset_id": self.dataset_id, "row_index": self.row_index}


@dataclass
class IndexSnapshot:
    index_id: str | None = None
    status: str = "not_built"
    index_type: str = "IVF_FLAT"
    metric: str = "l2"
    build_mode: str = "combined"
    mode: str = "unavailable"
    dataset_ids: list[str] = field(default_factory=list)
    vector_count: int = 0
    dimension: int = 0
    nlist: int = 0
    nprobe: int = 0
    index_path: str | None = None
    metadata_path: str | None = None
    build_duration_ms: float | None = None
    error: str | None = None

    @property
    def ready(self) -> bool:
        return self.status == "ready"

    def summary(self) -> dict[str, Any]:
        return {
            "index_id": self.index_id,
            "ready": self.ready,
            "status": self.status,
            "index_type": self.index_type,
            "metric": self.metric,
            "build_mode": self.build_mode,
            "mode": self.mode,
            "dataset_ids": self.dataset_ids,
            "dataset_count": len(self.dataset_ids),
            "vector_count": self.vector_count,
            "dimension": self.dimension,
            "nlist": self.nlist,
            "nprobe": self.nprobe,
            "index_path": self.index_path,
            "metadata_path": self.metadata_path,
            "build_duration_ms": self.build_duration_ms,
            "error": self.error,
        }


@dataclass
class IndexBundle:
    snapshot: IndexSnapshot
    cpu_index: Any
    search_index: Any
    index_to_cell: list[CellRef]
    gpu_resources: Any = None


class IndexService:
    def __init__(self) -> None:
        self._lock = RLock()
        self._snapshot = IndexSnapshot()
        self._indexes: dict[str, IndexBundle] = {}
        self._active_index_id: str | None = None
        self._faiss = None

    @property
    def snapshot(self) -> IndexSnapshot:
        if self._active_index_id and self._active_index_id in self._indexes:
            return self._indexes[self._active_index_id].snapshot
        return self._snapshot

    def status(self) -> dict[str, Any]:
        with self._lock:
            active = self.snapshot.summary()
            return {
                **active,
                "active_index_id": self._active_index_id,
                "indexes": [bundle.snapshot.summary() for bundle in self._indexes.values()],
            }

    def switch_index(self, index_id: str) -> dict[str, Any]:
        with self._lock:
            if index_id not in self._indexes:
                raise KeyError(f"Unknown index_id: {index_id}")
            self._active_index_id = index_id
            self._snapshot = self._indexes[index_id].snapshot
            return self.status()

    def load_index(self, index_dir: Path, index_id: str) -> dict[str, Any]:
        with self._lock:
            runtime = inspect_faiss_runtime()
            if not runtime.available:
                raise RuntimeError(runtime.error or "FAISS is not available")

            import faiss  # type: ignore

            safe_index_id = self._safe_index_id(index_id)
            index_path = index_dir / f"{safe_index_id}.faiss"
            metadata_path = index_dir / f"{safe_index_id}.meta.json"
            if not index_path.exists() or not metadata_path.exists():
                raise FileNotFoundError(f"index files not found for {safe_index_id}")

            cpu_index = faiss.read_index(str(index_path))
            with metadata_path.open("r", encoding="utf-8") as file:
                metadata = json.load(file)
            snapshot = IndexSnapshot(**metadata["snapshot"])
            index_to_cell = [CellRef(**item) for item in metadata["index_to_cell"]]
            bundle = IndexBundle(
                snapshot=snapshot,
                cpu_index=cpu_index,
                search_index=cpu_index,
                index_to_cell=index_to_cell,
            )
            self._indexes[safe_index_id] = bundle
            self._active_index_id = safe_index_id
            self._snapshot = snapshot
            self._faiss = faiss
            return self.status()

    def delete_index(self, index_dir: Path, index_id: str) -> dict[str, Any]:
        with self._lock:
            safe_index_id = self._safe_index_id(index_id)
            removed = self._indexes.pop(safe_index_id, None)
            index_path = index_dir / f"{safe_index_id}.faiss"
            metadata_path = index_dir / f"{safe_index_id}.meta.json"
            for path in (index_path, metadata_path):
                if path.exists():
                    path.unlink()
            if self._active_index_id == safe_index_id:
                self._active_index_id = next(iter(self._indexes), None)
                self._snapshot = self._indexes[self._active_index_id].snapshot if self._active_index_id else IndexSnapshot()
            return {
                "deleted": removed.snapshot.summary() if removed else {"index_id": safe_index_id},
                **self.status(),
            }

    def build_ivf_flat(
        self,
        index_dir: Path,
        nlist: int,
        nprobe: int,
        *,
        dataset_ids: list[str] | None = None,
        build_mode: str = "combined",
        metric: str = "l2",
        registry_path: Path | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            runtime = inspect_faiss_runtime()
            if not runtime.available:
                self._snapshot = IndexSnapshot(
                    status="error",
                    mode="unavailable",
                    error=runtime.error or "FAISS is not available",
                )
                raise RuntimeError(self._snapshot.error)

            import faiss  # type: ignore

            build_mode = (build_mode or "combined").lower()
            if build_mode not in {"combined", "separate"}:
                raise ValueError("mode must be combined or separate")
            metric = (metric or "l2").lower()
            if metric not in ("l2", "cosine", "ip"):
                raise ValueError("metric must be l2, cosine, or ip")

            snapshots = self._resolve_snapshots(dataset_ids or [], registry_path)
            if build_mode == "combined":
                bundle = self._build_combined_index(faiss, runtime, index_dir, snapshots, nlist, nprobe, metric=metric)
                self._indexes[bundle.snapshot.index_id] = bundle
                self._active_index_id = bundle.snapshot.index_id
                self._snapshot = bundle.snapshot
                return self.status()

            built = []
            for snapshot in snapshots:
                bundle = self._build_single_index(faiss, runtime, index_dir, snapshot, nlist, nprobe, metric=metric)
                self._indexes[bundle.snapshot.index_id] = bundle
                built.append(bundle.snapshot.summary())

            if built:
                self._active_index_id = built[0]["index_id"]
                self._snapshot = self._indexes[self._active_index_id].snapshot
            status = self.status()
            status["built_indexes"] = built
            return status

    def build_hnsw(
        self,
        index_dir: Path,
        *,
        dataset_ids: list[str] | None = None,
        build_mode: str = "combined",
        metric: str = "l2",
        M: int = 32,
        ef_construction: int = 200,
        ef_search: int = 64,
        registry_path: Path | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            runtime = inspect_faiss_runtime()
            if not runtime.available:
                self._snapshot = IndexSnapshot(status="error", mode="unavailable", error=runtime.error or "FAISS is not available")
                raise RuntimeError(self._snapshot.error)

            import faiss  # type: ignore

            build_mode = (build_mode or "combined").lower()
            if build_mode not in {"combined", "separate"}:
                raise ValueError("mode must be combined or separate")
            metric = (metric or "l2").lower()
            if metric not in ("l2", "cosine", "ip"):
                raise ValueError("metric must be l2, cosine, or ip")

            snapshots = self._resolve_snapshots(dataset_ids or [], registry_path)
            if build_mode == "combined":
                bundle = self._build_combined_hnsw(faiss, runtime, index_dir, snapshots, M, ef_construction, ef_search, metric=metric)
                self._indexes[bundle.snapshot.index_id] = bundle
                self._active_index_id = bundle.snapshot.index_id
                self._snapshot = bundle.snapshot
                return self.status()

            built = []
            for snapshot in snapshots:
                bundle = self._build_single_hnsw(faiss, runtime, index_dir, snapshot, M, ef_construction, ef_search, metric=metric)
                self._indexes[bundle.snapshot.index_id] = bundle
                built.append(bundle.snapshot.summary())
            if built:
                self._active_index_id = built[0]["index_id"]
                self._snapshot = self._indexes[self._active_index_id].snapshot
            status = self.status()
            status["built_indexes"] = built
            return status

    def search(self, query_vector: np.ndarray, top_k: int, index_id: str | None = None) -> tuple[np.ndarray, np.ndarray, IndexBundle]:
        bundle = self._active_bundle(index_id)
        query = np.ascontiguousarray(query_vector.reshape(1, -1).astype("float32", copy=False))
        # 当索引使用 cosine/ip 度量时，查询向量也需归一化
        metric = bundle.snapshot.metric
        if metric in ("cosine", "ip"):
            query = self._normalize_for_metric(query, metric)
        distances, indices = bundle.search_index.search(query, int(top_k))
        return distances[0], indices[0], bundle

    def _resolve_snapshots(self, dataset_ids: list[str], registry_path: Path | None) -> list[DatasetSnapshot]:
        clean_dataset_ids = [str(item).strip() for item in dataset_ids if str(item).strip()]
        if clean_dataset_ids:
            if registry_path is None:
                raise ValueError("registry_path is required when dataset_ids are used")
            return [data_service.get_snapshot(dataset_id, registry_path=registry_path) for dataset_id in clean_dataset_ids]

        active_snapshot = data_service.snapshot
        if active_snapshot.loaded:
            return [active_snapshot]
        raise RuntimeError("Dataset has not been loaded")

    def _build_combined_index(
        self,
        faiss: Any,
        runtime: Any,
        index_dir: Path,
        snapshots: list[DatasetSnapshot],
        nlist: int,
        nprobe: int,
        *,
        metric: str = "l2",
    ) -> IndexBundle:
        dimension = self._require_shared_dimension(snapshots)
        vectors = np.ascontiguousarray(np.vstack([snapshot.vectors for snapshot in snapshots]).astype("float32", copy=False))
        index_to_cell = [
            CellRef(dataset_id=snapshot.dataset_id, row_index=row_index)
            for snapshot in snapshots
            for row_index in range(snapshot.cell_count)
        ]
        dataset_ids = [snapshot.dataset_id for snapshot in snapshots]
        index_id = self._combined_index_id(dataset_ids)
        return self._build_index(
            faiss, runtime, index_dir, index_id, "combined", dataset_ids,
            vectors, dimension, index_to_cell, nlist, nprobe, metric=metric,
        )

    def _build_single_index(
        self,
        faiss: Any,
        runtime: Any,
        index_dir: Path,
        snapshot: DatasetSnapshot,
        nlist: int,
        nprobe: int,
        *,
        metric: str = "l2",
    ) -> IndexBundle:
        if snapshot.vectors is None:
            raise RuntimeError(f"Dataset has no vectors: {snapshot.dataset_id}")
        vectors = np.ascontiguousarray(snapshot.vectors.astype("float32", copy=False))
        index_to_cell = [CellRef(dataset_id=snapshot.dataset_id, row_index=row_index) for row_index in range(snapshot.cell_count)]
        index_id = self._safe_index_id(f"{snapshot.dataset_id}_ivf_flat")
        return self._build_index(
            faiss, runtime, index_dir, index_id, "separate", [snapshot.dataset_id],
            vectors, snapshot.vector_dim, index_to_cell, nlist, nprobe, metric=metric,
        )

    def _build_combined_hnsw(
        self, faiss: Any, runtime: Any, index_dir: Path,
        snapshots: list[DatasetSnapshot], M: int, ef_construction: int, ef_search: int,
        *, metric: str = "l2",
    ) -> IndexBundle:
        dimension = self._require_shared_dimension(snapshots)
        vectors = np.ascontiguousarray(np.vstack([s.vectors for s in snapshots]).astype("float32", copy=False))
        index_to_cell = [CellRef(dataset_id=s.dataset_id, row_index=i) for s in snapshots for i in range(s.cell_count)]
        dataset_ids = [s.dataset_id for s in snapshots]
        index_id = self._combined_index_id(dataset_ids).replace("ivf_flat", "hnsw")
        return self._build_hnsw_index(
            faiss, runtime, index_dir, index_id, "combined", dataset_ids,
            vectors, dimension, index_to_cell, M, ef_construction, ef_search, metric=metric,
        )

    def _build_single_hnsw(
        self, faiss: Any, runtime: Any, index_dir: Path,
        snapshot: DatasetSnapshot, M: int, ef_construction: int, ef_search: int,
        *, metric: str = "l2",
    ) -> IndexBundle:
        if snapshot.vectors is None:
            raise RuntimeError(f"Dataset has no vectors: {snapshot.dataset_id}")
        vectors = np.ascontiguousarray(snapshot.vectors.astype("float32", copy=False))
        index_to_cell = [CellRef(dataset_id=snapshot.dataset_id, row_index=i) for i in range(snapshot.cell_count)]
        index_id = self._safe_index_id(f"{snapshot.dataset_id}_hnsw")
        return self._build_hnsw_index(
            faiss, runtime, index_dir, index_id, "separate", [snapshot.dataset_id],
            vectors, snapshot.vector_dim, index_to_cell, M, ef_construction, ef_search, metric=metric,
        )

    @staticmethod
    def _faiss_metric(faiss: Any, metric: str) -> int:
        if metric == "cosine":
            return faiss.METRIC_INNER_PRODUCT
        elif metric == "ip":
            return faiss.METRIC_INNER_PRODUCT
        return faiss.METRIC_L2

    @staticmethod
    def _normalize_for_metric(vectors: np.ndarray, metric: str) -> np.ndarray:
        if metric in ("cosine", "ip"):
            import numpy as np
            norms = np.linalg.norm(vectors, axis=1, keepdims=True)
            norms = np.where(norms == 0, 1.0, norms)
            return vectors / norms
        return vectors

    def _build_index(
        self,
        faiss: Any,
        runtime: Any,
        index_dir: Path,
        index_id: str,
        build_mode: str,
        dataset_ids: list[str],
        vectors: np.ndarray,
        dimension: int,
        index_to_cell: list[CellRef],
        nlist: int,
        nprobe: int,
        *,
        metric: str = "l2",
    ) -> IndexBundle:
        vector_count = int(vectors.shape[0])
        effective_nlist = max(1, min(int(nlist), vector_count))
        effective_nprobe = max(1, min(int(nprobe), effective_nlist))
        faiss_metric = self._faiss_metric(faiss, metric)
        vectors = self._normalize_for_metric(vectors, metric)

        start = time.perf_counter()
        cpu_quantizer = faiss.IndexFlat(dimension, faiss_metric)
        cpu_index = faiss.IndexIVFFlat(cpu_quantizer, dimension, effective_nlist, faiss_metric)
        cpu_index.nprobe = effective_nprobe
        cpu_index.train(vectors)
        cpu_index.add(vectors)

        search_index = cpu_index
        gpu_resources = None
        faiss_mode = "cpu"
        if runtime.gpu_count > 0:
            try:
                gpu_resources = faiss.StandardGpuResources()
                search_index = faiss.index_cpu_to_gpu(gpu_resources, 0, cpu_index)
                search_index.nprobe = effective_nprobe
                faiss_mode = "gpu"
            except Exception:
                gpu_resources = None
                search_index = cpu_index
                faiss_mode = "cpu"

        search_index.search(vectors[:1], 1)

        index_dir.mkdir(parents=True, exist_ok=True)
        index_path = index_dir / f"{index_id}.faiss"
        metadata_path = index_dir / f"{index_id}.meta.json"
        faiss.write_index(cpu_index, str(index_path))

        duration_ms = (time.perf_counter() - start) * 1000
        self._faiss = faiss
        type_label = "IVF_FLAT"
        snapshot = IndexSnapshot(
            index_id=index_id,
            status="ready",
            index_type=type_label,
            metric=metric,
            build_mode=build_mode,
            mode=faiss_mode,
            dataset_ids=dataset_ids,
            vector_count=vector_count,
            dimension=dimension,
            nlist=effective_nlist,
            nprobe=effective_nprobe,
            index_path=str(index_path.resolve()),
            metadata_path=str(metadata_path.resolve()),
            build_duration_ms=round(duration_ms, 3),
            error=None,
        )
        self._write_index_metadata(metadata_path, snapshot, index_to_cell)
        return IndexBundle(
            snapshot=snapshot,
            cpu_index=cpu_index,
            search_index=search_index,
            gpu_resources=gpu_resources,
            index_to_cell=index_to_cell,
        )

    def _build_hnsw_index(
        self,
        faiss: Any,
        runtime: Any,
        index_dir: Path,
        index_id: str,
        build_mode: str,
        dataset_ids: list[str],
        vectors: np.ndarray,
        dimension: int,
        index_to_cell: list[CellRef],
        M: int,
        ef_construction: int,
        ef_search: int,
        *,
        metric: str = "l2",
    ) -> IndexBundle:
        faiss_metric = self._faiss_metric(faiss, metric)
        vectors = self._normalize_for_metric(vectors, metric)

        start = time.perf_counter()
        cpu_index = faiss.IndexHNSWFlat(dimension, max(4, int(M)), faiss_metric)
        cpu_index.hnsw.efConstruction = max(8, int(ef_construction))
        cpu_index.hnsw.efSearch = max(1, int(ef_search))
        cpu_index.add(vectors)

        search_index = cpu_index
        gpu_resources = None
        faiss_mode = "cpu"
        if runtime.gpu_count > 0:
            try:
                gpu_resources = faiss.StandardGpuResources()
                search_index = faiss.index_cpu_to_gpu(gpu_resources, 0, cpu_index)
                faiss_mode = "gpu"
            except Exception:
                gpu_resources = None
                search_index = cpu_index
                faiss_mode = "cpu"

        search_index.search(vectors[:1], 1)

        index_dir.mkdir(parents=True, exist_ok=True)
        index_path = index_dir / f"{index_id}.faiss"
        metadata_path = index_dir / f"{index_id}.meta.json"
        faiss.write_index(cpu_index, str(index_path))

        duration_ms = (time.perf_counter() - start) * 1000
        self._faiss = faiss
        snapshot = IndexSnapshot(
            index_id=index_id,
            status="ready",
            index_type="HNSW",
            metric=metric,
            build_mode=build_mode,
            mode=faiss_mode,
            dataset_ids=dataset_ids,
            vector_count=int(vectors.shape[0]),
            dimension=dimension,
            nlist=0,
            nprobe=ef_search,
            index_path=str(index_path.resolve()),
            metadata_path=str(metadata_path.resolve()),
            build_duration_ms=round(duration_ms, 3),
            error=None,
        )
        self._write_index_metadata(metadata_path, snapshot, index_to_cell)
        return IndexBundle(
            snapshot=snapshot,
            cpu_index=cpu_index,
            search_index=search_index,
            gpu_resources=gpu_resources,
            index_to_cell=index_to_cell,
        )

    def _active_bundle(self, index_id: str | None = None) -> IndexBundle:
        target_index_id = index_id or self._active_index_id
        if target_index_id is None or target_index_id not in self._indexes:
            raise RuntimeError("Index has not been built")
        return self._indexes[target_index_id]

    @staticmethod
    def _write_index_metadata(metadata_path: Path, snapshot: IndexSnapshot, index_to_cell: list[CellRef]) -> None:
        payload = {
            "snapshot": snapshot.__dict__,
            "index_to_cell": [cell_ref.summary() for cell_ref in index_to_cell],
        }
        with metadata_path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)

    @staticmethod
    def _require_shared_dimension(snapshots: list[DatasetSnapshot]) -> int:
        if not snapshots:
            raise RuntimeError("No datasets selected")
        dimensions = {snapshot.vector_dim for snapshot in snapshots}
        if len(dimensions) != 1:
            raise ValueError("Selected datasets must have the same PCA vector dimension")
        return dimensions.pop()

    @staticmethod
    def _combined_index_id(dataset_ids: list[str]) -> str:
        joined = "_".join(dataset_ids)
        digest = hashlib.sha1(joined.encode("utf-8")).hexdigest()[:8]
        if len(dataset_ids) == 1:
            return IndexService._safe_index_id(f"{dataset_ids[0]}_ivf_flat")
        return IndexService._safe_index_id(f"combined_{digest}_ivf_flat")

    @staticmethod
    def _safe_index_id(value: str) -> str:
        return re.sub(r"[^a-zA-Z0-9_]+", "_", value).strip("_").lower()


index_service = IndexService()
