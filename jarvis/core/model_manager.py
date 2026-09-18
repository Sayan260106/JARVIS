"""Intelligent Model Manager for JARVIS.

Manages model assignments and fallback chains for specialized roles:
- FAST -> Small local model for simple commands & low-latency routing (e.g. qwen2.5:1.5b)
- REASONING -> Better reasoning model for planning & complex task orchestration (e.g. qwen2.5:3b)
- DOCUMENT -> Local LLM for document reading & exam summarization (e.g. qwen2.5:3b)
- CODING -> Dedicated coding model for scripts & debugging (e.g. qwen2.5-coder:1.5b)
- VISION -> Multimodal model for GUI & screen analysis (e.g. llava)
- EMBEDDING -> Semantic memory vector retrieval (e.g. nomic-embed-text)
- CLOUD -> Optional high-capacity cloud model (e.g. gemini-1.5-flash)

Enables switching models at runtime without modifying JARVIS subsystems.
"""

from __future__ import annotations
from typing import Dict, List, Optional
from jarvis.core.llm_provider import ModelRole


DEFAULT_ROLE_MODELS: Dict[ModelRole, str] = {
    ModelRole.FAST: "qwen2.5:1.5b",
    ModelRole.REASONING: "qwen2.5:3b",
    ModelRole.DOCUMENT: "qwen2.5:3b",
    ModelRole.CODING: "qwen2.5-coder:1.5b",
    ModelRole.VISION: "llava",
    ModelRole.EMBEDDING: "nomic-embed-text",
    ModelRole.CLOUD: "gemini-1.5-flash",
}

DEFAULT_FALLBACK_CHAINS: Dict[ModelRole, List[ModelRole]] = {
    ModelRole.FAST: [ModelRole.REASONING],
    ModelRole.REASONING: [ModelRole.FAST],
    ModelRole.DOCUMENT: [ModelRole.REASONING, ModelRole.FAST],
    ModelRole.CODING: [ModelRole.REASONING, ModelRole.FAST],
    ModelRole.VISION: [ModelRole.REASONING],
    ModelRole.EMBEDDING: [],
    ModelRole.CLOUD: [ModelRole.REASONING, ModelRole.FAST],
}


class ModelManager:
    """Manages role-to-model configuration, dynamic binding, and fallback policies."""

    def __init__(
        self,
        initial_models: Optional[Dict[ModelRole, str]] = None,
        fallback_chains: Optional[Dict[ModelRole, List[ModelRole]]] = None,
    ):
        self._models: Dict[ModelRole, str] = dict(DEFAULT_ROLE_MODELS)
        if initial_models:
            self._models.update(initial_models)

        self._fallbacks: Dict[ModelRole, List[ModelRole]] = dict(DEFAULT_FALLBACK_CHAINS)
        if fallback_chains:
            self._fallbacks.update(fallback_chains)

    def get_model(self, role: ModelRole, fallback: Optional[str] = None) -> str:
        """Get the configured model name for a given role."""
        return self._models.get(role, fallback or self._models[ModelRole.REASONING])

    def set_model(self, role: ModelRole, model_name: str) -> None:
        """Bind a specific model to a functional role."""
        self._models[role] = model_name.strip()

    def get_fallback_chain(self, role: ModelRole) -> List[str]:
        """Returns the list of fallback model names for a role."""
        chain_roles = self._fallbacks.get(role, [])
        return [self.get_model(r) for r in chain_roles]

    def get_all_models(self) -> Dict[str, str]:
        """Return a mapping of all active role assignments."""
        return {role.value: model for role, model in self._models.items()}

    def resolve_model_with_fallbacks(
        self, role: ModelRole, available_models: Optional[List[str]] = None
    ) -> str:
        """Resolves the preferred model for a role, falling back if not available."""
        preferred = self.get_model(role)
        if not available_models:
            return preferred

        # Clean check matching tags or prefixes (e.g. qwen2.5:3b or qwen2.5:latest)
        def _matches(name: str, avail: List[str]) -> bool:
            base = name.split(":")[0]
            return any(a == name or a.startswith(base) for a in avail)

        if _matches(preferred, available_models):
            return preferred

        # Check fallback chain
        for fallback_role in self._fallbacks.get(role, []):
            fallback_model = self.get_model(fallback_role)
            if _matches(fallback_model, available_models):
                return fallback_model

        # Default to first available or preferred
        return available_models[0] if available_models else preferred


# Global singleton instance for convenient default usage across subsystems
default_model_manager = ModelManager()
