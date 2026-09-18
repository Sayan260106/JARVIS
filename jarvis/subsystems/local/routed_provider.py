"""Routed LLM Provider for JARVIS.

Wraps model providers (Ollama and optional Cloud) and intercepts inference calls
to dispatch them to specialized models based on ModelRouter decisions.
Preserves the unified LLMProvider interface with zero breaking changes.
"""

from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional

from jarvis.core.llm_provider import LLMProvider, ModelRole
from jarvis.core.router import ModelRouter, RoutingDecision, TaskType, default_model_router
from jarvis.subsystems.local.ollama_provider import OllamaProvider

logger = logging.getLogger("jarvis.routed_provider")


class RoutedLLMProvider(LLMProvider):
    """Router-aware LLMProvider that dynamically selects the best model for each task."""

    def __init__(
        self,
        router: Optional[ModelRouter] = None,
        local_provider: Optional[LLMProvider] = None,
        cloud_provider: Optional[LLMProvider] = None,
    ):
        self.router = router or default_model_router
        self.local_provider = local_provider or OllamaProvider()
        self.cloud_provider = cloud_provider
        self.last_decision: Optional[RoutingDecision] = None

    def _get_available_models(self) -> List[str]:
        """Queries local provider for installed models if supported."""
        if hasattr(self.local_provider, "list_models"):
            try:
                return self.local_provider.list_models()
            except Exception:
                pass
        return []

    def route_request(
        self,
        prompt: str,
        role: Optional[ModelRole] = None,
        model: Optional[str] = None,
        has_images: bool = False,
        **kwargs,
    ) -> RoutingDecision:
        """Determines the routing decision for a request."""
        if model:
            # Explicit model override
            return RoutingDecision(
                task_type=TaskType.GENERAL,
                role=role or ModelRole.REASONING,
                model_name=model,
                provider_type="local",
                confidence=1.0,
                reasoning=f"Explicit model override: {model}",
                fallback_models=[],
            )

        available = self._get_available_models()
        decision = self.router.route(
            prompt,
            role=role,
            available_models=available,
            has_images=has_images,
        )
        self.last_decision = decision
        return decision

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        role: Optional[ModelRole] = None,
        **kwargs,
    ) -> str:
        decision = self.route_request(prompt, role=role, model=model, **kwargs)
        target_model = decision.model_name
        target_provider = (
            self.cloud_provider
            if decision.provider_type == "cloud" and self.cloud_provider
            else self.local_provider
        )

        try:
            return target_provider.generate(
                prompt,
                system_prompt=system_prompt,
                model=target_model,
                role=decision.role,
                **kwargs,
            )
        except Exception as primary_exc:
            logger.warning(
                f"Primary model '{target_model}' execution failed: {primary_exc}. Attempting fallbacks..."
            )
            # Try fallback models
            for fallback_model in decision.fallback_models:
                try:
                    return self.local_provider.generate(
                        prompt,
                        system_prompt=system_prompt,
                        model=fallback_model,
                        role=ModelRole.REASONING,
                        **kwargs,
                    )
                except Exception:
                    continue
            raise primary_exc

    def structured_output(
        self,
        prompt: str,
        schema: Dict[str, Any],
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        role: Optional[ModelRole] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        decision = self.route_request(prompt, role=role, model=model, **kwargs)
        target_model = decision.model_name
        target_provider = (
            self.cloud_provider
            if decision.provider_type == "cloud" and self.cloud_provider
            else self.local_provider
        )

        try:
            return target_provider.structured_output(
                prompt,
                schema=schema,
                system_prompt=system_prompt,
                model=target_model,
                role=decision.role,
                **kwargs,
            )
        except Exception as primary_exc:
            logger.warning(
                f"Primary model '{target_model}' structured_output failed: {primary_exc}. Attempting fallbacks..."
            )
            for fallback_model in decision.fallback_models:
                try:
                    return self.local_provider.structured_output(
                        prompt,
                        schema=schema,
                        system_prompt=system_prompt,
                        model=fallback_model,
                        role=ModelRole.REASONING,
                        **kwargs,
                    )
                except Exception:
                    continue
            raise primary_exc

    def embed(
        self,
        text: str,
        model: Optional[str] = None,
        role: Optional[ModelRole] = None,
        **kwargs,
    ) -> List[float]:
        decision = self.route_request(text, role=role or ModelRole.EMBEDDING, model=model, **kwargs)
        return self.local_provider.embed(text, model=decision.model_name, role=decision.role, **kwargs)

    def vision(
        self,
        image_data: str,
        prompt: str,
        model: Optional[str] = None,
        role: Optional[ModelRole] = None,
        **kwargs,
    ) -> str:
        decision = self.route_request(prompt, role=role or ModelRole.VISION, model=model, has_images=True, **kwargs)
        target_provider = (
            self.cloud_provider
            if decision.provider_type == "cloud" and self.cloud_provider
            else self.local_provider
        )
        return target_provider.vision(image_data, prompt, model=decision.model_name, role=decision.role, **kwargs)
