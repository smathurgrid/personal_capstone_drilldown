"""Unified LLM access — LiteLLM SDK or direct Ollama fallback."""

from __future__ import annotations

import logging
from typing import Any

import requests

from backend.shared.config import Settings, settings
from backend.shared.errors import AppError
from backend.shared.ollama_health import ollama_connection_app_error

logger = logging.getLogger(__name__)


def resolve_litellm_model(model: str) -> str:
    """Map bare Ollama model names to LiteLLM provider prefixes."""
    if "/" in model:
        return model
    return f"ollama/{model}"


def _build_vision_content(prompt: str, images: list[str] | None) -> Any:
    if not images:
        return prompt
    parts: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    for img_b64 in images:
        parts.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"},
            }
        )
    return parts


class LLMClient:
    """Chat / vision completions routed through LiteLLM or native Ollama."""

    def __init__(self, app_settings: Settings | None = None) -> None:
        self._settings = app_settings or settings
        self._ollama_api = self._settings.OLLAMA_BASE.rstrip("/") + "/api"

    @property
    def provider(self) -> str:
        return self._settings.LLM_PROVIDER.lower()

    def chat_completion(
        self,
        model: str,
        prompt: str,
        *,
        images: list[str] | None = None,
        temperature: float = 0.0,
        timeout: int = 300,
        think: bool = False,
        num_predict: int | None = None,
        json_mode: bool = False,
    ) -> str:
        if self.provider == "litellm":
            return self._litellm_completion(
                model,
                prompt,
                images=images,
                temperature=temperature,
                timeout=timeout,
                num_predict=num_predict,
                json_mode=json_mode,
            )
        return self._ollama_chat_completion(
            model,
            prompt,
            images=images,
            temperature=temperature,
            timeout=timeout,
            think=think,
            num_predict=num_predict,
            json_mode=json_mode,
        )

    def _litellm_completion(
        self,
        model: str,
        prompt: str,
        *,
        images: list[str] | None,
        temperature: float,
        timeout: int,
        num_predict: int | None = None,
        json_mode: bool = False,
    ) -> str:
        import litellm

        litellm_model = resolve_litellm_model(model)
        content = _build_vision_content(prompt, images)
        messages = [{"role": "user", "content": content}]

        kwargs: dict[str, Any] = {
            "model": litellm_model,
            "messages": messages,
            "temperature": temperature,
            "timeout": timeout,
        }
        if num_predict is not None:
            kwargs["max_tokens"] = num_predict
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        if litellm_model.startswith("ollama/"):
            kwargs["api_base"] = self._settings.OLLAMA_BASE.rstrip("/")

        logger.debug("LiteLLM completion model=%s images=%s", litellm_model, len(images or []))
        response = litellm.completion(**kwargs)
        text = response.choices[0].message.content
        return (text or "").strip()

    def _ollama_chat_completion(
        self,
        model: str,
        prompt: str,
        *,
        images: list[str] | None,
        temperature: float,
        timeout: int,
        think: bool,
        num_predict: int | None = None,
        json_mode: bool = False,
    ) -> str:
        message: dict[str, Any] = {"role": "user", "content": prompt}
        if images:
            message["images"] = images

        # Vision JSON tasks must not run unbounded — qwen3.5 will fill n_ctx (~4k) without a cap.
        effective_predict = num_predict
        if effective_predict is None and images:
            effective_predict = 1024

        options: dict[str, Any] = {"temperature": temperature}
        if effective_predict is not None:
            options["num_predict"] = effective_predict

        payload: dict[str, Any] = {
            "model": model,
            "messages": [message],
            "stream": False,
            "options": options,
        }
        if json_mode:
            payload["format"] = "json"
        # Explicitly disable thinking templates on Qwen3.x when not requested.
        payload["think"] = think
        try:
            resp = requests.post(f"{self._ollama_api}/chat", json=payload, timeout=timeout)
        except requests.exceptions.ConnectionError as exc:
            raise ollama_connection_app_error(exc) from exc
        except requests.exceptions.Timeout as exc:
            raise AppError(
                "OLLAMA_TIMEOUT",
                f"Ollama request timed out after {timeout}s",
                status_code=504,
            ) from exc
        try:
            resp.raise_for_status()
        except requests.exceptions.HTTPError as exc:
            logger.error("Ollama bad request details: %s", resp.text)
            raise ValueError(f"Ollama error: {resp.text}") from exc
        return resp.json().get("message", {}).get("content", "")

    def openai_compatible_base_url(self) -> str:
        """Base URL for OpenAI-style clients (e.g. pi-agent-core)."""
        if self.provider == "litellm" and self._settings.LITELLM_PROXY_BASE:
            return self._settings.LITELLM_PROXY_BASE.rstrip("/") + "/v1/"
        return self._settings.OLLAMA_BASE.rstrip("/") + "/v1/"

    def orchestrator_model_id(self) -> str:
        """Model id sent to OpenAI-compatible agent endpoints."""
        model = self._settings.AGENT_ORCHESTRATOR_MODEL
        if self.provider == "litellm" and self._settings.LITELLM_PROXY_BASE:
            return resolve_litellm_model(model).split("/", 1)[-1]
        return model


_default_client: LLMClient | None = None


def get_llm_client(app_settings: Settings | None = None) -> LLMClient:
    global _default_client
    if app_settings is not None:
        return LLMClient(app_settings)
    if _default_client is None:
        _default_client = LLMClient()
    return _default_client
