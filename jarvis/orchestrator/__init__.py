"""Complex Task Engine & DAG Orchestrator Package for JARVIS.

Coordinates multi-system workflows with explicit dependency graphs,
autonomous observe-verify-recover sub-stages, and executive severity reporting.
"""

from jarvis.orchestrator.schemas import (
    NodeStatus,
    ErrorSeverity,
    SubStageRecord,
    TaskNode,
    CollectedIssue,
    ExecutionReport,
)
from jarvis.orchestrator.dag import TaskDAG
from jarvis.orchestrator.engine import ComplexTaskEngine
from jarvis.orchestrator.workflows import PresentationPrepWorkflow

__all__ = [
    "NodeStatus",
    "ErrorSeverity",
    "SubStageRecord",
    "TaskNode",
    "CollectedIssue",
    "ExecutionReport",
    "TaskDAG",
    "ComplexTaskEngine",
    "PresentationPrepWorkflow",
]
