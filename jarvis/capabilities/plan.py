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

        # 2. Typed Windows Control Action decomposition
        if "action" in entities:
            action = entities["action"]
            if action == "open_application":
                app_name = entities.get("app_name", "")
                steps.append(
                    PlanStep.create(
                        description=f"Launch application '{app_name}'",
                        subsystem=SubsystemType.SYSTEM,
                        tool_name="open_application",
                        arguments={"app_name": app_name},
                        expected_outcome=f"Application '{app_name}' launched and process running.",
                    )
                )
            elif action == "close_application":
                app_name = entities.get("app_name", "")
                steps.append(
                    PlanStep.create(
                        description=f"Close application '{app_name}'",
                        subsystem=SubsystemType.SYSTEM,
                        tool_name="close_application",
                        arguments={"app_name": app_name},
                        expected_outcome=f"Application '{app_name}' closed.",
                    )
                )
            elif action == "create_folder":
                folder_path = entities.get("path", "")
                steps.append(
                    PlanStep.create(
                        description=f"Create folder '{folder_path}'",
                        subsystem=SubsystemType.SYSTEM,
                        tool_name="create_folder",
                        arguments={"path": folder_path},
                        expected_outcome=f"Folder '{folder_path}' created on filesystem.",
                    )
                )
            elif action == "shutdown":
                delay = entities.get("delay_seconds", 60)
                steps.append(
                    PlanStep.create(
                        description=f"Schedule computer shutdown ({delay}s delay)",
                        subsystem=SubsystemType.SYSTEM,
                        tool_name="shutdown",
                        arguments={"delay_seconds": delay},
                        expected_outcome="Computer shutdown scheduled.",
                    )
                )
            elif action == "restart":
                delay = entities.get("delay_seconds", 60)
                steps.append(
                    PlanStep.create(
                        description=f"Schedule computer restart ({delay}s delay)",
                        subsystem=SubsystemType.SYSTEM,
                        tool_name="restart",
                        arguments={"delay_seconds": delay},
                        expected_outcome="Computer restart scheduled.",
                    )
                )
            elif action == "lock_pc":
                steps.append(
                    PlanStep.create(
                        description="Lock workstation",
                        subsystem=SubsystemType.SYSTEM,
                        tool_name="lock_pc",
                        arguments={},
                        expected_outcome="Workstation locked.",
                    )
                )
            elif action == "sleep_pc":
                steps.append(
                    PlanStep.create(
                        description="Put computer to sleep",
                        subsystem=SubsystemType.SYSTEM,
                        tool_name="sleep_pc",
                        arguments={},
                        expected_outcome="Computer in sleep mode.",
                    )
                )
            elif action == "volume_control":
                v_act = entities.get("vol_action", "set")
                v_args = {"action": v_act}
                if "level" in entities:
                    v_args["level"] = entities["level"]
                steps.append(
                    PlanStep.create(
                        description=f"Adjust volume ({v_act})",
                        subsystem=SubsystemType.SYSTEM,
                        tool_name="volume_control",
                        arguments=v_args,
                        expected_outcome="System volume adjusted.",
                    )
                )
            elif action == "focus_window":
                title = entities.get("title", "")
                steps.append(
                    PlanStep.create(
                        description=f"Focus window '{title}'",
                        subsystem=SubsystemType.SYSTEM,
                        tool_name="focus_window",
                        arguments={"title": title},
                        expected_outcome=f"Window '{title}' focused.",
                    )
                )
            elif action == "window_control":
                w_act = entities.get("action", "minimize")
                title = entities.get("title", "")
                steps.append(
                    PlanStep.create(
                        description=f"{w_act.capitalize()} window '{title}'",
                        subsystem=SubsystemType.SYSTEM,
                        tool_name="window_control",
                        arguments={"action": w_act, "title": title},
                        expected_outcome=f"Window '{title}' {w_act}d.",
                    )
                )
            if steps:
                return ExecutionPlan.create(objective=objective, steps=steps)

        # 3. Intent-based decomposition & tool selection
        if objective.intent == IntentCategory.SYSTEM_COMMAND:
            lower_input = objective.raw_input.lower().strip().rstrip(".")
            if lower_input.startswith("open "):
                target_app = objective.raw_input.strip()[5:].rstrip(".").strip()
                steps.append(
                    PlanStep.create(
                        description=f"Open application '{target_app}'",
                        subsystem=SubsystemType.SYSTEM,
                        tool_name="open_application",
                        arguments={"app_name": target_app},
                        expected_outcome=f"Application '{target_app}' launched.",
                    )
                )
            elif lower_input.startswith("close "):
                target_app = objective.raw_input.strip()[6:].rstrip(".").strip()
                steps.append(
                    PlanStep.create(
                        description=f"Close application '{target_app}'",
                        subsystem=SubsystemType.SYSTEM,
                        tool_name="close_application",
                        arguments={"app_name": target_app},
                        expected_outcome=f"Application '{target_app}' closed.",
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

