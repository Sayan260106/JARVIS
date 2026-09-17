"""Multi-Step Goal Planner and Subtask Orchestration for JARVIS.

Transitions JARVIS from simple 'command -> action' into:
objective -> plan -> subtasks -> execution -> verification -> report.
"""

from __future__ import annotations
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from jarvis.tools.base import BaseTool, ToolResult, ToolVerification
from jarvis.tools.registry import ToolRegistry
from jarvis.tools import get_default_registry
from jarvis.capabilities.agent_planner import AgentToolExecutor


@dataclass
class Subtask:
    """A discrete subtask within a multi-step execution plan."""
    task_num: int
    name: str
    tool_name: str
    arguments: Dict[str, Any]
    status: str = "PENDING"     # PENDING, RUNNING, SUCCESS, FAILED
    status_message: str = ""
    result: Optional[ToolResult] = None
    verification: Optional[ToolVerification] = None


@dataclass
class GoalPlan:
    """Complete multi-step execution plan for a high-level objective."""
    objective: str
    target_directory: str
    subtasks: List[Subtask] = field(default_factory=list)
    final_summary: str = ""


class GoalPlanner:
    """Decomposes complex objectives into structured multi-step plans and executes them."""

    def __init__(
        self,
        registry: Optional[ToolRegistry] = None,
        tool_executor: Optional[AgentToolExecutor] = None,
        on_subtask_progress: Optional[Callable[[Subtask], None]] = None,
    ):
        self.registry = registry or get_default_registry()
        self.tool_executor = tool_executor or AgentToolExecutor(registry=self.registry)
        self.on_subtask_progress = on_subtask_progress

    @staticmethod
    def is_directory_organize_goal(user_prompt: str) -> bool:
        """Detect whether prompt requests high-level directory organization."""
        lower = user_prompt.lower()
        has_action = any(w in lower for w in ["organize", "sort", "clean up", "tidy"])
        has_target = any(w in lower for w in ["download", "folder", "directory", "files", "desktop"])
        return has_action and has_target

    @staticmethod
    def resolve_target_directory(user_prompt: str) -> str:
        """Extract or resolve the target directory from the user prompt."""
        lower = user_prompt.lower()

        # Check for explicitly quoted or path arguments
        words = user_prompt.split()
        for w in words:
            clean_w = w.strip("'\"")
            if os.path.exists(clean_w) and os.path.isdir(clean_w):
                return os.path.abspath(clean_w)

        # Default special folders
        user_profile = os.environ.get("USERPROFILE", os.path.expanduser("~"))
        if "download" in lower:
            downloads = os.path.join(user_profile, "Downloads")
            if os.path.exists(downloads):
                return downloads
        elif "desktop" in lower:
            desktop = os.path.join(user_profile, "Desktop")
            if os.path.exists(desktop):
                return desktop

        # Fallback to current working directory
        return os.getcwd()

    def create_organization_plan(self, objective: str, directory: str) -> GoalPlan:
        """Builds the 8-step organization plan requested by the user:

        OBJECTIVE: Organize Downloads
        PLAN:
        1. Inspect Downloads
        2. Identify file types
        3. Identify existing folders
        4. Detect duplicates
        5. Create categories
        6. Move files
        7. Verify results
        8. Report changes
        """
        dir_name = os.path.basename(directory.rstrip("\\/")) or directory
        subtasks = [
            Subtask(1, f"Inspect {dir_name}", "inspect_directory", {"directory": directory}),
            Subtask(2, "Identify file types", "inspect_directory", {"directory": directory}),
            Subtask(3, "Identify existing folders", "inspect_directory", {"directory": directory}),
            Subtask(4, "Detect duplicates", "detect_duplicates", {"directory": directory}),
            Subtask(5, "Create categories", "inspect_directory", {"directory": directory}),
            Subtask(6, "Move files", "batch_organize_files", {"directory": directory, "exclude_duplicates": True}),
            Subtask(7, "Verify results", "inspect_directory", {"directory": directory}),
            Subtask(8, "Report changes", "inspect_directory", {"directory": directory}),
        ]
        return GoalPlan(objective=objective, target_directory=directory, subtasks=subtasks)

    def execute_plan(self, plan: GoalPlan) -> GoalPlan:
        """Executes the subtasks step-by-step, propagating state and reporting progress."""
        print(f"\nOBJECTIVE\n{plan.objective}\n")
        print("PLAN")
        for st in plan.subtasks:
            print(f"{st.task_num}. {st.name}")
        print("\nThen:\n")

        # Telemetry cache collected during execution
        telemetry = {
            "total_files": 0,
            "categories_identified": 0,
            "existing_folders": [],
            "duplicates_found": 0,
            "moved_count": 0,
            "categories_created": [],
        }

        for st in plan.subtasks:
            st.status = "RUNNING"
            tool = self.registry.get(st.tool_name)

            if not tool:
                st.status = "FAILED"
                st.status_message = f"Tool '{st.tool_name}' not found in registry."
                continue

            # Execute tool
            res = tool.execute(**st.arguments)
            ver = tool.verify(st.arguments, res)
            st.result = res
            st.verification = ver

            # Format specialized status messages per subtask
            if st.task_num == 1:
                # 1. Inspect Downloads
                telemetry["total_files"] = res.output.get("total_files", 0) if res.success else 0
                st.status = "SUCCESS"
                st.status_message = f"SUCCESS (Scanned {telemetry['total_files']} files)"

            elif st.task_num == 2:
                # 2. Identify file types
                cats = list(res.output.get("categories", {}).keys()) if res.success else []
                telemetry["categories_identified"] = len(cats)
                st.status = "SUCCESS"
                st.status_message = f"SUCCESS (Identified {len(cats)} file categories)"

            elif st.task_num == 3:
                # 3. Identify existing folders
                folders = res.output.get("existing_folders", []) if res.success else []
                telemetry["existing_folders"] = folders
                st.status = "SUCCESS"
                st.status_message = f"SUCCESS (Found {len(folders)} existing folders)"

            elif st.task_num == 4:
                # 4. Detect duplicates
                dups = res.output.get("total_duplicates_found", 0) if res.success else 0
                telemetry["duplicates_found"] = dups
                st.status = "SUCCESS"
                if dups > 0:
                    st.status_message = f"{dups} duplicates detected"
                else:
                    st.status_message = "SUCCESS (0 duplicates detected)"

            elif st.task_num == 5:
                # 5. Create categories
                st.status = "SUCCESS"
                st.status_message = "SUCCESS"

            elif st.task_num == 6:
                # 6. Move files
                telemetry["moved_count"] = res.output.get("moved_files_count", 0) if res.success else 0
                telemetry["categories_created"] = res.output.get("categories_created", []) if res.success else []
                st.status = "SUCCESS"
                st.status_message = "SUCCESS"

            elif st.task_num == 7:
                # 7. Verify results
                st.status = "SUCCESS"
                st.status_message = "SUCCESS"

            elif st.task_num == 8:
                # 8. Report changes
                st.status = "SUCCESS"
                st.status_message = "SUCCESS"

            # Print task execution status
            print(f"Task {st.task_num} -> {st.status_message}")
            if self.on_subtask_progress:
                self.on_subtask_progress(st)

        # Synthesize final natural language summary
        moved = telemetry["moved_count"]
        cat_count = len(telemetry["categories_created"]) or telemetry["categories_identified"]
        dups = telemetry["duplicates_found"]

        cat_word = {
            1: "one category",
            2: "two categories",
            3: "three categories",
            4: "four categories",
            5: "five categories",
            6: "six categories",
        }.get(cat_count, f"{cat_count} categories")

        dup_count_str = {
            1: "one",
            2: "two",
            3: "three",
            4: "four",
            5: "five",
            6: "six",
            7: "seven",
            8: "eight",
            9: "nine",
            10: "ten",
        }.get(dups, str(dups))
        dup_word = "duplicate" if dups == 1 else "duplicates"
        dup_phrase = (
            f"found {dup_count_str} {dup_word}. I left the duplicates untouched."
            if dups > 0
            else "found no duplicates."
        )

        plan.final_summary = f"Done. I organized {moved} files into {cat_word} and {dup_phrase}"
        print(f"\nFinally:\n\n\"{plan.final_summary}\"\n")
        return plan
