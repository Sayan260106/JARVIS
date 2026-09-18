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

        # 2. Windows Control Actions detection
        win_control = self._parse_windows_control_action(cleaned)
        if win_control:
            action = win_control["action"]
            extracted_entities = win_control.get("entities", {})
            intent = win_control.get("intent", IntentCategory.SYSTEM_COMMAND)
            desc = win_control.get("description", f"Execute Windows action: {action}")
            target_crit = win_control.get("target_criteria", f"Windows action '{action}' verified.")
            return TaskObjective(
                raw_input=cleaned,
                intent=intent,
                description=desc,
                target_criteria=target_crit,
                context=context,
                sub_goals=[desc],
                extracted_entities={"action": action, **extracted_entities},
                is_ambiguous=False,
            )

        # 3. General Intent classification heuristics
        if any(w in lower for w in ["automate", "backup", "sync", "organize"]):
            intent = IntentCategory.TASK_AUTOMATION
        elif any(w in lower for w in ["run", "execute", "create", "delete", "mkdir", "write", "open", "close", "kill"]):
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

    def _parse_windows_control_action(self, text: str) -> Dict[str, Any] | None:
        """Parses natural language commands directly into typed Windows control actions."""
        norm = text.rstrip(".").strip()
        lower = norm.lower()

        # 1. Shutdown / Power Off
        if re.match(r"^(?:shut\s*down|power\s*off|turn\s*off)\s*(?:the\s+)?(?:computer|pc|system)?$", lower):
            return {
                "action": "shutdown",
                "entities": {"delay_seconds": 60},
                "intent": IntentCategory.SYSTEM_COMMAND,
                "description": "Schedule computer shutdown (60s delay)",
                "target_criteria": "Computer shutdown scheduled.",
            }

        # 2. Restart / Reboot
        if re.match(r"^(?:restart|reboot)\s*(?:the\s+)?(?:computer|pc|system)?$", lower):
            return {
                "action": "restart",
                "entities": {"delay_seconds": 60},
                "intent": IntentCategory.SYSTEM_COMMAND,
                "description": "Schedule computer restart (60s delay)",
                "target_criteria": "Computer restart scheduled.",
            }

        # 3. Lock PC
        if re.match(r"^lock\s*(?:the\s+)?(?:computer|pc|system|screen)?$", lower):
            return {
                "action": "lock_pc",
                "entities": {},
                "intent": IntentCategory.SYSTEM_COMMAND,
                "description": "Lock the workstation",
                "target_criteria": "Workstation locked.",
            }

        # 4. Sleep PC
        if re.match(r"^(?:sleep|put\s+to\s+sleep)\s*(?:the\s+)?(?:computer|pc|system)?$", lower):
            return {
                "action": "sleep_pc",
                "entities": {},
                "intent": IntentCategory.SYSTEM_COMMAND,
                "description": "Put computer to sleep",
                "target_criteria": "Computer in sleep mode.",
            }

        # 5. Create Folder: "Create a folder called GATE 2027", "Make folder Work", "mkdir test"
        m_folder = re.match(r"^(?:create|make|mkdir)\s+(?:a\s+)?(?:folder|directory)\s+(?:called\s+|named\s+)?['\"]?(.+?)['\"]?$", norm, re.IGNORECASE)
        if m_folder:
            folder_path = m_folder.group(1).strip()
            return {
                "action": "create_folder",
                "entities": {"path": folder_path},
                "intent": IntentCategory.SYSTEM_COMMAND,
                "description": f"Create folder '{folder_path}'",
                "target_criteria": f"Folder '{folder_path}' verified on filesystem.",
            }

        # 6. Close Application: "Close Chrome", "Quit Notepad", "Kill VS Code"
        m_close = re.match(r"^(?:close|quit|exit|kill|terminate)\s+(?:application\s+|app\s+|window\s+|process\s+)?(.+)$", norm, re.IGNORECASE)
        if m_close:
            app_target = m_close.group(1).strip()
            return {
                "action": "close_application",
                "entities": {"app_name": app_target},
                "intent": IntentCategory.SYSTEM_COMMAND,
                "description": f"Close application '{app_target}'",
                "target_criteria": f"Application '{app_target}' closed.",
            }

        # 7. Focus Window: "Focus Chrome", "Switch to VS Code"
        m_focus = re.match(r"^(?:focus|switch\s+to)\s+(?:window\s+)?(.+)$", norm, re.IGNORECASE)
        if m_focus:
            win_title = m_focus.group(1).strip()
            return {
                "action": "focus_window",
                "entities": {"title": win_title},
                "intent": IntentCategory.SYSTEM_COMMAND,
                "description": f"Focus window '{win_title}'",
                "target_criteria": f"Window '{win_title}' focused.",
            }

        # 8. Minimize / Maximize / Restore Window
        m_win = re.match(r"^(minimize|maximize|restore)\s+(?:window\s+)?(.+)$", norm, re.IGNORECASE)
        if m_win:
            win_action = m_win.group(1).lower()
            win_title = m_win.group(2).strip()
            return {
                "action": "window_control",
                "entities": {"action": win_action, "title": win_title},
                "intent": IntentCategory.SYSTEM_COMMAND,
                "description": f"{win_action.capitalize()} window '{win_title}'",
                "target_criteria": f"Window '{win_title}' {win_action}d.",
            }

        # 9. Volume Control
        m_vol_set = re.match(r"^(?:set\s+)?volume\s+(?:to\s+)?(\d+)(?:%)?$", lower)
        if m_vol_set:
            level = int(m_vol_set.group(1))
            return {
                "action": "volume_control",
                "entities": {"vol_action": "set", "level": level},
                "intent": IntentCategory.MEDIA_CONTROL,
                "description": f"Set volume to {level}%",
                "target_criteria": f"Volume set to {level}%.",
            }
        if re.match(r"^mute\s*(?:volume|audio|sound)?$", lower):
            return {
                "action": "volume_control",
                "entities": {"vol_action": "mute"},
                "intent": IntentCategory.MEDIA_CONTROL,
                "description": "Mute system audio",
                "target_criteria": "Audio muted.",
            }
        if re.match(r"^unmute\s*(?:volume|audio|sound)?$", lower):
            return {
                "action": "volume_control",
                "entities": {"vol_action": "unmute"},
                "intent": IntentCategory.MEDIA_CONTROL,
                "description": "Unmute system audio",
                "target_criteria": "Audio unmuted.",
            }

        # 10. Open Application / Directory: "Open VS Code", "Open Downloads", "Launch notepad"
        m_open = re.match(r"^(?:open|launch|start)\s+(.+)$", norm, re.IGNORECASE)
        if m_open:
            app_target = m_open.group(1).strip()
            # Do not hijack compound sentences with commas or 'and'
            if not any(sep in app_target.lower() for sep in [",", " and ", ";", " then "]):
                return {
                    "action": "open_application",
                    "entities": {"app_name": app_target},
                    "intent": IntentCategory.SYSTEM_COMMAND,
                    "description": f"Open application '{app_target}'",
                    "target_criteria": f"Application '{app_target}' launched and active.",
                }

        return None


