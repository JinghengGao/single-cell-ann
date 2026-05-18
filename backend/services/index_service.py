from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Any

import numpy as np

from backend.faiss_runtime import inspect_faiss_runtime
from backend.services.data_service import data_service


@dataclass
class IndexSnapshot:
    status: str = "not_built"
    index_type: str = "IVF_FLAT"
    metric: str = "l2"
    mode: str = "unavailable"
    vector_count: int = 0
    dimension: int = 0
    nlist: int = 0
    nprobe: int = 0
    index_path: str | None = None
    build_duration_ms: float | None = None
    error: str | None = None

    @property
    def ready(self) -> bool:
        return self.status == "ready"

    def summary(self) -> dict[str, Any]:
        return {
            "ready": self.ready,
            "status": self.status,
            "index_type": self.index_type,
            "metric": self.metric,
            "mode": self.mode,
            "vector_count": self.vector_count,
            "dimension": self.dimension,
            "nlist": self.nlist,
            "nprobe": self.nprobe,
            "index_path": self.index_path,
            "build_duration_ms": self.build_duration_ms,
            "error": self.error,
        }


class IndexService:
    def __init__(self) -> None:
        self._lock = RLock()
        self._snapshot = IndexSnapshot()
        self._cpu_index = None
        self._search_index = None
        self._gpu_resources = None
        self._faiss = None

    @property
    def snapshot(self) -> IndexSnapshot:
        return self._snapshot

    def build_ivf_flat(self, index_dir: Path, nlist: int, nprobe: int) -> dict[str, Any]:
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

            dataset = data_service.snapshot
            if not dataset.loaded or dataset.vectors is None:
                self._snapshot = IndexSnapshot(status="error", error="Dataset has not been loaded")
                raise RuntimeError("Dataset has not been loaded")

            vectors = np.ascontiguousarray(dataset.vectors.astype("float32", copy=False))
            vector_count, dimension = vectors.shape
            effective_nlist = max(1, min(int(nlist), vector_count))
            effective_nprobe = max(1, min(int(nprobe), effective_nlist))

            start = time.perf_counter()
            cpu_quantizer = faiss.IndexFlatL2(dimension)
            cpu_index = faiss.IndexIVFFlat(cpu_quantizer, dimension, effective_nlist, faiss.METRIC_L2)
            cpu_index.nprobe = effective_nprobe
            cpu_index.train(vectors)
            cpu_index.add(vectors)

            search_index = cpu_index
            mode = "cpu"
            if runtime.gpu_count > 0:
                try:
                    resources = faiss.StandardGpuResources()
                    search_index = faiss.index_cpu_to_gpu(resources, 0, cpu_index)
                    search_index.nprobe = effective_nprobe
                    self._gpu_resources = resources
                    mode = "gpu"
                except Exception:
                    self._gpu_resources = None
                    search_index = cpu_index
                    mode = "cpu"

            search_index.search(vectors[:1], 1)

            index_dir.mkdir(parents=True, exist_ok=True)
            index_path = index_dir / "liver_ivf_flat.faiss"
            faiss.write_index(cpu_index, str(index_path))

            duration_ms = (time.perf_counter() - start) * 1000
            self._faiss = faiss
            self._cpu_index = cpu_index
            self._search_index = search_index
            self._snapshot = IndexSnapshot(
                status="ready",
                mode=mode,
                vector_count=vector_count,
                dimension=dimension,
                nlist=effective_nlist,
                nprobe=effective_nprobe,
                index_path=str(index_path.resolve()),
                build_duration_ms=round(duration_ms, 3),
                error=None,
            )
            return self._snapshot.summary()

    def search(self, query_vector: np.ndarray, top_k: int) -> tuple[np.ndarray, np.ndarray]:
        if self._search_index is None or not self._snapshot.ready:
            raise RuntimeError("Index has not been built")

        query = np.ascontiguousarray(query_vector.reshape(1, -1).astype("float32", copy=False))
        distances, indices = self._search_index.search(query, int(top_k))
        return distances[0], indices[0]


index_service = IndexService()
