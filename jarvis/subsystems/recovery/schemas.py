"""Data schemas for Autonomous Recovery 2.0 Subsystem (Phase 14).

Defines typed contracts for diagnostic classification, alternate selectors,
tool fallbacks, prerequisite injection, and recovery resolution.
"""

from __future__ import annotations
from dataclasses import dataclass, field
import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from jarvis.core.schemas import PlanStep, RecoveryStrategy


class FailureCategory(str, Enum):
    """Categorization of step execution failures."""
    PROCESS_NOT_RUNNING = "PROCESS_NOT_RUNNING"
    ELEMENT_NOT_FOUND = "ELEMENT_NOT_FOUND"
    NAVIGATION_FAILED = "NAVIGATION_FAILED"
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    WINDOW_NOT_FOUND = "WINDOW_NOT_FOUND"
    NETWORK_ERROR = "NETWORK_ERROR"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    TIMEOUT = "TIMEOUT"
    UNKNOWN = "UNKNOWN"


@dataclass
class FailureDiagnosis:
    """The diagnostic answer to 'Why did it fail?'."""
    category: FailureCategory
    root_cause: str
    attempted_action: str
    evidence: str
    suggested_strategy: RecoveryStrategy
    context_snapshot: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category.value,
            "root_cause": self.root_cause,
            "attempted_action": self.attempted_action,
            "evidence": self.evidence,
            "suggested_strategy": self.suggested_strategy.value,
            "context_snapshot": self.context_snapshot,
            "timestamp": self.timestamp,
        }


@dataclass
class AlternateSelector:
    """An alternate locator derived through semantic, fuzzy, or structural analysis."""
    selector_type: str  # "exact_text", "acronym_expansion", "fuzzy_text", "css", "aria", "in_page_search"
    value: str
    confidence: float = 0.8
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "selector_type": self.selector_type,
            "value": self.value,
            "confidence": self.confidence,
            "description": self.description,
        }


@dataclass
class RecoveryResolution:
    """The formulated adaptation to resolve the diagnosed failure."""
    strategy: RecoveryStrategy
    diagnosis: FailureDiagnosis
    explanation: str
    modified_step: Optional[PlanStep] = None
    injected_steps: List[PlanStep] = field(default_factory=list)
    retry_count: int = 1
    max_retries: int = 3
    escalate: bool = False
    user_prompt: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy": self.strategy.value,
            "diagnosis": self.diagnosis.to_dict(),
            "explanation": self.explanation,
            "injected_steps_count": len(self.injected_steps),
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "escalate": self.escalate,
            "user_prompt": self.user_prompt,
        }
