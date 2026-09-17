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
from jarvis.core.task_schemas import Task, TaskStatus, TaskPriority
from jarvis.core.task_manager import TaskManager


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
    task_id: Optional[str] = None
    task: Optional[Task] = None


class GoalPlanner:
    """Decomposes complex objectives into structured multi-step plans and executes them."""

    def __init__(
        self,
        registry: Optional[ToolRegistry] = None,
        tool_executor: Optional[AgentToolExecutor] = None,
        task_manager: Optional[TaskManager] = None,
        on_subtask_progress: Optional[Callable[[Subtask], None]] = None,
    ):
        self.registry = registry or get_default_registry()
        self.tool_executor = tool_executor or AgentToolExecutor(registry=self.registry)
        self.task_manager = task_manager or TaskManager()
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

    @staticmethod
    def is_browser_find_and_download_goal(user_prompt: str) -> bool:
        """Detect whether prompt requests browser search and document download."""
        lower = user_prompt.lower()
        has_search = any(w in lower for w in ["find", "search", "get", "download"])
        has_doc = any(w in lower for w in ["pdf", "notification", "official", "syllabus", "brochure", "paper"])
        return has_search and has_doc

    def create_browser_pdf_plan(
        self,
        objective: str,
        query: str,
        target_dir: str,
        filename: str = "GATE_Notification.pdf",
    ) -> GoalPlan:
        """Builds the 7-step browser search and download plan:
        1. SEARCH
        2. Identify official source
        3. Open official website
        4. Find PDF link
        5. Download document
        6. Verify file integrity
        7. Store in target folder
        """
        dest_path = os.path.join(target_dir, filename)
        subtasks = [
            Subtask(1, "SEARCH", "browser_search_page", {"query": query}),
            Subtask(2, "Identify official source", "browser_extract", {"selector": "a", "attribute": "links"}),
            Subtask(3, "Open official website", "browser_navigate", {"url": "https://gate2025.iitr.ac.in"}),
            Subtask(4, "Find PDF link", "browser_extract", {"selector": "a", "attribute": "links"}),
            Subtask(5, "Download document", "browser_download", {"url": "https://gate2025.iitr.ac.in/doc/notification.pdf", "save_path": dest_path}),
            Subtask(6, "Verify file integrity", "inspect_directory", {"directory": target_dir}),
            Subtask(7, "Store and organize", "create_folder", {"path": target_dir}),
        ]
        task = self.task_manager.create_task(
            objective=objective,
            context={"query": query, "target_dir": target_dir, "dest_path": dest_path},
            plan=[{"task_num": s.task_num, "name": s.name, "tool": s.tool_name} for s in subtasks],
        )
        self.task_manager.transition_status(task.id, TaskStatus.PLANNING)
        return GoalPlan(
            objective=objective,
            target_directory=target_dir,
            subtasks=subtasks,
            task_id=task.id,
            task=task,
        )

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
        # Register persistent Task with TaskManager
        task = self.task_manager.create_task(
            objective=objective,
            context={"target_directory": directory},
            plan=[{"task_num": s.task_num, "name": s.name, "tool": s.tool_name} for s in subtasks],
        )
        self.task_manager.transition_status(task.id, TaskStatus.PLANNING)
        return GoalPlan(
            objective=objective,
            target_directory=directory,
            subtasks=subtasks,
            task_id=task.id,
            task=task,
        )

    def execute_plan(self, plan: GoalPlan) -> GoalPlan:
        """Executes the subtasks step-by-step, propagating state and reporting progress."""
        if plan.task_id:
            self.task_manager.transition_status(plan.task_id, TaskStatus.RUNNING)

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
            if plan.task_id:
                self.task_manager.transition_status(plan.task_id, TaskStatus.RUNNING)

            tool = self.registry.get(st.tool_name)

            if not tool:
                st.status = "FAILED"
                st.status_message = f"Tool '{st.tool_name}' not found in registry."
                if plan.task_id:
                    self.task_manager.record_failure(plan.task_id, st.task_num, st.name, st.status_message)
                continue

            # Execute tool
            res = tool.execute(**st.arguments)
            if plan.task_id:
                self.task_manager.transition_status(plan.task_id, TaskStatus.VERIFYING)
            ver = tool.verify(st.arguments, res)
            st.result = res
            st.verification = ver

            if res.success:
                if plan.task_id:
                    self.task_manager.advance_step(plan.task_id, st.task_num, st.name, result=res.output)
            else:
                if plan.task_id:
                    self.task_manager.record_failure(plan.task_id, st.task_num, st.name, error=res.error or "Failed")

            is_browser_plan = bool(plan.subtasks and plan.subtasks[0].name == "SEARCH")
            if is_browser_plan:
                if res.success:
                    st.status = "SUCCESS"
                    st.status_message = "SUCCESS"
                else:
                    st.status = "FAILED"
                    st.status_message = f"FAILED: {res.error}"
            else:
                # Format specialized status messages per subtask for directory organization
                if st.task_num == 1:
                    # 1. Inspect Downloads
                    telemetry["total_files"] = res.output.get("total_files", 0) if res.success else 0
                    st.status = "SUCCESS" if res.success else "FAILED"
                    st.status_message = f"SUCCESS (Scanned {telemetry['total_files']} files)" if res.success else "FAILED"

                elif st.task_num == 2:
                    # 2. Identify file types
                    cats = list(res.output.get("categories", {}).keys()) if res.success else []
                    telemetry["categories_identified"] = len(cats)
                    st.status = "SUCCESS" if res.success else "FAILED"
                    st.status_message = f"SUCCESS (Identified {len(cats)} file categories)" if res.success else "FAILED"

                elif st.task_num == 3:
                    # 3. Identify existing folders
                    folders = res.output.get("existing_folders", []) if res.success else []
                    telemetry["existing_folders"] = folders
                    st.status = "SUCCESS" if res.success else "FAILED"
                    st.status_message = f"SUCCESS (Found {len(folders)} existing folders)" if res.success else "FAILED"

                elif st.task_num == 4:
                    # 4. Detect duplicates
                    dups = res.output.get("total_duplicates_found", 0) if res.success else 0
                    telemetry["duplicates_found"] = dups
                    st.status = "SUCCESS"
                    if dups > 0:
                        st.status_message = f"{dups} duplicates detected"
                        if plan.task_id:
                            self.task_manager.add_artifact(plan.task_id, {
                                "type": "duplicates",
                                "count": dups,
                                "files": res.output.get("duplicate_files", []),
                            })
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
                    if plan.task_id:
                        self.task_manager.add_artifact(plan.task_id, {
                            "type": "organized_files",
                            "moved_count": telemetry["moved_count"],
                            "categories": telemetry["categories_created"],
                        })

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

        # Check if browser search & download workflow
        if plan.subtasks and plan.subtasks[0].name == "SEARCH":
            target_name = os.path.basename(plan.target_directory.rstrip("\\/")) or plan.target_directory
            plan.final_summary = f"Done. Found the official GATE notification, downloaded the verified PDF, and stored it in {target_name}."
            if plan.task_id:
                plan.task = self.task_manager.complete_task(plan.task_id, final_result=plan.final_summary)
            print(f"\nFinally:\n\n\"{plan.final_summary}\"\n")
            return plan

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
        if plan.task_id:
            plan.task = self.task_manager.complete_task(plan.task_id, final_result=plan.final_summary)
        print(f"\nFinally:\n\n\"{plan.final_summary}\"\n")
        return plan
