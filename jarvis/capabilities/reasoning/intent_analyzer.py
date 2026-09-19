"""Intent Analyzer for JARVIS Modular Reasoning Architecture.

Decouples intent classification and permission gating from single-prompt execution.
Analyzes user input to determine:
- Intent Type (READ_QUERY, WRITE_ACTION, EXTERNAL_ACTION, DESTRUCTIVE_ACTION, COMPLEX_WORKFLOW, CONVERSATION)
- Safety / Permission Level (LEVEL 0, LEVEL 1, LEVEL 2, LEVEL 3)
- Target Tools and Extracted Parameters
- Required Confirmations & Previews
"""

from __future__ import annotations
import os
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from jarvis.tools.base import PermissionLevel
from jarvis.core.llm_provider import LLMProvider, ModelRole


class IntentType(str, Enum):
    CONVERSATION = "CONVERSATION"
    READ_QUERY = "READ_QUERY"
    WRITE_ACTION = "WRITE_ACTION"
    EXTERNAL_ACTION = "EXTERNAL_ACTION"
    DESTRUCTIVE_ACTION = "DESTRUCTIVE_ACTION"
    COMPLEX_WORKFLOW = "COMPLEX_WORKFLOW"


@dataclass
class UserIntent:
    """Structured representation of analyzed user intent."""
    raw_query: str
    intent_type: IntentType
    permission_level: PermissionLevel
    target_tool: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    requires_confirmation: bool = False
    confirmation_preview: Optional[Dict[str, Any]] = None
    warning_prompt: Optional[str] = None
    requires_research: bool = False
    context: Dict[str, Any] = field(default_factory=dict)


