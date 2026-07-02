from __future__ import annotations

import json
from pathlib import Path

import backend
from backend.app import app
from backend.config import Config


def main() -> None:
    runtime_dir = Path("runtime")
    runtime_dir.mkdir(exist_ok=True)
    runtime_dir.joinpath("startup_diag.json").write_text(
        json.dumps(
            {
                "backend_file": str(Path(backend.__file__).resolve()),
                "llm_provider": Config.LLM_PROVIDER,
                "llm_api_url": Config.LLM_API_URL,
                "llm_model": Config.LLM_MODEL,
                "llm_api_key_configured": bool((Config.LLM_API_KEY or "").strip()),
                "app_llm_provider": app.config.get("LLM_PROVIDER"),
                "app_llm_api_url": app.config.get("LLM_API_URL"),
                "app_llm_model": app.config.get("LLM_MODEL"),
                "app_llm_api_key_configured": bool((app.config.get("LLM_API_KEY") or "").strip()),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    app.run(host=Config.HOST, port=Config.PORT, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
