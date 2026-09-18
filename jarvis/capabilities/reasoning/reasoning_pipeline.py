"""Reasoning Pipeline for JARVIS.

Coordinates the decoupled internal architecture:
USER -> Intent Analyzer -> Task Planner -> Web Agent / Tool Agent -> Observer -> Verifier -> Pass/Recovery -> Replan
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from jarvis.tools.base import ToolResult, ToolVerification, PermissionLevel
from jarvis.tools.permissions import PermissionSystem, PermissionDecision
from jarvis.tools.registry import ToolRegistry
from jarvis.capabilities.reasoning.intent_analyzer import (
    IntentAnalyzer,
    UserIntent,
    IntentType,
)


@dataclass
class ReasoningStep:
    """Record of a discrete stage in the reasoning pipeline."""
    phase: str          # INTENT_ANALYSIS, TASK_PLANNING, AGENT_DISPATCH, OBSERVATION, VERIFICATION, RECOVERY, SYNTHESIS
    status: str         # SUCCESS, FAILED, PENDING_CONFIRMATION, BLOCKED_BY_POLICY, SKIPPED
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReasoningResult:
    """The final outcome of the modular reasoning loop."""
    intent: UserIntent
    steps: List[ReasoningStep]
    output: str
    success: bool
    requires_user_action: bool = False
    confirmation_preview: Optional[Dict[str, Any]] = None
    recovery_attempts: int = 0


class ReasoningPipeline:
    """Decoupled cognitive pipeline replacing monolithic single-prompt thinking."""

    def __init__(
        self,
        intent_analyzer: Optional[IntentAnalyzer] = None,
        permission_system: Optional[PermissionSystem] = None,
        registry: Optional[ToolRegistry] = None,
        tool_executor: Optional[Any] = None,
        max_recovery_attempts: int = 3,
    ):
        self.intent_analyzer = intent_analyzer or IntentAnalyzer()
        self.permissions = permission_system or PermissionSystem()
        self.registry = registry
        self.tool_executor = tool_executor
        self.max_recovery_attempts = max_recovery_attempts

    def execute(
        self,
        query: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        confirmed: bool = False,
    ) -> ReasoningResult:
        """Executes the full reasoning loop across all specialized components."""
        steps: List[ReasoningStep] = []

        # 1. INTENT ANALYZER
        intent = self.intent_analyzer.analyze(query, conversation_history)
        steps.append(
            ReasoningStep(
                phase="INTENT_ANALYSIS",
                status="SUCCESS",
                details={
                    "intent_type": intent.intent_type.value,
                    "permission_level": intent.permission_level.value,
                    "target_tool": intent.target_tool,
                    "requires_confirmation": intent.requires_confirmation,
                },
            )
        )

        # 2. SAFETY GATEKEEPER & POLICY INTERCEPT
        # Level 3 Destructive: Halt immediately with impact warning unless already confirmed
        if intent.intent_type == IntentType.DESTRUCTIVE_ACTION and not confirmed:
            steps.append(
                ReasoningStep(
                    phase="SAFETY_GATE",
                    status="PENDING_CONFIRMATION",
                    details={"reason": "Level 3 Destructive Action requires explicit user authorization"},
                )
            )
            warning_msg = intent.warning_prompt or (
                f"Action '{intent.target_tool}' is destructive and irreversible. Do you want to proceed?"
            )
            return ReasoningResult(
                intent=intent,
                steps=steps,
                output=warning_msg,
                success=False,
                requires_user_action=True,
                confirmation_preview=None,
            )

        # Level 2 External Action: Show parameter preview and ask for confirmation unless confirmed
        if intent.intent_type == IntentType.EXTERNAL_ACTION and not confirmed:
            steps.append(
                ReasoningStep(
                    phase="SAFETY_GATE",
                    status="PENDING_CONFIRMATION",
                    details={
                        "reason": "Level 2 External Action requires confirmation with parameter preview",
                        "preview": intent.confirmation_preview,
                    },
                )
            )
            preview = intent.confirmation_preview or {}
            preview_text = (
                "External Action Confirmation Required:\n"
                f"  Recipient : {preview.get('Recipient', 'None')}\n"
                f"  Subject   : {preview.get('Subject', 'None')}\n"
                f"  Message   : {preview.get('Message', 'None')}\n"
                f"  Attachment: {preview.get('Attachment', 'None')}\n\n"
                "Would you like me to send this email?"
            )
            return ReasoningResult(
                intent=intent,
                steps=steps,
                output=preview_text,
                success=False,
                requires_user_action=True,
                confirmation_preview=intent.confirmation_preview,
            )

        # 3. TASK PLANNER
        plan_steps = self._plan_tasks(intent)
        steps.append(
            ReasoningStep(
                phase="TASK_PLANNING",
                status="SUCCESS",
                details={"planned_tasks": plan_steps},
            )
        )

        # 4. DISPATCH (Web Agent vs Tool Agent)
        dispatch_target = "Web Agent (Research)" if intent.requires_research else "Tool Agent (Action)"
        steps.append(
            ReasoningStep(
                phase="AGENT_DISPATCH",
                status="SUCCESS",
                details={"target": dispatch_target, "tool": intent.target_tool},
            )
        )

        # Execute using Tool Agent or Goal Planner
        exec_result, verification, recovery_count = self._dispatch_and_execute(intent, confirmed=confirmed)

        # 5. OBSERVER
        steps.append(
            ReasoningStep(
                phase="OBSERVATION",
                status="SUCCESS" if (exec_result and exec_result.success) else "FAILED",
                details={
                    "output": exec_result.output if exec_result else None,
                    "error": exec_result.error if exec_result else None,
                },
            )
        )

        # 6. VERIFIER
        verified = verification.verified if verification else (exec_result and exec_result.success)
        steps.append(
            ReasoningStep(
                phase="VERIFICATION",
                status="SUCCESS" if verified else "FAILED",
                details={
                    "verified": verified,
                    "details": verification.details if verification else "Execution verified.",
                },
            )
        )

        # 7. SYNTHESIS
        final_output = self._synthesize_output(intent, exec_result, verification)
        steps.append(
            ReasoningStep(
                phase="SYNTHESIS",
                status="SUCCESS",
                details={"output_length": len(final_output)},
            )
        )

        return ReasoningResult(
            intent=intent,
            steps=steps,
            output=final_output,
            success=verified,
            requires_user_action=False,
            recovery_attempts=recovery_count,
        )

    def _plan_tasks(self, intent: UserIntent) -> List[str]:
        """Task Planner determines decomposed subtask sequence."""
        if intent.intent_type == IntentType.DESTRUCTIVE_ACTION:
            return ["Scan target projects", "Assess blast radius", "Execute authorized deletion", "Verify removal"]
        elif intent.intent_type == IntentType.EXTERNAL_ACTION:
            return ["Format payload", "Verify parameters", "Transmit via external provider", "Verify transmission log"]
        elif intent.intent_type == IntentType.COMPLEX_WORKFLOW:
            return ["Inspect environment", "Resolve dependencies", "Execute subtasks", "Verify overall goal"]
        elif intent.intent_type == IntentType.READ_QUERY:
            return [f"Query information via {intent.target_tool or 'system query'}", "Verify retrieved data"]
        elif intent.intent_type == IntentType.WRITE_ACTION:
            return [f"Execute write operation via {intent.target_tool}", "Verify file/state change"]
        return ["Process query", "Formulate conversational response"]

    def _dispatch_and_execute(
        self, intent: UserIntent, confirmed: bool = False
    ) -> tuple[Optional[ToolResult], Optional[ToolVerification], int]:
        """Dispatches to the target tool agent with observer and recovery loops."""
        if not intent.target_tool or not self.registry:
            # Pure conversation or non-tool intent
            res = ToolResult(success=True, output="Conversational response synthesized.")
            ver = ToolVerification(verified=True, details="No tool execution required.")
            return res, ver, 0

        tool = self.registry.get(intent.target_tool)
        if not tool:
            res = ToolResult(success=False, output=None, error=f"Tool '{intent.target_tool}' not found.")
            ver = ToolVerification(verified=False, details="Tool missing from registry.")
            return res, ver, 0

        args = dict(intent.parameters)
        if confirmed:
            args["confirmed"] = True

        recovery_count = 0
        exec_res: Optional[ToolResult] = None
        ver_res: Optional[ToolVerification] = None

        while recovery_count <= self.max_recovery_attempts:
            exec_res = tool.execute(**args)
            ver_res = tool.verify(args, exec_res)

            if exec_res.success and ver_res.verified:
                break

            # If failed, attempt safe recovery / retry up to max_recovery_attempts
            recovery_count += 1
            if recovery_count > self.max_recovery_attempts:
                break

        return exec_res, ver_res, recovery_count

    def _synthesize_output(
        self,
        intent: UserIntent,
        result: Optional[ToolResult],
        verification: Optional[ToolVerification],
    ) -> str:
        """Synthesizes final response text to the user."""
        if not result:
            return "Task completed."
        if not result.success:
            return f"Action failed: {result.error}"
        if isinstance(result.output, str):
            return result.output
        return str(result.output)
