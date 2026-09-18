"""Orchestration Tools for JARVIS.

Provides BaseTool implementations for executing complex multi-system DAG workflows
and end-to-end unified computer-use plans across Windows, Browser, Documents, Vision, and LLM.
"""

from __future__ import annotations
import time
from typing import Any, Dict, Optional

from jarvis.tools.base import BaseTool, RiskLevel, ToolParameter, ToolResult, ToolVerification
from jarvis.orchestrator.engine import ComplexTaskEngine
from jarvis.orchestrator.workflows import PresentationPrepWorkflow
from jarvis.orchestrator.unified_planner import UnifiedComputerUsePlanner


class RunComplexTaskTool(BaseTool):
    """Executes a multi-system complex workflow using the DAG orchestrator."""
    name = "run_complex_task"
    description = "Executes complex multi-system tasks using the DAG orchestrator with strict dependency tracking and sub-stages."
    risk_level = RiskLevel.MEDIUM
    parameters = {
        "workflow": ToolParameter("workflow", "string", "Workflow type (e.g. 'presentation_prep').", required=True),
        "project_name": ToolParameter("project_name", "string", "Target project name (e.g. 'ORCA-X').", required=False, default="ORCA-X"),
        "project_path": ToolParameter("project_path", "string", "Optional local directory path for the project.", required=False),
    }

    def __init__(self, engine: Optional[ComplexTaskEngine] = None):
        self.engine = engine or ComplexTaskEngine()

    def execute(self, *args, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        params = args[0] if args and isinstance(args[0], dict) else kwargs
        workflow = params.get("workflow", "presentation_prep")
        project_name = params.get("project_name", "ORCA-X")
        project_path = params.get("project_path")

        try:
            if workflow.lower() in ["presentation_prep", "prepare_presentation", "presentation"]:
                dag = PresentationPrepWorkflow.build_dag(project_name=project_name, project_path=project_path)
            else:
                dag = PresentationPrepWorkflow.build_dag(project_name=project_name, project_path=project_path)

            report = self.engine.execute_dag(dag, objective=f"Prepare {project_name} for presentation", print_tree=True)
            return ToolResult(
                success=(report.overall_status in ["READY", "ACTION_REQUIRED"]),
                output={
                    "workflow": report.workflow_name,
                    "overall_status": report.overall_status,
                    "completed_nodes": report.completed_nodes,
                    "total_nodes": report.total_nodes,
                    "issues_count": len(report.issues),
                    "summary": report.summary_text,
                },
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=str(e),
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        verified = result.success and result.output is not None and result.output.get("completed_nodes", 0) > 0
        return ToolVerification(
            verified=verified,
            details=f"Workflow completed {result.output.get('completed_nodes', 0)}/{result.output.get('total_nodes', 0)} nodes." if verified else "Workflow failed",
        )


class UnifiedComputerUseTool(BaseTool):
    """Executes end-to-end 13-stage computer-use workflow combining Browser, Filesystem, Documents, LLM, and Windows."""
    name = "unified_computer_use"
    description = "Executes autonomous computer-use plan combining Browser, Filesystem, Document Intelligence, LLM Solving, and Windows Desktop Control."
    risk_level = RiskLevel.MEDIUM
    parameters = {
        "prompt": ToolParameter("prompt", "string", "User task objective description.", required=False, default="Find DBMS assignment in Classroom, solve it, save in college folder, and open in VS Code."),
        "course": ToolParameter("course", "string", "Course or subject name (e.g. 'DBMS').", required=False, default="DBMS"),
        "destination_folder": ToolParameter("destination_folder", "string", "Target folder to store assignment and solution.", required=False),
        "editor": ToolParameter("editor", "string", "Editor application to open solution in (default: 'VS Code').", required=False, default="VS Code"),
        "simulated": ToolParameter("simulated", "boolean", "Run in simulated mode for headless/test environments.", required=False, default=False),
    }

    def __init__(self, planner: Optional[UnifiedComputerUsePlanner] = None):
        self._planner = planner

    @property
    def planner(self) -> UnifiedComputerUsePlanner:
        if self._planner is None:
            self._planner = UnifiedComputerUsePlanner()
        return self._planner

    def execute(self, *args, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        params = args[0] if args and isinstance(args[0], dict) else kwargs
        prompt = params.get("prompt", "Find DBMS assignment in Classroom, solve it, save in college folder, and open in VS Code.")
        course = params.get("course", "DBMS")
        destination_folder = params.get("destination_folder")
        editor = params.get("editor", "VS Code")
        simulated = params.get("simulated", False)

        try:
            plan = self.planner.create_assignment_workflow_plan(
                objective=prompt,
                course=course,
                destination_folder=destination_folder,
                editor=editor,
                simulated=simulated,
            )
            report = self.planner.execute_plan(plan, simulated=simulated)
            return ToolResult(
                success=report.success,
                output=report.to_dict(),
                error=None if report.success else "Failed to complete all unified steps.",
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=str(e),
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        verified = result.success and result.output is not None and result.output.get("completed_steps", 0) == 13
        return ToolVerification(
            verified=verified,
            details=f"Unified computer-use plan executed {result.output.get('completed_steps', 0)}/13 steps successfully." if verified else "Plan failed.",
        )
