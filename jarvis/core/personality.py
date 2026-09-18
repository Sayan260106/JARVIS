"""Personality Engine for JARVIS (Phase 11).

Provides an interaction styling layer without claiming artificial consciousness:
- Tone, Humor, Formality, Warmth, Confidence, Curiosity
- Dynamic Emotional States:
    Task success     -> slightly positive response
    Task failure     -> calm explanation
    Repeated failure -> mild frustration-style wording
    User appreciation -> warm response

Personality never overrides factual reasoning or tool execution safety.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
import re
from typing import Any, Dict, List, Optional


class EmotionalState(str, Enum):
    """Observable interaction states reflecting conversational and task context."""
    NEUTRAL = "NEUTRAL"
    PLEASED = "PLEASED"
    CALM_ANALYTIC = "CALM_ANALYTIC"
    MILDLY_PERPLEXED = "MILDLY_PERPLEXED"
    WARM_APPRECIATIVE = "WARM_APPRECIATIVE"
    FOCUSED = "FOCUSED"


@dataclass
class PersonalityConfig:
    """Configurable personality traits for JARVIS."""
    tone: str = "polite_witty"      # Polite, articulate, subtly witty British understatement
    humor: float = 0.35             # 0.0 (stoic) to 1.0 (comedic)
    formality: float = 0.75         # 0.0 (casual) to 1.0 (formal butler / advisor)
    warmth: float = 0.65            # 0.0 (clinical) to 1.0 (warm, supportive)
    confidence: float = 0.90        # 0.0 (tentative) to 1.0 (authoritative)
    curiosity: float = 0.50         # 0.0 (purely reactive) to 1.0 (inquiring)
    address_title: str = "sir"      # Courteous title when formality > 0.6


class PersonalityEngine:
    """Adapts phrasing and interaction tone based on task outcome and user sentiment."""

    def __init__(self, config: Optional[PersonalityConfig] = None):
        self.config = config or PersonalityConfig()
        self.current_state: EmotionalState = EmotionalState.NEUTRAL
        self.consecutive_failures: int = 0

    def is_user_appreciation(self, text: str) -> bool:
        """Detects whether user is expressing gratitude or appreciation."""
        cleaned = text.lower().strip()
        triggers = [
            "thank you", "thanks", "great job", "awesome", "good job",
            "well done", "brilliant", "appreciate it", "you're the best",
            "nice work", "superb", "excellent",
        ]
        return any(t in cleaned for t in triggers)

    def on_task_success(self, task_name: str, metrics: Optional[Dict[str, Any]] = None) -> str:
        """Generates a slightly positive response upon successful task completion."""
        self.consecutive_failures = 0
        self.current_state = EmotionalState.PLEASED
        title = f", {self.config.address_title}" if self.config.formality >= 0.6 else ""

        phrasings = [
            f"All operations for '{task_name}' completed cleanly{title}. Everything is in order.",
            f"Successfully executed '{task_name}'{title}. Results have been verified.",
            f"Done{title}. I've verified the outcome and everything concluded without issue.",
        ]
        return phrasings[0]

    def on_task_failure(self, task_name: str, error: str) -> str:
        """Generates a calm, analytical explanation upon first task failure."""
        self.consecutive_failures += 1
        self.current_state = EmotionalState.CALM_ANALYTIC
        title = f", {self.config.address_title}" if self.config.formality >= 0.6 else ""

        return (
            f"It appears '{task_name}' encountered an impediment{title}. "
            f"Specifically: {error}. I am investigating the cause."
        )

    def on_repeated_failure(self, task_name: str, attempts: int, error: str) -> str:
        """Generates mild frustration-style wording on recurring failures without fake consciousness."""
        self.consecutive_failures = attempts
        self.current_state = EmotionalState.MILDLY_PERPLEXED
        title = f", {self.config.address_title}" if self.config.formality >= 0.6 else ""

        return (
            f"Right{title}. That is the {attempts}th consecutive failure attempting '{task_name}'. "
            f"The underlying issue ({error}) persists despite automated recovery attempts. "
            "I suggest we inspect the configuration before continuing."
        )

    def on_user_appreciation(self, query: str) -> str:
        """Generates a warm, courteous response to user appreciation."""
        self.current_state = EmotionalState.WARM_APPRECIATIVE
        title = f", {self.config.address_title}" if self.config.formality >= 0.6 else ""

        phrasings = [
            f"Always a pleasure to be of service{title}.",
            f"Happy to assist{title}. Let me know what you require next.",
            f"Much obliged{title}. I'm glad that met your expectations.",
        ]
        return phrasings[0]

    def format_status_greeting(self) -> str:
        """Standard courteous greeting for the UI listening state."""
        title = f", {self.config.address_title}" if self.config.formality >= 0.7 else ""
        return f"How may I assist you{title}?"

    def stylize_response(self, raw_text: str, context_state: Optional[EmotionalState] = None) -> str:
        """Applies stylistic polish to raw text conforming to personality traits."""
        if context_state:
            self.current_state = context_state

        # Personality never alters purely structured json or system error payloads
        if raw_text.startswith("{") or raw_text.startswith("["):
            return raw_text

        # Ensure courteous tone without overriding content
        cleaned = raw_text.strip()
        if self.current_state == EmotionalState.WARM_APPRECIATIVE and not cleaned.endswith((".", "!", "?")):
            cleaned += "."
        return cleaned
