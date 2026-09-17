"""2. PLAN Capability — 'What steps are required?'"""

from jarvis.capabilities.base import PlanCapability
from jarvis.core.schemas import (
    TaskObjective,
    ExecutionPlan,
    PlanStep,
    SubsystemType,
    IntentCategory,
)
from jarvis.core.state import AgentSessionState


class DefaultPlanCapability(PlanCapability):
    """Decomposes an objective into ordered PlanSteps assigned to subsystems."""

    def plan(self, objective: TaskObjective, state: AgentSessionState) -> ExecutionPlan:
        steps = []

        if objective.intent == IntentCategory.SYSTEM_COMMAND:
            steps.append(
                PlanStep.create(
                    description=f"Execute system command for: {objective.raw_input}",
                    subsystem=SubsystemType.SYSTEM,
                    tool_name="powershell_exec",
                    arguments={"command": objective.raw_input},
                    expected_outcome="Exit code 0 with expected stdout.",
                )
            )
        elif objective.intent == IntentCategory.RESEARCH:
            steps.append(
                PlanStep.create(
                    description=f"Query search engine for: {objective.raw_input}",
                    subsystem=SubsystemType.WEB,
                    tool_name="web_search",
                    arguments={"query": objective.raw_input},
                    expected_outcome="Relevant search results extracted.",
                )
            )
            steps.append(
                PlanStep.create(
                    description="Synthesize research findings",
                    subsystem=SubsystemType.LOCAL,
                    tool_name="local_summarizer",
                    arguments={"style": "concise"},
                    expected_outcome="Summary generated without hallucinations.",
                )
            )
        elif objective.intent == IntentCategory.QUERY:
            steps.append(
                PlanStep.create(
                    description=f"Process informational query: {objective.raw_input}",
                    subsystem=SubsystemType.LOCAL,
                    tool_name="local_reasoning",
                    arguments={"prompt": objective.raw_input},
                    expected_outcome="Direct, accurate answer formulated.",
                )
            )
        else:
            # General fallback decomposition
            steps.append(
                PlanStep.create(
                    description=f"Execute task: {objective.raw_input}",
                    subsystem=SubsystemType.SYSTEM,
                    tool_name="task_runner",
                    arguments={"task": objective.raw_input},
                    expected_outcome="Task completion status verified.",
                )
            )

        return ExecutionPlan.create(objective=objective, steps=steps)
