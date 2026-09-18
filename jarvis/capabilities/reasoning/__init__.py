"""JARVIS Modular Internal Reasoning Architecture.

Decouples reasoning into specialized components:
User -> Intent Analyzer -> Task Planner -> Web Agent / Tool Agent -> Observer -> Verifier -> Pass/Recovery -> Replan
"""

from jarvis.capabilities.reasoning.intent_analyzer import (
    IntentAnalyzer,
    UserIntent,
    IntentType,
)
from jarvis.capabilities.reasoning.reasoning_pipeline import (
    ReasoningPipeline,
    ReasoningResult,
    ReasoningStep,
)

__all__ = [
    "IntentAnalyzer",
    "UserIntent",
    "IntentType",
    "ReasoningPipeline",
    "ReasoningResult",
    "ReasoningStep",
]
