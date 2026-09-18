"""Core Model Abstraction Layer for JARVIS.

Provides a unified interface decoupling JARVIS from any single LLM or vendor:
- Fast model -> Intent classification
- Reasoning-capable model -> Planning & complex execution
- Vision model -> Screen & desktop analysis
- Embedding model -> Semantic memory retrieval

Concrete providers (such as OllamaProvider) implement this abstraction.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional


class ModelRole(str, Enum):
    """Functional role taxonomy for specialized local and remote models."""
    FAST = "FAST"                 # Fast SLM for intent classification & routing
    REASONING = "REASONING"       # Reasoning-capable model for planning & complex task orchestration
    VISION = "VISION"             # Multimodal vision model for screen/image analysis
    EMBEDDING = "EMBEDDING"       # Embedding model for semantic vector memory retrieval


class LLMProvider(ABC):
    """Abstract base class for model providers (Ollama, OpenAI, Gemini, Mock, etc.)."""

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        role: Optional[ModelRole] = None,
        **kwargs,
    ) -> str:
        """Generate a direct conversational or task response string.

        Args:
            prompt: User or task prompt.
            system_prompt: Optional custom persona / system prompt.
            model: Optional direct model name override.
            role: Functional role (FAST, REASONING, VISION, EMBEDDING).
            **kwargs: Provider-specific options (temperature, top_p, etc.).
        """
        pass

    @abstractmethod
    def structured_output(
        self,
        prompt: str,
        schema: Dict[str, Any],
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        role: Optional[ModelRole] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Generate structured data strictly conforming to the given JSON schema.

        Args:
            prompt: Instruction prompt requesting structured data.
            schema: Expected JSON schema dictionary.
            system_prompt: Optional persona / instructions.
            model: Optional direct model name override.
            role: Functional role (defaults to REASONING or FAST).
            **kwargs: Additional parameters.
        """
        pass

    @abstractmethod
    def embed(
        self,
        text: str,
        model: Optional[str] = None,
        role: Optional[ModelRole] = None,
        **kwargs,
    ) -> List[float]:
        """Generate a dense numerical vector embedding for text.

        Args:
            text: Input text string to vectorize.
            model: Optional embedding model name override.
            role: Functional role (defaults to EMBEDDING).
            **kwargs: Additional options.
        """
        pass

    @abstractmethod
    def vision(
        self,
        image_data: str,
        prompt: str,
        model: Optional[str] = None,
        role: Optional[ModelRole] = None,
        **kwargs,
    ) -> str:
        """Analyze a screen capture or image with a multimodal vision model.

        Args:
            image_data: Base64-encoded image string.
            prompt: Question or diagnostic instruction.
            model: Optional vision model name override.
            role: Functional role (defaults to VISION).
            **kwargs: Additional options.
        """
        pass
