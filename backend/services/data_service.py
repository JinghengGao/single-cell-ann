from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any

import h5py
import numpy as np
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename


METADATA_FIELDS = ("cell_type", "disease", "AgeGroup", "tissue")
REQUIRED_H5AD_FIELDS = ("obsm/X_pca", "obsm/X_umap", "obs/_index")


@dataclass
class DatasetRecord:
    dataset_id: str
    name: str
    data_path: str
    source: str = "local"
    status: str = "registered"
    file_size_bytes: int = 0
    cell_count: int = 0
    vector_dim: int = 0
    embedding_method: str = "obsm/X_pca"
    visualization_method: str = "obsm/X_umap"
    metadata_fields: list[str] = field(default_factory=list)
    sample_cell_ids: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    error: str | None = None

    @property
    def loaded(self) -> bool:
        return self.status == "loaded"

    def summary(self) -> dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "name": self.name,
            "source": self.source,
            "status": self.status,
            "data_path": self.data_path,
            "file_size_bytes": self.file_size_bytes,
            "cell_count": self.cell_count,
            "vector_dim": self.vector_dim,
            "embedding_method": self.embedding_method,
            "visualization_method": self.visualization_method,
            "metadata_fields": self.metadata_fields,
            "sample_cell_ids": self.sample_cell_ids,
            "loaded": self.loaded,
            "error": self.error,
        }


@dataclass
class DatasetSnapshot:
    dataset_id: str = "liver"
    name: str = "Human pediatric liver"
    source: str = "local"
    status: str = "not_loaded"
    data_path: str | None = None
    embedding_method: str = "obsm/X_pca"
    visualization_method: str = "obsm/X_umap"
    vectors: np.ndarray | None = None
    umap: np.ndarray | None = None
    cell_ids: list[str] = field(default_factory=list)
    metadata: dict[str, list[str]] = field(default_factory=dict)
    cell_id_to_index: dict[str, int] = field(default_factory=dict)
    error: str | None = None

    @property
    def loaded(self) -> bool:
        return self.status == "loaded" and self.vectors is not None

    @property
    def cell_count(self) -> int:
        return len(self.cell_ids)

    @property
    def vector_dim(self) -> int:
        if self.vectors is None:
            return 0
        return int(self.vectors.shape[1])

    def summary(self) -> dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "name": self.name,
            "source": self.source,
            "status": self.status,
            "data_path": self.data_path,
            "loaded": self.loaded,
            "cell_count": self.cell_count,
            "vector_dim": self.vector_dim,
            "embedding_method": self.embedding_method,
            "visualization_method": self.visualization_method,
            "metadata_fields": list(self.metadata.keys()),
            "sample_cell_ids": self.cell_ids[:5],
            "error": self.error,
        }


