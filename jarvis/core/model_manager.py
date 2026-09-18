"""Intelligent Model Manager for JARVIS.

Manages model assignments for specialized roles:
- FAST -> Intent classification & low-latency routing
- REASONING -> Planning, task decomposition, and recovery
- VISION -> Screen & GUI analysis
- EMBEDDING -> Semantic memory vector retrieval

Enables switching models at runtime without modifying JARVIS subsystems.
"""

from __future__ import annotations
from typing import Dict, Optional
from jarvis.core.llm_provider import ModelRole


DEFAULT_ROLE_MODELS: Dict[ModelRole, str] = {
    ModelRole.FAST: "qwen2.5:1.5b",
    ModelRole.REASONING: "qwen2.5:3b",
    ModelRole.VISION: "llava",
    ModelRole.EMBEDDING: "nomic-embed-text",
}


class ModelManager:
    """Manages role-to-model configuration and dynamic binding."""

    def __init__(self, initial_models: Optional[Dict[ModelRole, str]] = None):
        self._models: Dict[ModelRole, str] = dict(DEFAULT_ROLE_MODELS)
        if initial_models:
            self._models.update(initial_models)

    def get_model(self, role: ModelRole, fallback: Optional[str] = None) -> str:
        """Get the configured model name for a given role."""
        return self._models.get(role, fallback or self._models[ModelRole.REASONING])

    def set_model(self, role: ModelRole, model_name: str) -> None:
        """Bind a specific model to a functional role."""
        self._models[role] = model_name.strip()

    def get_all_models(self) -> Dict[str, str]:
        """Return a mapping of all active role assignments."""
        return {role.value: model for role, model in self._models.items()}


# Global singleton instance for convenient default usage across subsystems
default_model_manager = ModelManager()
