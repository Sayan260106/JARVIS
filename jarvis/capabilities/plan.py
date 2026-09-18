"""2. PLAN Capability — 'What steps are required?'"""

from typing import List, Optional
from jarvis.capabilities.base import PlanCapability
from jarvis.core.schemas import (
    TaskObjective,
    ExecutionPlan,
    PlanStep,
    SubsystemType,
    IntentCategory,
)
from jarvis.core.state import AgentSessionState
from jarvis.tools.registry import ToolRegistry


class DefaultPlanCapability(PlanCapability):
    """Decomposes an objective into ordered PlanSteps with explicit dependencies and tool selection."""

    def __init__(self, registry: Optional[ToolRegistry] = None):
        self.registry = registry

    def plan(self, objective: TaskObjective, state: AgentSessionState) -> ExecutionPlan:
        steps: List[PlanStep] = []

        # 1. Compound editor automation: "Open <App>, type <Text>, save it as <File>"
        entities = objective.extracted_entities or {}
        if "app_name" in entities and "text" in entities and "file_path" in entities:
            app_name = entities["app_name"]
            text_content = entities["text"]
            file_path = entities["file_path"]

            step_open = PlanStep.create(
                description=f"Launch application '{app_name}'",
                subsystem=SubsystemType.SYSTEM,
                tool_name="open_application",
                arguments={"app_name": app_name},
                expected_outcome=f"Application '{app_name}' launched and process running.",
                depends_on=[],
            )
            step_type = PlanStep.create(
                description=f"Type text '{text_content}' into {app_name}",
                subsystem=SubsystemType.SYSTEM,
                tool_name="type_text",
                arguments={"text": text_content},
                expected_outcome=f"Text '{text_content}' successfully entered into {app_name}.",
                depends_on=[step_open.step_id],
            )
            step_save = PlanStep.create(
                description=f"Save document as '{file_path}'",
                subsystem=SubsystemType.SYSTEM,
                tool_name="create_file",
                arguments={"path": file_path, "content": text_content, "overwrite": True},
                expected_outcome=f"File '{file_path}' saved on disk and verified.",
                depends_on=[step_type.step_id],
            )
            steps.extend([step_open, step_type, step_save])
            return ExecutionPlan.create(objective=objective, steps=steps)

        # 2. Intent-based decomposition & tool selection
        if objective.intent == IntentCategory.SYSTEM_COMMAND:
            lower_input = objective.raw_input.lower().strip()
            if lower_input.startswith("open ") and len(lower_input.split()) == 2:
                target_app = lower_input.split()[1]
                steps.append(
                    PlanStep.create(
                        description=f"Open application '{target_app}'",
                        subsystem=SubsystemType.SYSTEM,
                        tool_name="open_application",
                        arguments={"app_name": target_app},
                        expected_outcome=f"Application '{target_app}' launched.",
                    )
                )
            else:
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
            step_search = PlanStep.create(
                description=f"Query search engine for: {objective.raw_input}",
                subsystem=SubsystemType.WEB,
                tool_name="web_search",
                arguments={"query": objective.raw_input},
                expected_outcome="Relevant search results extracted.",
                depends_on=[],
            )
            step_summary = PlanStep.create(
                description="Synthesize research findings",
                subsystem=SubsystemType.LOCAL,
                tool_name="local_summarizer",
                arguments={"style": "concise"},
                expected_outcome="Summary generated without hallucinations.",
                depends_on=[step_search.step_id],
            )
            steps.extend([step_search, step_summary])

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