class DataService:
    def __init__(self) -> None:
        self._lock = RLock()
        self._records: dict[str, DatasetRecord] = {}
        self._snapshots: dict[str, DatasetSnapshot] = {}
        self._active_dataset_id: str | None = None
        self._snapshot = DatasetSnapshot()

    @property
    def snapshot(self) -> DatasetSnapshot:
        if self._active_dataset_id and self._active_dataset_id in self._snapshots:
            return self._snapshots[self._active_dataset_id]
        return self._snapshot

    def list_datasets(self, registry_path: Path) -> dict[str, Any]:
        with self._lock:
            self._load_registry(registry_path)
            datasets = sorted(self._records.values(), key=lambda item: (item.name.lower(), item.dataset_id))
            return {
                "count": len(datasets),
                "active_dataset_id": self._active_dataset_id,
                "datasets": [record.summary() for record in datasets],
            }

    def get_dataset(self, dataset_id: str, registry_path: Path) -> dict[str, Any]:
        with self._lock:
            record = self._get_record(dataset_id, registry_path)
            summary = record.summary()
            summary["loaded"] = dataset_id in self._snapshots
            return summary

    def scan_dataset_files(
        self,
        data_dir: Path,
        dataset_library_dir: Path,
        upload_dir: Path,
        default_data_path: Path,
        registry_path: Path,
    ) -> dict[str, Any]:
        with self._lock:
            self._load_registry(registry_path)
            discovered: list[Path] = []
            seen_paths: set[Path] = set()

            candidates = [default_data_path, *data_dir.glob("*.h5ad"), *dataset_library_dir.glob("*.h5ad"), *upload_dir.glob("*.h5ad")]
            for path in candidates:
                resolved = path.resolve()
                if resolved.exists() and resolved not in seen_paths:
                    seen_paths.add(resolved)
                    discovered.append(resolved)

            registered = []
            for path in discovered:
                source = self._source_for_path(path, data_dir, dataset_library_dir, upload_dir)
                registered.append(self._register_path(path, source, registry_path).summary())

            self._save_registry(registry_path)
            return {"count": len(registered), "datasets": registered}

    def upload_dataset(self, file_storage: FileStorage, upload_dir: Path, registry_path: Path) -> dict[str, Any]:
        filename = secure_filename(file_storage.filename or "")
        if not filename:
            raise ValueError("file is required")
        if not filename.lower().endswith(".h5ad"):
            raise ValueError("only .h5ad files are supported")

        with self._lock:
            upload_dir.mkdir(parents=True, exist_ok=True)
            target = upload_dir / filename
            if target.exists():
                stem = target.stem
                suffix = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
                target = upload_dir / f"{stem}_{suffix}.h5ad"
            file_storage.save(target)
            record = self._register_path(target.resolve(), "upload", registry_path)
            self._save_registry(registry_path)
            return record.summary()

    def validate_dataset(self, dataset_id: str, registry_path: Path) -> dict[str, Any]:
        with self._lock:
            record = self._get_record(dataset_id, registry_path)
            try:
                validation = self._inspect_h5ad(Path(record.data_path))
                record.status = "validated"
                record.cell_count = validation["cell_count"]
                record.vector_dim = validation["vector_dim"]
                record.metadata_fields = validation["metadata_fields"]
                record.sample_cell_ids = validation["sample_cell_ids"]
                record.error = None
            except Exception as exc:
                record.status = "error"
                record.error = str(exc)
                raise
            finally:
                record.updated_at = self._now()
                self._save_registry(registry_path)
            return record.summary()

    def validate_datasets(self, dataset_ids: list[str], registry_path: Path) -> dict[str, Any]:
        with self._lock:
            self._load_registry(registry_path)
            target_ids = dataset_ids or sorted(self._records.keys())
            results = []
            errors = []
            for dataset_id in target_ids:
                try:
                    results.append(self.validate_dataset(dataset_id, registry_path))
                except Exception as exc:
                    errors.append({"dataset_id": dataset_id, "message": str(exc)})
            return {
                "requested_count": len(target_ids),
                "validated_count": len(results),
                "error_count": len(errors),
                "datasets": results,
                "errors": errors,
            }

    def load_h5ad(
        self,
        path: Path | None = None,
        *,
        dataset_id: str | None = None,
        registry_path: Path | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            if dataset_id:
                if registry_path is None:
                    raise ValueError("registry_path is required when dataset_id is used")
                record = self._get_record(dataset_id, registry_path)
                resolved = Path(record.data_path).resolve()
            elif path is not None:
                resolved = path.resolve()
                if registry_path is not None:
                    record = self._register_path(resolved, "local", registry_path)
                else:
                    record = self._record_from_path(resolved, "local")
            else:
                raise ValueError("path or dataset_id is required")

            if not resolved.exists():
                raise FileNotFoundError(f"Data file not found: {resolved}")

            try:
                vectors, umap, cell_ids, metadata = self._read_h5ad(resolved)
                self._validate_loaded_data(vectors, umap, cell_ids, metadata)
                snapshot = DatasetSnapshot(
                    dataset_id=record.dataset_id,
                    name=record.name,
                    source=record.source,
                    status="loaded",
                    data_path=str(resolved),
                    vectors=np.ascontiguousarray(vectors),
                    umap=np.ascontiguousarray(umap),
                    cell_ids=cell_ids,
                    metadata=metadata,
                    cell_id_to_index={cell_id: idx for idx, cell_id in enumerate(cell_ids)},
                    error=None,
                )
                self._snapshots[snapshot.dataset_id] = snapshot
                self._active_dataset_id = snapshot.dataset_id
                self._snapshot = snapshot

                if registry_path is not None:
                    record.status = "loaded"
                    record.cell_count = snapshot.cell_count
                    record.vector_dim = snapshot.vector_dim
                    record.metadata_fields = list(snapshot.metadata.keys())
                    record.sample_cell_ids = snapshot.cell_ids[:5]
                    record.error = None
                    record.updated_at = self._now()
                    self._save_registry(registry_path)

                return snapshot.summary()
            except Exception as exc:
                if registry_path is not None:
                    record.status = "error"
                    record.error = str(exc)
                    record.updated_at = self._now()
                    self._save_registry(registry_path)
                self._snapshot.status = "error"
                self._snapshot.data_path = str(resolved)
                self._snapshot.error = str(exc)
                raise

    def get_snapshot(
        self,
        dataset_id: str | None = None,
        *,
        registry_path: Path | None = None,
        load_if_needed: bool = True,
    ) -> DatasetSnapshot:
        with self._lock:
            target_dataset_id = dataset_id or self._active_dataset_id
            if target_dataset_id and target_dataset_id in self._snapshots:
                return self._snapshots[target_dataset_id]
            if target_dataset_id and load_if_needed and registry_path is not None:
                self.load_h5ad(dataset_id=target_dataset_id, registry_path=registry_path)
                return self._snapshots[target_dataset_id]
            if dataset_id is None and self.snapshot.loaded:
                return self.snapshot
            raise RuntimeError("Dataset has not been loaded")

    def get_vector_by_cell_id(
        self,
        cell_id: str,
        *,
        dataset_id: str | None = None,
        registry_path: Path | None = None,
    ) -> np.ndarray:
        snapshot = self.get_snapshot(dataset_id, registry_path=registry_path)
        try:
            idx = snapshot.cell_id_to_index[cell_id]
        except KeyError as exc:
            raise KeyError(f"Unknown cell_id: {cell_id}") from exc
        return snapshot.vectors[idx]

    def get_cell_metadata(
        self,
        idx: int,
        *,
        dataset_id: str | None = None,
        registry_path: Path | None = None,
    ) -> dict[str, Any]:
        snapshot = self.get_snapshot(dataset_id, registry_path=registry_path)
        return self._metadata_for_snapshot(snapshot, idx)

    def sample_visualization_points(
        self,
        limit: int,
        *,
        dataset_id: str | None = None,
        registry_path: Path | None = None,
    ) -> dict[str, Any]:
        snapshot = self.get_snapshot(dataset_id, registry_path=registry_path)
        if limit <= 0:
            raise ValueError("limit must be positive")

        points = self._sample_snapshot_points(snapshot, limit)
        return {
            "dataset": snapshot.summary(),
            "datasets": [snapshot.summary()],
            "limit": int(limit),
            "total": snapshot.cell_count,
            "points": points,
        }

    def sample_visualization_points_for_datasets(
        self,
        dataset_ids: list[str],
        limit: int,
        *,
        registry_path: Path,
    ) -> dict[str, Any]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        if not dataset_ids:
            return self.sample_visualization_points(limit, registry_path=registry_path)

        snapshots = [self.get_snapshot(dataset_id, registry_path=registry_path) for dataset_id in dataset_ids]
        total = sum(snapshot.cell_count for snapshot in snapshots)
        per_dataset_limit = max(1, limit // max(len(snapshots), 1))
        points = []
        for snapshot in snapshots:
            points.extend(self._sample_snapshot_points(snapshot, min(per_dataset_limit, snapshot.cell_count)))
        return {
            "dataset": snapshots[0].summary() if len(snapshots) == 1 else None,
            "datasets": [snapshot.summary() for snapshot in snapshots],
            "limit": int(limit),
            "total": total,
            "points": points[:limit],
        }

    def resolve_cell(
        self,
        cell_id: str,
        dataset_ids: list[str],
        *,
        registry_path: Path,
        dataset_id: str | None = None,
    ) -> tuple[DatasetSnapshot, int]:
        candidates = [dataset_id] if dataset_id else dataset_ids
        matches: list[tuple[DatasetSnapshot, int]] = []
        for candidate_dataset_id in candidates:
            snapshot = self.get_snapshot(candidate_dataset_id, registry_path=registry_path)
            idx = snapshot.cell_id_to_index.get(cell_id)
            if idx is not None:
                matches.append((snapshot, idx))
        if not matches:
            raise KeyError(f"Unknown cell_id: {cell_id}")
        if len(matches) > 1:
            raise ValueError("cell_id exists in multiple datasets; dataset_id is required")
        return matches[0]

    def _sample_snapshot_points(self, snapshot: DatasetSnapshot, limit: int) -> list[dict[str, Any]]:
        count = snapshot.cell_count
        if limit >= count:
            indices = np.arange(count)
        else:
            indices = np.linspace(0, count - 1, limit, dtype=np.int64)

        points = []
        for idx in indices.tolist():
            meta = self._metadata_for_snapshot(snapshot, int(idx))
            points.append(
                {
                    "index": int(idx),
                    "dataset_id": meta["dataset_id"],
                    "dataset_name": meta["dataset_name"],
                    "cell_id": meta["cell_id"],
                    "x": meta["umap"][0],
                    "y": meta["umap"][1],
                    "cell_type": meta.get("cell_type"),
                    "disease": meta.get("disease"),
                    "AgeGroup": meta.get("AgeGroup"),
                    "tissue": meta.get("tissue"),
                }
            )
        return points

    def _metadata_for_snapshot(self, snapshot: DatasetSnapshot, idx: int) -> dict[str, Any]:
        return {
            "dataset_id": snapshot.dataset_id,
            "dataset_name": snapshot.name,
            "cell_id": snapshot.cell_ids[idx],
            **{field_name: values[idx] for field_name, values in snapshot.metadata.items()},
            "umap": [float(snapshot.umap[idx, 0]), float(snapshot.umap[idx, 1])] if snapshot.umap is not None else None,
        }

    def _get_record(self, dataset_id: str, registry_path: Path) -> DatasetRecord:
        self._load_registry(registry_path)
        try:
            return self._records[dataset_id]
        except KeyError as exc:
            raise KeyError(f"Unknown dataset_id: {dataset_id}") from exc

    def _register_path(self, path: Path, source: str, registry_path: Path) -> DatasetRecord:
        resolved = path.resolve()
        self._load_registry(registry_path)
        existing = self._record_for_path(resolved)
        if existing is not None:
            existing.file_size_bytes = resolved.stat().st_size if resolved.exists() else 0
            existing.updated_at = self._now()
            return existing

        record = self._record_from_path(resolved, source)
        dataset_id = record.dataset_id
        if dataset_id in self._records and Path(self._records[dataset_id].data_path).resolve() != resolved:
            dataset_id = f"{dataset_id}_{self._short_hash(str(resolved))}"
            record.dataset_id = dataset_id
        self._records[dataset_id] = record
        return record

    def _record_from_path(self, path: Path, source: str) -> DatasetRecord:
        now = self._now()
        return DatasetRecord(
            dataset_id=self._dataset_id_from_path(path),
            name=path.stem,
            data_path=str(path.resolve()),
            source=source,
            file_size_bytes=path.stat().st_size if path.exists() else 0,
            created_at=now,
            updated_at=now,
        )

    def _record_for_path(self, path: Path) -> DatasetRecord | None:
        for record in self._records.values():
            if Path(record.data_path).resolve() == path.resolve():
                return record
        return None

    def _load_registry(self, registry_path: Path) -> None:
        if not registry_path.exists():
            return
        with registry_path.open("r", encoding="utf-8") as file:
            raw = json.load(file)
        records = {}
        for item in raw.get("datasets", []):
            record = DatasetRecord(**item)
            records[record.dataset_id] = record
        self._records = records

    def _save_registry(self, registry_path: Path) -> None:
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "updated_at": self._now(),
            "datasets": [record.__dict__ for record in sorted(self._records.values(), key=lambda item: item.dataset_id)],
        }
        with registry_path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)

    @staticmethod
    def _read_h5ad(path: Path) -> tuple[np.ndarray, np.ndarray, list[str], dict[str, list[str]]]:
        with h5py.File(path, "r") as h5:
            vectors = DataService._read_required_array(h5, "obsm/X_pca").astype("float32", copy=False)
            umap = DataService._read_required_array(h5, "obsm/X_umap").astype("float32", copy=False)
            cell_ids = DataService._read_string_or_categorical(h5["obs"]["_index"])
            metadata = {
                field_name: DataService._read_string_or_categorical(h5["obs"][field_name])
                for field_name in METADATA_FIELDS
                if field_name in h5["obs"]
            }
        return vectors, umap, cell_ids, metadata

    @staticmethod
    def _inspect_h5ad(path: Path) -> dict[str, Any]:
        if not path.exists():
            raise FileNotFoundError(f"Data file not found: {path}")

        with h5py.File(path, "r") as h5:
            for key in REQUIRED_H5AD_FIELDS:
                if key not in h5:
                    raise KeyError(f"Required H5AD field missing: {key}")
            vectors = h5["obsm/X_pca"]
            umap = h5["obsm/X_umap"]
            if vectors.ndim != 2 or vectors.shape[0] == 0 or vectors.shape[1] == 0:
                raise ValueError(f"Invalid array shape for obsm/X_pca: {vectors.shape}")
            if umap.ndim != 2 or umap.shape[0] != vectors.shape[0] or umap.shape[1] < 2:
                raise ValueError(f"Invalid array shape for obsm/X_umap: {umap.shape}")
            metadata_fields = [field_name for field_name in METADATA_FIELDS if field_name in h5["obs"]]
            sample_cell_ids = DataService._read_string_or_categorical(h5["obs"]["_index"], limit=5)
            return {
                "cell_count": int(vectors.shape[0]),
                "vector_dim": int(vectors.shape[1]),
                "metadata_fields": metadata_fields,
                "sample_cell_ids": sample_cell_ids,
            }

    @staticmethod
    def _read_required_array(h5: h5py.File, key: str) -> np.ndarray:
        if key not in h5:
            raise KeyError(f"Required H5AD field missing: {key}")
        data = h5[key][:]
        if data.ndim != 2 or data.shape[0] == 0 or data.shape[1] == 0:
            raise ValueError(f"Invalid array shape for {key}: {data.shape}")
        return data

    @classmethod
    def _read_string_or_categorical(cls, obj: h5py.Dataset | h5py.Group, limit: int | None = None) -> list[str]:
        if isinstance(obj, h5py.Dataset):
            values = obj[:limit] if limit is not None else obj[:]
            return [cls._decode(value) for value in values]

        if {"categories", "codes"}.issubset(obj.keys()):
            categories = [cls._decode(value) for value in obj["categories"][:]]
            codes = obj["codes"][:limit] if limit is not None else obj["codes"][:]
            return [categories[int(code)] if int(code) >= 0 else "" for code in codes]

        raise TypeError(f"Unsupported obs field encoding for {obj.name}")

    @staticmethod
    def _decode(value: Any) -> str:
        if isinstance(value, bytes):
            return value.decode("utf-8")
        return str(value)

    @staticmethod
    def _validate_loaded_data(
        vectors: np.ndarray,
        umap: np.ndarray,
        cell_ids: list[str],
        metadata: dict[str, list[str]],
    ) -> None:
        row_count = vectors.shape[0]
        if umap.shape[0] != row_count:
            raise ValueError("PCA and UMAP row counts do not match")
        if len(cell_ids) != row_count:
            raise ValueError("cell_id count does not match vector row count")
        for field_name, values in metadata.items():
            if len(values) != row_count:
                raise ValueError(f"metadata field {field_name} has invalid length")

    @staticmethod
    def _source_for_path(path: Path, data_dir: Path, dataset_library_dir: Path, upload_dir: Path) -> str:
        resolved = path.resolve()
        if DataService._is_relative_to(resolved, upload_dir.resolve()):
            return "upload"
        if DataService._is_relative_to(resolved, dataset_library_dir.resolve()):
            return "library"
        if DataService._is_relative_to(resolved, data_dir.resolve()):
            return "local"
        return "manual"

    @staticmethod
    def _is_relative_to(path: Path, parent: Path) -> bool:
        try:
            path.relative_to(parent)
            return True
        except ValueError:
            return False

    @staticmethod
    def _dataset_id_from_path(path: Path) -> str:
        slug = re.sub(r"[^a-zA-Z0-9]+", "_", path.stem).strip("_").lower()
        return slug or f"dataset_{DataService._short_hash(str(path.resolve()))}"

    @staticmethod
    def _short_hash(value: str) -> str:
        return hashlib.sha1(value.encode("utf-8")).hexdigest()[:8]

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()


data_service = DataService()
