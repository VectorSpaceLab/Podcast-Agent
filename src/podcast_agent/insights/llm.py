"""Minimal OpenAI-compatible chat client for insight extraction."""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Protocol

from podcast_agent.errors import EvidenceExtractionError


class ModelWriter(Protocol):
    def __call__(self, prompt: str) -> str:
        ...


@dataclass(frozen=True)
class ChatModelConfig:
    api_key: str
    api_base: str
    model: str
    timeout_sec: int = 120


class OpenAICompatibleChatModel:
    def __init__(self, config: ChatModelConfig) -> None:
        self.config = config

    def __call__(self, prompt: str) -> str:
        try:
            import requests
        except ImportError as exc:  # pragma: no cover - depends on runtime environment.
            raise EvidenceExtractionError("requests is required for LLM evidence extraction.") from exc

        url = self.config.api_base.rstrip("/") + "/chat/completions"
        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.config.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
            },
            timeout=self.config.timeout_sec,
        )
        if response.status_code >= 400:
            raise EvidenceExtractionError(f"LLM request failed: HTTP {response.status_code} {response.text[:200]}")
        payload = response.json()
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise EvidenceExtractionError("LLM response did not contain choices[0].message.content.") from exc
        return str(content)


def build_default_model_writer() -> OpenAICompatibleChatModel:
    api_key = os.getenv("LLM_API_KEY") or os.getenv("DEEPSEEK_API_KEY")
    api_base = os.getenv("LLM_API_BASE") or os.getenv("DEEPSEEK_API_BASE")
    model = os.getenv("LLM_MODEL") or os.getenv("DEEPSEEK_MODEL") or os.getenv("DEFAULT_MODEL")
    missing = [
        name
        for name, value in {
            "LLM_API_KEY or DEEPSEEK_API_KEY": api_key,
            "LLM_API_BASE or DEEPSEEK_API_BASE": api_base,
            "LLM_MODEL or DEEPSEEK_MODEL or DEFAULT_MODEL": model,
        }.items()
        if not value
    ]
    if missing:
        raise EvidenceExtractionError(f"Missing required LLM environment variables: {', '.join(missing)}")
    return OpenAICompatibleChatModel(
        ChatModelConfig(
            api_key=api_key or "",
            api_base=api_base or "",
            model=model or "",
        )
    )