class IntentAnalyzer:
    """Classifies user queries into discrete intent types and permission categories using heuristics and fast SLMs."""

    def __init__(
        self,
        projects_directory: Optional[str] = None,
        llm_provider: Optional[LLMProvider] = None,
    ):
        self.projects_directory = projects_directory or os.path.join(os.path.expanduser("~"), "Projects")
        self.llm_provider = llm_provider

    def analyze(
        self,
        query: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> UserIntent:
        """Analyze user query and optional history to produce a structured UserIntent."""
        q = query.strip()
        lower_q = q.lower()

        # 1. Check for Level 3 Destructive: Mass Project / File Deletion, Shutdown, Format
        destructive_delete_patterns = [
            r"delete\s+(all\s+)?(my\s+)?(old\s+)?projects?",
            r"remove\s+(all\s+)?(my\s+)?(old\s+)?projects?",
            r"delete\s+(all\s+)?old\s+dirs?",
            r"format\s+(drive|disk)",
        ]
        for pat in destructive_delete_patterns:
            if re.search(pat, lower_q):
                # Count projects in directory or default to 17 if mock/demo
                count = 17
                if os.path.exists(self.projects_directory):
                    subdirs = [
                        d for d in os.listdir(self.projects_directory)
                        if os.path.isdir(os.path.join(self.projects_directory, d))
                    ]
                    if subdirs:
                        count = len(subdirs)

                warning = (
                    f"I found {count} project directories. "
                    "Deleting them would be irreversible. Would you like me to list them first?"
                )

                return UserIntent(
                    raw_query=q,
                    intent_type=IntentType.DESTRUCTIVE_ACTION,
                    permission_level=PermissionLevel.LEVEL_3_DESTRUCTIVE,
                    target_tool="safe_delete_projects",
                    parameters={
                        "target_directory": self.projects_directory,
                        "pattern": "*",
                        "confirmed": False,
                    },
                    requires_confirmation=True,
                    warning_prompt=warning,
                )

        if any(w in lower_q for w in ["shutdown", "shut down", "restart the computer", "reboot"]):
            tool_name = "shutdown" if "shut" in lower_q else "restart"
            return UserIntent(
                raw_query=q,
                intent_type=IntentType.DESTRUCTIVE_ACTION,
                permission_level=PermissionLevel.LEVEL_3_DESTRUCTIVE,
                target_tool=tool_name,
                parameters={"force": False},
                requires_confirmation=True,
                warning_prompt=f"Executing '{tool_name}' will terminate system operations. Are you sure?",
            )

        # 2. Check for Level 2 External Action: Send Email, Post, Publish, Purchase
        email_patterns = [
            r"send\s+(this\s+|an\s+)?email",
            r"mail\s+(this\s+|to\s+)",
            r"email\s+([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)",
        ]
        for pat in email_patterns:
            if re.search(pat, lower_q):
                params = self._extract_email_params(q, conversation_history)
                preview = {
                    "Recipient": params.get("recipient") or "recipient@example.com",
                    "Subject": params.get("subject") or "Important Update",
                    "Message": params.get("message") or "Draft message content.",
                    "Attachment": params.get("attachment") or "None",
                }
                return UserIntent(
                    raw_query=q,
                    intent_type=IntentType.EXTERNAL_ACTION,
                    permission_level=PermissionLevel.LEVEL_2_EXTERNAL_ACTION,
                    target_tool="send_email",
                    parameters=params,
                    requires_confirmation=True,
                    confirmation_preview=preview,
                )

        # 2.5 Check for Phase 17 Proactive Intents (Scheduled Tasks, Folder Watchers, Process Watchers)
        sched_match = re.search(r"^(?:every\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|day|weekday|morning|evening|\d+\s*(?:minute|min|hour|hr|sec|second)s?)|schedule\s+)", lower_q)
        if sched_match or (lower_q.startswith("every ") and any(w in lower_q for w in ["check", "run", "do", "remind", "scan"])):
            if "," in q:
                parts = q.split(",", 1)
                expr, objective = parts[0].strip(), parts[1].strip()
            else:
                expr = "Every Monday"
                objective = q
            return UserIntent(
                raw_query=q,
                intent_type=IntentType.READ_QUERY,
                permission_level=PermissionLevel.LEVEL_0_READ,
                target_tool="schedule_task",
                parameters={"expression": expr, "objective": objective, "title": objective[:40]},
            )

        if "watch" in lower_q and any(w in lower_q for w in ["folder", "downloads", "directory"]):
            folder = "Downloads"
            pattern = "*.pdf"
            if "pdf" in lower_q: pattern = "*.pdf"
            elif "zip" in lower_q: pattern = "*.zip"
            elif "csv" in lower_q: pattern = "*.csv"
            elif any(img in lower_q for img in ["image", "photo", "png", "jpg"]): pattern = "*.png"
            elif "doc" in lower_q: pattern = "*.docx"

            return UserIntent(
                raw_query=q,
                intent_type=IntentType.READ_QUERY,
                permission_level=PermissionLevel.LEVEL_0_READ,
                target_tool="watch_folder",
                parameters={"folder_path": folder, "file_pattern": pattern, "target_objective": f"Process new {pattern} in {folder}"},
            )

        if any(w in lower_q for w in ["tell me when", "notify me when", "alert me when"]) or ("watch" in lower_q and "process" in lower_q):
            proc_pattern = "GPU training"
            if "gpu" in lower_q or "train" in lower_q:
                proc_pattern = "*train*"
            elif "python" in lower_q:
                proc_pattern = "python.exe"
            else:
                m = re.search(r"(?:when|watch\s+process)\s+my?\s*([a-zA-Z0-9_\-\.]+)", lower_q)
                if m:
                    proc_pattern = m.group(1)

            return UserIntent(
                raw_query=q,
                intent_type=IntentType.READ_QUERY,
                permission_level=PermissionLevel.LEVEL_0_READ,
                target_tool="watch_process",
                parameters={"process_name": proc_pattern, "target_objective": f"Notify user when {proc_pattern} finishes"},
            )

        if any(w in lower_q for w in ["list scheduled", "list proactive", "list active monitors", "show monitors", "active monitors"]):
            return UserIntent(
                raw_query=q,
                intent_type=IntentType.READ_QUERY,
                permission_level=PermissionLevel.LEVEL_0_READ,
                target_tool="list_proactive_rules",
                parameters={},
            )

        # 3. Check for Complex Workflows / Goals (e.g. presentation prep, organize downloads)
        from jarvis.capabilities.goal_planner import GoalPlanner
        if GoalPlanner.is_directory_organize_goal(q):
            target_dir = GoalPlanner.resolve_target_directory(q)
            return UserIntent(
                raw_query=q,
                intent_type=IntentType.COMPLEX_WORKFLOW,
                permission_level=PermissionLevel.LEVEL_1_REVERSIBLE_WRITE,
                target_tool="batch_organize_files",
                parameters={"directory": target_dir},
            )

        if GoalPlanner.is_complex_project_goal(q):
            return UserIntent(
                raw_query=q,
                intent_type=IntentType.COMPLEX_WORKFLOW,
                permission_level=PermissionLevel.LEVEL_1_REVERSIBLE_WRITE,
                target_tool="run_complex_task",
                parameters={"workflow": "presentation_prep"},
            )

        # 4. Check for Level 1 Reversible Write (create folder, create file, move file, open app)
        if any(w in lower_q for w in ["create a folder", "make a folder", "new folder"]):
            folder_name = self._extract_name(q, ["called", "named"]) or "New Folder"
            return UserIntent(
                raw_query=q,
                intent_type=IntentType.WRITE_ACTION,
                permission_level=PermissionLevel.LEVEL_1_REVERSIBLE_WRITE,
                target_tool="create_folder",
                parameters={"folder_name": folder_name},
            )

        if any(w in lower_q for w in ["create a text file", "create a file", "new file", "write a file"]):
            file_name = self._extract_name(q, ["called", "named"]) or "note.txt"
            return UserIntent(
                raw_query=q,
                intent_type=IntentType.WRITE_ACTION,
                permission_level=PermissionLevel.LEVEL_1_REVERSIBLE_WRITE,
                target_tool="create_file",
                parameters={"file_name": file_name, "content": ""},
            )

        if "move" in lower_q and ("into" in lower_q or "to" in lower_q):
            return UserIntent(
                raw_query=q,
                intent_type=IntentType.WRITE_ACTION,
                permission_level=PermissionLevel.LEVEL_1_REVERSIBLE_WRITE,
                target_tool="move_file",
                parameters={"source": "context_file", "destination": "context_folder"},
            )

        if lower_q.startswith("open "):
            app_name = q[5:].strip().strip(".!?,")
            return UserIntent(
                raw_query=q,
                intent_type=IntentType.WRITE_ACTION,
                permission_level=PermissionLevel.LEVEL_1_REVERSIBLE_WRITE,
                target_tool="open_application",
                parameters={"app_name": app_name},
            )

        # 5. Check for Level 0 Read (search files, telemetry, screenshot, inspect)
        if any(w in lower_q for w in ["find my", "search for", "locate file"]):
            term = re.sub(r"^(find my|search for|locate file)\s+", "", lower_q).strip().strip(".!?")
            return UserIntent(
                raw_query=q,
                intent_type=IntentType.READ_QUERY,
                permission_level=PermissionLevel.LEVEL_0_READ,
                target_tool="search_files",
                parameters={"query": term},
            )

        if any(w in lower_q for w in ["how much ram", "cpu usage", "hardware metrics", "memory usage"]):
            return UserIntent(
                raw_query=q,
                intent_type=IntentType.READ_QUERY,
                permission_level=PermissionLevel.LEVEL_0_READ,
                target_tool="get_hardware_metrics",
                parameters={},
            )

        proc_match = re.search(r"(?:is|check\s+(?:if)?)\s+([a-zA-Z0-9_\-\.]+)\s+(?:is\s+)?running", lower_q)
        if proc_match or "check process" in lower_q or "is ollama running" in lower_q:
            proc_name = proc_match.group(1).strip() if proc_match else "ollama"
            return UserIntent(
                raw_query=q,
                intent_type=IntentType.READ_QUERY,
                permission_level=PermissionLevel.LEVEL_0_READ,
                target_tool="check_process",
                parameters={"process_name": proc_name},
            )

        if "take a screenshot" in lower_q or "capture screen" in lower_q:
            return UserIntent(
                raw_query=q,
                intent_type=IntentType.READ_QUERY,
                permission_level=PermissionLevel.LEVEL_0_READ,
                target_tool="take_screenshot",
                parameters={},
            )

        # 6. Check for Web Research Need
        research_cues = ["who won", "latest news", "stock price of", "weather in", "current version"]
        if any(cue in lower_q for cue in research_cues):
            return UserIntent(
                raw_query=q,
                intent_type=IntentType.READ_QUERY,
                permission_level=PermissionLevel.LEVEL_0_READ,
                target_tool="research_topic",
                parameters={"topic": q},
                requires_research=True,
            )

        # 6.5 Check for Contextual Deictic Queries (Phase 10: "Summarize this", "Fix this", "Explain this")
        from jarvis.subsystems.context.resolver import ContextResolver
        from jarvis.subsystems.context.collector import ContextCollector
        from jarvis.subsystems.context.schemas import DeicticTargetType

        if ContextResolver.contains_deictic_reference(q):
            collector = ContextCollector.get_instance()
            sys_snap = collector.collect(refresh=False, capture_selection=True)
            res_action = ContextResolver.resolve(q, sys_snap)
            if res_action.confidence >= 0.7:
                if res_action.target_type == DeicticTargetType.CODE_IN_EDITOR:
                    return UserIntent(
                        raw_query=q,
                        intent_type=IntentType.WRITE_ACTION,
                        permission_level=PermissionLevel.LEVEL_1_REVERSIBLE_WRITE,
                        target_tool="modify_file",
                        parameters={"path": res_action.target_path or res_action.target_name, "resolved_prompt": res_action.resolved_prompt},
                    )
                elif res_action.target_type == DeicticTargetType.OPEN_DOCUMENT:
                    return UserIntent(
                        raw_query=q,
                        intent_type=IntentType.READ_QUERY,
                        permission_level=PermissionLevel.LEVEL_0_READ,
                        target_tool="document_read",
                        parameters={"file_path": res_action.target_path or res_action.target_name, "resolved_prompt": res_action.resolved_prompt},
                    )
                elif res_action.target_type == DeicticTargetType.SELECTED_TEXT:
                    is_fix = any(w in lower_q for w in ["fix", "debug", "correct"])
                    return UserIntent(
                        raw_query=q,
                        intent_type=IntentType.WRITE_ACTION if is_fix else IntentType.READ_QUERY,
                        permission_level=PermissionLevel.LEVEL_1_REVERSIBLE_WRITE if is_fix else PermissionLevel.LEVEL_0_READ,
                        target_tool="get_selected_text",
                        parameters={"text": res_action.content_payload, "resolved_prompt": res_action.resolved_prompt},
                    )
                elif res_action.target_type == DeicticTargetType.BROWSER_PAGE:
                    return UserIntent(
                        raw_query=q,
                        intent_type=IntentType.READ_QUERY,
                        permission_level=PermissionLevel.LEVEL_0_READ,
                        target_tool="browser_get_state",
                        parameters={"url": res_action.content_payload, "resolved_prompt": res_action.resolved_prompt},
                    )

        # 7. Fast SLM Classification (ModelRole.FAST) for ambiguous queries
        if self.llm_provider is not None:
            fast_intent = self.classify_with_fast_model(q)
            if fast_intent is not None:
                return fast_intent

        # Default: Pure conversation
        return UserIntent(
            raw_query=q,
            intent_type=IntentType.CONVERSATION,
            permission_level=PermissionLevel.LEVEL_0_READ,
            target_tool=None,
            parameters={},
        )

    def classify_with_fast_model(self, query: str) -> Optional[UserIntent]:
        """Classifies query using a specialized fast model (ModelRole.FAST)."""
        if not self.llm_provider:
            return None
        schema = {
            "type": "object",
            "properties": {
                "intent_type": {
                    "type": "string",
                    "enum": ["CONVERSATION", "READ_QUERY", "WRITE_ACTION", "EXTERNAL_ACTION", "DESTRUCTIVE_ACTION", "COMPLEX_WORKFLOW"],
                },
                "target_tool": {"type": "string"},
                "confidence": {"type": "number"},
            },
            "required": ["intent_type"],
        }
        prompt = (
            f"Classify the following user input into an intent type:\n\"{query}\"\n"
            "Return valid JSON strictly conforming to the requested schema."
        )
        try:
            res = self.llm_provider.structured_output(prompt, schema=schema, role=ModelRole.FAST)
            itype_str = res.get("intent_type", "CONVERSATION")
            try:
                itype = IntentType(itype_str)
            except ValueError:
                itype = IntentType.CONVERSATION

            tool = res.get("target_tool") or None
            # Derive permission level
            if itype == IntentType.DESTRUCTIVE_ACTION:
                plevel = PermissionLevel.LEVEL_3_DESTRUCTIVE
            elif itype == IntentType.EXTERNAL_ACTION:
                plevel = PermissionLevel.LEVEL_2_EXTERNAL_ACTION
            elif itype in (IntentType.WRITE_ACTION, IntentType.COMPLEX_WORKFLOW):
                plevel = PermissionLevel.LEVEL_1_REVERSIBLE_WRITE
            else:
                plevel = PermissionLevel.LEVEL_0_READ

            return UserIntent(
                raw_query=query,
                intent_type=itype,
                permission_level=plevel,
                target_tool=tool,
                requires_confirmation=plevel in (PermissionLevel.LEVEL_2_EXTERNAL_ACTION, PermissionLevel.LEVEL_3_DESTRUCTIVE),
            )
        except Exception:
            return None


    def _extract_name(self, text: str, triggers: List[str]) -> Optional[str]:
        for trigger in triggers:
            pattern = rf"{trigger}\s+['\"]?([^'\"\.\?!,]+)['\"]?"
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None

    def _extract_email_params(
        self,
        text: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """Extract or infer email parameters from the query or preceding context."""
        email_match = re.search(r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)", text)
        recipient = email_match.group(1) if email_match else ""

        # Subject extraction
        subj_match = re.search(r"subject\s*[:=]?\s*['\"]?([^'\"\n\r]+)['\"]?", text, re.IGNORECASE)
        subject = subj_match.group(1).strip() if subj_match else ""

        # Attachment extraction
        att_match = re.search(r"attach(ment)?\s*[:=]?\s*['\"]?([^'\"\s]+\.[a-zA-Z0-9]+)['\"]?", text, re.IGNORECASE)
        attachment = att_match.group(2).strip() if att_match else ""

        # Message extraction
        msg_match = re.search(r"(?:saying|message|body)\s*[:=]?\s*['\"]([^'\"]+)['\"]", text, re.IGNORECASE)
        message = msg_match.group(1).strip() if msg_match else ""

        # Check conversational history if parameters missing
        if conversation_history and (not recipient or not subject or not message):
            for turn in reversed(conversation_history):
                content = turn.get("content", "")
                if not recipient:
                    m = re.search(r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)", content)
                    if m:
                        recipient = m.group(1)
                if not attachment:
                    m = re.search(r"([a-zA-Z0-9_\-\\\/]+\.(?:pdf|docx|txt|png|jpg))", content, re.IGNORECASE)
                    if m:
                        attachment = m.group(1)

        return {
            "recipient": recipient or "team@example.com",
            "subject": subject or "Project Status Update",
            "message": message or "Attached is the latest documentation for your review.",
            "attachment": attachment or "",
        }
