"""Local Ollama client for JARVIS.

Connects to the local Ollama API (http://127.0.0.1:11434) without third-party dependencies.
"""

from __future__ import annotations
import json
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional


DEFAULT_JARVIS_SYSTEM_PROMPT = """You are JARVIS, an advanced, highly intelligent local AI assistant.
Your responses are direct, articulate, insightful, and technically precise.
You excel at computer science, engineering, and analytical problem-solving.
Always tailor explanations accurately to the user's requested level of depth."""


class OllamaClient:
    """Client for local Ollama server."""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:11434",
        model: str = "qwen2.5:3b",
        system_prompt: str = DEFAULT_JARVIS_SYSTEM_PROMPT,
        timeout: float = 60.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.system_prompt = system_prompt
        self.timeout = timeout

    def is_available(self) -> bool:
        """Check if the local Ollama server is running and reachable."""
        try:
            req = urllib.request.Request(f"{self.base_url}/api/tags")
            with urllib.request.urlopen(req, timeout=3.0) as res:
                return res.status == 200
        except Exception:
            return False

    def list_models(self) -> List[str]:
        """Fetch list of models downloaded in local Ollama."""
        try:
            req = urllib.request.Request(f"{self.base_url}/api/tags")
            with urllib.request.urlopen(req, timeout=3.0) as res:
                data = json.loads(res.read().decode("utf-8"))
                return [m["name"] for m in data.get("models", [])]
        except Exception:
            return []

    def chat(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.7,
    ) -> str:
        """Send chat messages and return the assistant response string.

        Args:
            messages: List of dicts with 'role' ('user' | 'assistant') and 'content'.
            system_prompt: Optional override for system prompt.
            model: Optional override for model name.
            temperature: Sampling temperature.
        """
        sys_prompt = system_prompt or self.system_prompt
        target_model = model or self.model

        formatted_messages = []
        if sys_prompt:
            formatted_messages.append({"role": "system", "content": sys_prompt})

        for msg in messages:
            formatted_messages.append({"role": msg["role"], "content": msg["content"]})

        payload = {
            "model": target_model,
            "messages": formatted_messages,
            "stream": False,
            "options": {
                "temperature": temperature,
            },
        }

        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=data_bytes,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as res:
                if res.status != 200:
                    raise RuntimeError(f"Ollama returned status code {res.status}")
                result = json.loads(res.read().decode("utf-8"))
                return result.get("message", {}).get("content", "").strip()
        except urllib.error.URLError as e:
            raise ConnectionError(
                f"Failed to connect to Ollama at {self.base_url}. Is 'ollama serve' running? Error: {e}"
            )
