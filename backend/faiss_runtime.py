from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FaissRuntime:
    available: bool
    mode: str
    version: str | None
    gpu_count: int
    error: str | None = None


def inspect_faiss_runtime() -> FaissRuntime:
    try:
        import faiss  # type: ignore
    except Exception as exc:  # pragma: no cover - depends on local environment
        return FaissRuntime(
            available=False,
            mode="unavailable",
            version=None,
            gpu_count=0,
            error=str(exc),
        )

    gpu_count = 0
    mode = "cpu"
    try:
        gpu_count = int(faiss.get_num_gpus())
        if gpu_count > 0:
            mode = "gpu"
    except Exception:
        gpu_count = 0

    return FaissRuntime(
        available=True,
        mode=mode,
        version=getattr(faiss, "__version__", None),
        gpu_count=gpu_count,
    )
