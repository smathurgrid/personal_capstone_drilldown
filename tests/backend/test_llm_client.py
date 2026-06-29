"""Tests for LiteLLM adapter and model resolution."""

from unittest.mock import MagicMock, patch

from backend.shared.llm_client import LLMClient, resolve_litellm_model, _build_vision_content
from backend.shared.config import Settings


def test_resolve_litellm_model_adds_ollama_prefix():
    assert resolve_litellm_model("qwen2.5vl:7b") == "ollama/qwen2.5vl:7b"
    assert resolve_litellm_model("ollama/llama3.1") == "ollama/llama3.1"


def test_build_vision_content_text_only():
    assert _build_vision_content("hello", None) == "hello"


def test_build_vision_content_with_image():
    parts = _build_vision_content("describe", ["abc123"])
    assert parts[0]["type"] == "text"
    assert parts[1]["type"] == "image_url"
    assert "abc123" in parts[1]["image_url"]["url"]


def test_ollama_provider_uses_native_chat():
    settings = Settings()
    settings.LLM_PROVIDER = "ollama"
    settings.OLLAMA_BASE = "http://localhost:11434"
    client = LLMClient(settings)

    with patch("backend.shared.llm_client.requests.post") as mock_post:
        mock_post.return_value = MagicMock(
            ok=True,
            raise_for_status=MagicMock(),
            json=MagicMock(return_value={"message": {"content": "ok"}}),
        )
        result = client.chat_completion("qwen3.5:9b", "ping", images=["imgb64"])
        assert result == "ok"
        payload = mock_post.call_args[1]["json"]
        assert payload["messages"][0]["images"] == ["imgb64"]


def test_litellm_provider_calls_sdk():
    settings = Settings()
    settings.LLM_PROVIDER = "litellm"
    settings.OLLAMA_BASE = "http://localhost:11434"
    client = LLMClient(settings)

    mock_choice = MagicMock()
    mock_choice.message.content = "litellm reply"
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    with patch("litellm.completion", return_value=mock_response) as mock_completion:
        result = client.chat_completion("qwen2.5vl:7b", "analyze", images=["a", "b"])
        assert result == "litellm reply"
        kwargs = mock_completion.call_args[1]
        assert kwargs["model"] == "ollama/qwen2.5vl:7b"
        assert kwargs["api_base"] == "http://localhost:11434"


def test_openai_base_url_litellm_proxy():
    settings = Settings()
    settings.LLM_PROVIDER = "litellm"
    settings.LITELLM_PROXY_BASE = "http://localhost:4000"
    client = LLMClient(settings)
    assert client.openai_compatible_base_url() == "http://localhost:4000/v1/"
