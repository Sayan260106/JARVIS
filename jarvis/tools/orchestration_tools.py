"""Orchestration Tools for JARVIS.

Provides BaseTool implementations for executing complex multi-system DAG workflows.
"""

from __future__ import annotations
import time
from typing import Any, Dict, Optional

from jarvis.tools.base import BaseTool, RiskLevel, ToolParameter, ToolResult, ToolVerification
from jarvis.orchestrator.engine import ComplexTaskEngine
from jarvis.orchestrator.workflows import PresentationPrepWorkflow


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

    def execute(
        self,
        workflow: str = "presentation_prep",
        project_name: str = "ORCA-X",
        project_path: Optional[str] = None,
        **kwargs,
    ) -> ToolResult:
        start_t = time.perf_counter()
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
