"""Tool Fallback Engine for Autonomous Recovery 2.0 (Phase 14).

Maps failed tool operations to alternative tool routes and execution strategies.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple

from jarvis.core.schemas import PlanStep, SubsystemType


class ToolFallbackEngine:
    """Provides alternative tool bindings and argument adaptations."""

    TOOL_FALLBACK_MAP: Dict[str, List[Dict[str, Any]]] = {
        "focus_window": [
            {
                "tool_name": "open_application",
                "subsystem": SubsystemType.SYSTEM,
                "arg_adapter": lambda args: {"app_name": args.get("title") or args.get("window_title") or "app"},
                "explanation": "Switching from focus_window to open_application to ensure target process is launched.",
            }
        ],
        "browser_click": [
            {
                "tool_name": "browser_search_page",
                "subsystem": SubsystemType.WEB,
                "arg_adapter": lambda args: {"query": args.get("selector") or args.get("text") or "query"},
                "explanation": "Switching from direct DOM click to in-page search to locate renamed or hidden element.",
            },
            {
                "tool_name": "click_screen_element",
                "subsystem": SubsystemType.VISION,
                "arg_adapter": lambda args: {"target_label": args.get("selector") or args.get("text") or "button"},
                "explanation": "Switching from DOM selector click to vision-based screen element grounding.",
            },
        ],
        "modify_file": [
            {
                "tool_name": "create_file",
                "subsystem": SubsystemType.SYSTEM,
                "arg_adapter": lambda args: {"path": args.get("path") or args.get("file_path"), "content": args.get("replacement") or ""},
                "explanation": "Switching from modify_file to create_file as target file is missing.",
            }
        ],
        "get_active_document": [
            {
                "tool_name": "get_selected_text",
                "subsystem": SubsystemType.LOCAL,
                "arg_adapter": lambda args: {},
                "explanation": "Switching from editor context to highlighted selection buffer.",
            }
        ],
    }

    def get_fallback_step(self, step: PlanStep, failure_reason: str = "") -> Optional[PlanStep]:
        """Derives an alternative PlanStep with fallback tool binding."""
        fallbacks = self.TOOL_FALLBACK_MAP.get(step.tool_name, [])
        if not fallbacks:
            return None

        fb_config = fallbacks[0]
        new_tool = fb_config["tool_name"]
        new_subsystem = fb_config["subsystem"]
        adapter = fb_config["arg_adapter"]
        new_args = adapter(step.arguments)

        return PlanStep.create(
            description=f"{step.description} (via fallback {new_tool})",
            subsystem=new_subsystem,
            tool_name=new_tool,
            arguments=new_args,
            expected_outcome=step.expected_outcome,
            depends_on=step.depends_on,
        )
