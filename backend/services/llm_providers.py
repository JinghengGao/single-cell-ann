from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import requests


@dataclass(frozen=True)
class LlmResponse:
    content: str
    model: str
    usage: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)


class LlmProviderError(RuntimeError):
    def __init__(self, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


class BaseLlmProvider(ABC):
    name = "base"
    default_model = ""
    default_api_url = ""
    requires_api_key = True

    def api_url(self, config: dict[str, Any]) -> str:
        return str(config.get("LLM_API_URL") or self.default_api_url).strip()

    def model(self, config: dict[str, Any]) -> str:
        return str(config.get("LLM_MODEL") or self.default_model).strip()

    @abstractmethod
    def chat(
        self,
        messages: list[dict[str, str]],
        config: dict[str, Any],
        *,
        extra_options: dict[str, Any] | None = None,
    ) -> LlmResponse:
        raise NotImplementedError


class ChatCompletionsProvider(BaseLlmProvider):
    name = "openai_compatible"
    default_model = "gpt-4.1-mini"
    default_api_url = ""

    def chat(
        self,
        messages: list[dict[str, str]],
        config: dict[str, Any],
        *,
        extra_options: dict[str, Any] | None = None,
    ) -> LlmResponse:
        api_url = self.api_url(config)
        if not api_url:
            raise LlmProviderError("LLM API URL is not configured; set SCANN_LLM_API_URL")

        api_key = str(config.get("LLM_API_KEY") or "").strip()
        if self.requires_api_key and not api_key:
            raise LlmProviderError("LLM API key is not configured; set SCANN_LLM_API_KEY")

        model = self.model(config)
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": float(config.get("LLM_TEMPERATURE") or 0.2),
            "max_tokens": int(config.get("LLM_MAX_TOKENS") or 600),
        }
        payload.update(self.extra_payload(model, extra_options or {}))

        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        try:
            response = requests.post(
                api_url,
                headers=headers,
                json=payload,
                timeout=int(config.get("LLM_TIMEOUT_SECONDS") or 60),
            )
        except requests.Timeout as exc:
            raise LlmProviderError("LLM provider request timed out", retryable=True) from exc
        except requests.RequestException as exc:
            raise LlmProviderError(f"LLM provider request failed: {exc}", retryable=True) from exc

        if response.status_code >= 400:
            message = provider_error_message(response)
            retryable = response.status_code in {408, 409, 425, 429} or response.status_code >= 500
            raise LlmProviderError(
                f"LLM provider returned HTTP {response.status_code}: {message}",
                retryable=retryable,
            )

        try:
            data = response.json()
            analysis = data["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LlmProviderError("LLM provider returned an invalid response format") from exc

        if not str(analysis).strip():
            raise LlmProviderError("LLM provider returned an empty analysis")

        return LlmResponse(
            content=str(analysis).strip(),
            model=str(data.get("model") or model),
            usage=data.get("usage") if isinstance(data.get("usage"), dict) else {},
            raw=data if isinstance(data, dict) else {},
        )

    def extra_payload(self, model: str, extra_options: dict[str, Any]) -> dict[str, Any]:
        return {}


class SiliconFlowProvider(ChatCompletionsProvider):
    name = "siliconflow"
    default_model = "Qwen/Qwen3-8B"
    default_api_url = "https://api.siliconflow.cn/v1/chat/completions"

    def extra_payload(self, model: str, extra_options: dict[str, Any]) -> dict[str, Any]:
        thinking_enabled = bool(extra_options.get("enable_thinking"))
        if "qwen3" in model.lower() or thinking_enabled:
            return {"enable_thinking": thinking_enabled}
        return {}


class OpenAiProvider(ChatCompletionsProvider):
    name = "openai"
    default_model = "gpt-4.1-mini"
    default_api_url = "https://api.openai.com/v1/chat/completions"


class LocalModelProvider(ChatCompletionsProvider):
    name = "local"
    default_model = "qwen3:8b"
    default_api_url = "http://127.0.0.1:11434/v1/chat/completions"
    requires_api_key = False


PROVIDERS: dict[str, type[BaseLlmProvider]] = {
    "siliconflow": SiliconFlowProvider,
    "openai": OpenAiProvider,
    "openai_compatible": ChatCompletionsProvider,
    "compatible": ChatCompletionsProvider,
    "local": LocalModelProvider,
    "ollama": LocalModelProvider,
    "vllm": LocalModelProvider,
}


def get_llm_provider(provider_name: str | None) -> BaseLlmProvider:
    normalized = str(provider_name or "siliconflow").strip().lower()
    provider_class = PROVIDERS.get(normalized)
    if provider_class is None:
        supported = ", ".join(sorted(PROVIDERS))
        raise LlmProviderError(f"Unsupported LLM provider '{normalized}'. Supported providers: {supported}")
    return provider_class()


def provider_error_message(response: requests.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text[:300] or "empty error response"

    error = payload.get("error") if isinstance(payload, dict) else None
    if isinstance(error, dict):
        return str(error.get("message") or error.get("code") or "provider error")
    if isinstance(error, str):
        return error
    if isinstance(payload, dict) and payload.get("message"):
        return str(payload["message"])
    return "provider error"
