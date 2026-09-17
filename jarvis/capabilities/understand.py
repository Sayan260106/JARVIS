"""1. UNDERSTAND Capability — 'What did the user mean?'"""

from typing import Any, Dict
from jarvis.capabilities.base import UnderstandCapability
from jarvis.core.schemas import TaskObjective, IntentCategory


class DefaultUnderstandCapability(UnderstandCapability):
    """Parses user input into structured objectives with ambiguity detection."""

    def understand(self, user_input: str, context: Dict[str, Any]) -> TaskObjective:
        cleaned = user_input.strip()
        if not cleaned:
            return TaskObjective(
                raw_input=user_input,
                intent=IntentCategory.UNKNOWN,
                description="Empty request",
                target_criteria="",
                is_ambiguous=True,
                clarification_needed="Please provide a task or question for JARVIS to execute.",
            )

        lower = cleaned.lower()

        # Intent classification heuristics (can be backed by LLM or SLM)
        if any(w in lower for w in ["run", "execute", "create", "delete", "mkdir", "write", "open"]):
            intent = IntentCategory.SYSTEM_COMMAND
        elif any(w in lower for w in ["search", "find online", "browse", "look up", "google"]):
            intent = IntentCategory.RESEARCH
        elif any(w in lower for w in ["play", "pause", "volume", "music", "mute"]):
            intent = IntentCategory.MEDIA_CONTROL
        elif any(w in lower for w in ["automate", "backup", "sync", "organize"]):
            intent = IntentCategory.TASK_AUTOMATION
        else:
            intent = IntentCategory.QUERY

        # Ambiguity check (e.g. extremely short or underspecified commands)
        is_ambiguous = False
        clarification_needed = None

        if len(cleaned.split()) == 1 and intent in (IntentCategory.SYSTEM_COMMAND, IntentCategory.TASK_AUTOMATION):
            is_ambiguous = True
            clarification_needed = f"The objective '{cleaned}' is missing specific target arguments or file paths."

        return TaskObjective(
            raw_input=cleaned,
            intent=intent,
            description=f"Accomplish user goal: {cleaned}",
            target_criteria=f"Goal '{cleaned}' successfully achieved and verified.",
            context=context,
            is_ambiguous=is_ambiguous,
            clarification_needed=clarification_needed,
        )
