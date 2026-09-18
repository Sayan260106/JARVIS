"""Task-Based Model Router for JARVIS.

Directs incoming tasks and prompts to specialized models instead of sending
everything to a single model:
- Simple command -> Small fast local model (qwen2.5:1.5b)
- Planning -> Better reasoning model (qwen2.5:3b / qwen2.5:7b)
- Document summary -> Local LLM (qwen2.5:3b)
- Coding -> Dedicated coding model (qwen2.5-coder:1.5b)
- Vision -> Vision model (llava)
- Embeddings -> Dedicated embedding model (nomic-embed-text)
- Optional cloud -> Cloud model (gemini-1.5-flash / gpt-4o)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
import re
from typing import Any, Dict, List, Optional

from jarvis.core.llm_provider import ModelRole
from jarvis.core.model_manager import ModelManager, default_model_manager


class TaskType(str, Enum):
    """Categorization of agent tasks for specialized model dispatch."""
    SIMPLE_COMMAND = "SIMPLE_COMMAND"       # Fast local model
    PLANNING = "PLANNING"                   # Better reasoning model
    DOCUMENT_SUMMARY = "DOCUMENT_SUMMARY"   # Local LLM
    CODING = "CODING"                       # Coding model
    VISION = "VISION"                       # Vision model
    EMBEDDING = "EMBEDDING"                 # Embedding model
    CLOUD_REASONING = "CLOUD_REASONING"     # Optional cloud model
    GENERAL = "GENERAL"                     # Fast/Reasoning conversational fallback


@dataclass
class RoutingDecision:
    """The structured decision produced by the model router."""
    task_type: TaskType
    role: ModelRole
    model_name: str
    provider_type: str = "local"            # "local" or "cloud"
    confidence: float = 1.0
    reasoning: str = ""
    fallback_models: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_type": self.task_type.value,
            "role": self.role.value,
            "model_name": self.model_name,
            "provider_type": self.provider_type,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "fallback_models": self.fallback_models,
        }


class ModelRouter:
    """Intelligently routes prompts to specialized models with fallback support."""

    # Coding patterns: keywords, code fences, language indicators
    _CODING_PATTERNS = [
        r"```[a-zA-Z0-9_\+\-]*",
        r"\b(?:def|class|function|import|from\s+\w+\s+import|async\s+def|return|const|let|var)\b",
        r"\b(?:write\s+a\s+(?:python|javascript|typescript|c\+\+|bash|script|code|function))\b",
        r"\b(?:debug|refactor|fix\s+the\s+syntax|fix\s+bug|unit\s+test|regex|sql\s+query)\b",
        r"\b(?:dockerfile|npm\s+install|pip\s+install|git\s+commit)\b",
    ]

    # Document summary / study patterns
    _DOC_SUMMARY_PATTERNS = [
        r"\b(?:summarize|summary|summarise)\b",
        r"\b(?:lecture|pdf|docx|pptx|notes|exam|revision|syllabus|study\s+guide)\b",
        r"\b(?:extract\s+topics|key\s+concepts|cornell\s+notes|generate\s+questions)\b",
    ]

    # Planning & complex decomposition patterns
    _PLANNING_PATTERNS = [
        r"\b(?:plan|decompose|break\s+down|step\s+by\s+step|multi-step|workflow)\b",
        r"\b(?:first\s+.+?\s+then\s+.+?)\b",
        r"\b(?:find\s+.+?\s+and\s+then\s+.+?)\b",
        r"\b(?:diagnose\s+.+?\s+and\s+repair)\b",
    ]

    # Simple system commands
    _SIMPLE_COMMAND_PATTERNS = [
        r"^(?:open|launch|start)\s+[a-zA-Z0-9_\-\s]{1,30}$",
        r"^(?:close|quit|kill)\s+[a-zA-Z0-9_\-\s]{1,30}$",
        r"^(?:lock|sleep|shutdown|restart)\s*(?:the\s+)?(?:computer|pc|system)?$",
        r"^(?:volume\s+(?:up|down|mute|\d+)|mute)$",
        r"^(?:create|make)\s+(?:a\s+)?folder\s+.+$",
        r"^(?:what\s+time\s+is\s+it|date|who\s+are\s+you)$",
    ]

    # Vision cues
    _VISION_PATTERNS = [
        r"\b(?:screenshot|screen|image|look\s+at\s+the\s+screen|what\s+is\s+on\s+(?:my\s+)?screen)\b",
        r"\b(?:ui\s+element|locate\s+button|find\s+icon|read\s+the\s+image)\b",
    ]

    # Cloud preferences
    _CLOUD_PATTERNS = [
        r"\b(?:use\s+cloud|cloud\s+model|gemini|gpt-4|claude|deep\s+research)\b",
    ]

    def __init__(self, model_manager: Optional[ModelManager] = None):
        self.model_manager = model_manager or default_model_manager

    def classify_task(
        self,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
        has_images: bool = False,
    ) -> TaskType:
        """Classifies a user prompt or task into a TaskType."""
        if has_images:
            return TaskType.VISION

        text = prompt.strip()
        lower = text.lower()

        # 1. Cloud explicitly requested
        if any(re.search(p, lower) for p in self._CLOUD_PATTERNS):
            return TaskType.CLOUD_REASONING

        # 2. Vision cues in prompt
        if any(re.search(p, lower) for p in self._VISION_PATTERNS):
            return TaskType.VISION

        # 3. Coding detection
        if any(re.search(p, text, re.IGNORECASE) for p in self._CODING_PATTERNS):
            return TaskType.CODING

        # 4. Document summary / study
        if any(re.search(p, lower) for p in self._DOC_SUMMARY_PATTERNS):
            return TaskType.DOCUMENT_SUMMARY

        # 5. Planning
        if any(re.search(p, lower) for p in self._PLANNING_PATTERNS):
            return TaskType.PLANNING

        # 6. Simple command detection (short imperatives)
        if any(re.search(p, lower) for p in self._SIMPLE_COMMAND_PATTERNS) or len(text.split()) <= 4:
            return TaskType.SIMPLE_COMMAND

        return TaskType.GENERAL

    def route(
        self,
        prompt: str,
        role: Optional[ModelRole] = None,
        task_type: Optional[TaskType] = None,
        available_models: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None,
        has_images: bool = False,
    ) -> RoutingDecision:
        """Determines the optimal model role, model name, and fallback chain."""
        # 1. Determine task type
        effective_task_type = task_type or self.classify_task(prompt, context=context, has_images=has_images)

        # 2. Map task type to ModelRole if not explicitly overridden
        if role is not None:
            effective_role = role
        else:
            role_map = {
                TaskType.SIMPLE_COMMAND: ModelRole.FAST,
                TaskType.PLANNING: ModelRole.REASONING,
                TaskType.DOCUMENT_SUMMARY: ModelRole.DOCUMENT,
                TaskType.CODING: ModelRole.CODING,
                TaskType.VISION: ModelRole.VISION,
                TaskType.EMBEDDING: ModelRole.EMBEDDING,
                TaskType.CLOUD_REASONING: ModelRole.CLOUD,
                TaskType.GENERAL: ModelRole.FAST,
            }
            effective_role = role_map.get(effective_task_type, ModelRole.REASONING)

        # 3. Resolve preferred model and fallbacks
        preferred_model = self.model_manager.get_model(effective_role)
        resolved_model = self.model_manager.resolve_model_with_fallbacks(
            effective_role, available_models=available_models
        )
        fallbacks = self.model_manager.get_fallback_chain(effective_role)

        provider_type = "cloud" if effective_role == ModelRole.CLOUD else "local"

        reasoning = (
            f"Classified task as '{effective_task_type.value}' -> mapped to role '{effective_role.value}'. "
            f"Selected model '{resolved_model}' (preferred: '{preferred_model}')."
        )

        return RoutingDecision(
            task_type=effective_task_type,
            role=effective_role,
            model_name=resolved_model,
            provider_type=provider_type,
            confidence=0.95,
            reasoning=reasoning,
            fallback_models=fallbacks,
        )


# Global singleton instance
default_model_router = ModelRouter()
