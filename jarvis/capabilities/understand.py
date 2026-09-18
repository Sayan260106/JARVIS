import re
from typing import Any, Dict, List
from jarvis.capabilities.base import UnderstandCapability
from jarvis.core.schemas import TaskObjective, IntentCategory


class DefaultUnderstandCapability(UnderstandCapability):
    """Parses user input into structured objectives with entity extraction and ambiguity detection."""

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
        sub_goals: List[str] = []
        extracted_entities: Dict[str, Any] = {}

        # 1. Compound multi-step task detection (e.g. "Open Notepad, type Hello, save it as test.txt")
        compound_match = self._parse_compound_editor_task(cleaned)
        if compound_match:
            app_name = compound_match["app_name"]
            text_to_type = compound_match["text"]
            file_name = compound_match["file_name"]

            extracted_entities = {
                "app_name": app_name,
                "text": text_to_type,
                "file_path": file_name,
            }
            sub_goals = [
                f"Open application '{app_name}'",
                f"Type text '{text_to_type}' into {app_name}",
                f"Save document as '{file_name}'",
            ]
            return TaskObjective(
                raw_input=cleaned,
                intent=IntentCategory.TASK_AUTOMATION,
                description=f"Open {app_name}, type '{text_to_type}', and save as '{file_name}'.",
                target_criteria=f"Application '{app_name}' launched, text '{text_to_type}' entered, and file '{file_name}' verified on disk.",
                context=context,
                sub_goals=sub_goals,
                extracted_entities=extracted_entities,
                is_ambiguous=False,
            )

        # 2. General Intent classification heuristics
        if any(w in lower for w in ["automate", "backup", "sync", "organize"]):
            intent = IntentCategory.TASK_AUTOMATION
        elif any(w in lower for w in ["run", "execute", "create", "delete", "mkdir", "write", "open"]):
            intent = IntentCategory.SYSTEM_COMMAND
        elif any(w in lower for w in ["search", "find online", "browse", "look up", "google"]):
            intent = IntentCategory.RESEARCH
        elif any(w in lower for w in ["play", "pause", "volume", "music", "mute"]):
            intent = IntentCategory.MEDIA_CONTROL
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
            sub_goals=sub_goals,
            extracted_entities=extracted_entities,
        )

    def _parse_compound_editor_task(self, text: str) -> Dict[str, str] | None:
        """Parses patterns like 'Open Notepad, type Hello, save it as test.txt'."""
        # Normalize punctuation
        norm = text.rstrip(".").strip()

        # Regex for 'open <app>, type <text>, save (it)? as <file>'
        pattern = re.compile(
            r"open\s+([a-zA-Z0-9_\-\s]+?)"
            r"(?:,\s*|\s+and\s+|\s*;\s*|\s+then\s+)"
            r"(?:type|write|input)\s+['\"]?(.+?)['\"]?"
            r"(?:,\s*|\s+and\s+|\s*;\s*|\s+then\s+)"
            r"(?:save\s+(?:it\s+)?as|save\s+to|write\s+to)\s+['\"]?([^\s'\"]+)['\"]?",
            re.IGNORECASE,
        )
        m = pattern.search(norm)
        if m:
            return {
                "app_name": m.group(1).strip(),
                "text": m.group(2).strip(),
                "file_name": m.group(3).strip(),
            }

        return None

