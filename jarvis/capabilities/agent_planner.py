"""Agent Tool Executor for JARVIS.

Enforces the secure tool pipeline:
Ollama -> Tool Request -> Tool Validator -> Permission System -> Tool Execution -> Verification -> Result -> Ollama
"""

from __future__ import annotations
import json
import re
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from jarvis.tools.base import BaseTool, ToolResult, ToolVerification
from jarvis.tools.validator import ToolValidator
from jarvis.tools.permissions import PermissionSystem, PermissionDecision
from jarvis.tools.registry import ToolRegistry
from jarvis.tools import get_default_registry
from jarvis.subsystems.local.ollama_client import OllamaClient
from jarvis.capabilities.reasoning.intent_analyzer import IntentAnalyzer, IntentType
from jarvis.capabilities.reasoning.reasoning_pipeline import ReasoningPipeline


@dataclass
class AgentTurnResult:
    """Result of an autonomous agent turn."""
    tool_called: bool
    tool_name: Optional[str] = None
    arguments: Optional[Dict[str, Any]] = None
    tool_result: Optional[ToolResult] = None
    verification: Optional[ToolVerification] = None
    permission_decision: Optional[PermissionDecision] = None
    final_response: str = ""


class AgentToolExecutor:
    """Orchestrates Ollama with the secure local tool pipeline."""

    def __init__(
        self,
        ollama_client: Optional[OllamaClient] = None,
        registry: Optional[ToolRegistry] = None,
        permission_system: Optional[PermissionSystem] = None,
    ):
        self.ollama = ollama_client or OllamaClient()
        self.registry = registry or get_default_registry()
        self.permissions = permission_system or PermissionSystem()
        self.intent_analyzer = IntentAnalyzer()
        self.reasoning_pipeline = ReasoningPipeline(
            intent_analyzer=self.intent_analyzer,
            permission_system=self.permissions,
            registry=self.registry,
            tool_executor=self,
        )

    def build_system_prompt(self) -> str:
        """Construct the tool-augmented system prompt for Ollama."""
        tool_desc = self.registry.get_prompt_description()
        return (
            "You are JARVIS, an advanced autonomous AI assistant capable of controlling the local Windows laptop.\n"
            "When the user requests an action or asks about applications, files, hardware metrics, or system states, analyze which tool to use.\n"
            "If a tool is needed, respond ONLY with a JSON object in this exact format:\n"
            '{"tool": "<tool_name>", "arguments": {<key>: <value>}}\n\n'
            "Contextual Rules:\n"
            "- When the user refers to items from earlier in the conversation (e.g. 'this PDF', 'that folder', 'the file we found'), inspect previous turns and use those exact paths.\n"
            "- For applications like Edge, VS Code, Spotify, use 'open_application' with the app name.\n"
            "- For queries like 'How much RAM am I using?' or 'What is my CPU usage?', use 'get_hardware_metrics'.\n"
            "- For queries like 'Is Ollama running?', use 'check_process' with process_name='ollama'.\n"
            "- If no tool is needed (e.g. pure conversation or conceptual explanations), respond with standard text.\n\n"
            f"{tool_desc}"
        )

    def extract_tool_call(self, text: str) -> Optional[Tuple[str, Dict[str, Any]]]:
        """Extracts tool name and arguments from Ollama response only if tool exists in registry."""
        cleaned = text.strip()

        # Match ```json ... ``` blocks if present
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
        candidate = json_match.group(1) if json_match else cleaned

        tool_name = None
        args = {}

        # Attempt JSON parse
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                # Format: {"tool": "...", "arguments": {...}}
                if "tool" in data:
                    tool_name = data["tool"]
                    args = data.get("arguments", {})
                    if not isinstance(args, dict):
                        args = {}
                # Alternative format: {"name": "...", "parameters": {...}}
                elif "name" in data and "parameters" in data:
                    tool_name = data["name"]
                    args = data.get("parameters", {})
        except json.JSONDecodeError:
            # Try regex search for embedded {"tool": ...}
            embedded = re.search(r'\{[^{}]*"tool"\s*:\s*"([^"]+)"[^{}]*\}', cleaned, re.DOTALL)
            if embedded:
                try:
                    data = json.loads(embedded.group(0))
                    tool_name = data.get("tool")
                    args = data.get("arguments", {})
                except Exception:
                    pass

        if tool_name:
            clean_name = str(tool_name).strip().lower()
            # Verify tool is actually in the registry
            if self.registry.get(clean_name):
                return clean_name, args

        return None

    def execute_tool(
        self, tool_name: str, arguments: Dict[str, Any]
    ) -> Tuple[Optional[ToolResult], Optional[ToolVerification], PermissionDecision]:
        """Executes the complete validation, permission, execution, and verification pipeline."""
        tool = self.registry.get(tool_name)
        if not tool:
            res = ToolResult(success=False, output=None, error=f"Unknown tool '{tool_name}'")
            ver = ToolVerification(verified=False, details=f"Tool '{tool_name}' does not exist in registry.")
            perm = PermissionDecision(allowed=False, reason="Unknown tool", risk_level=tool.risk_level if tool else None)
            return res, ver, perm

        # 1. Validate
        val_result = ToolValidator.validate(tool, arguments)
        if not val_result.valid:
            res = ToolResult(success=False, output=None, error=val_result.error)
            ver = ToolVerification(verified=False, details=f"Validation failed: {val_result.error}")
            perm = PermissionDecision(allowed=False, reason=val_result.error, risk_level=tool.risk_level)
            return res, ver, perm

        sanitized_args = val_result.sanitized_arguments

        # 2. Permission Check
        perm_decision = self.permissions.check_permission(tool, sanitized_args)
        if not perm_decision.allowed:
            res = ToolResult(success=False, output=None, error=f"Permission denied: {perm_decision.reason}")
            ver = ToolVerification(verified=False, details="Execution blocked by Permission System.")
            return res, ver, perm_decision

        # 3. Execution
        exec_result = tool.execute(**sanitized_args)

        # 4. Ground-truth Verification
        verification = tool.verify(sanitized_args, exec_result)

        return exec_result, verification, perm_decision

    def run_turn(
        self,
        user_prompt: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> AgentTurnResult:
        """Complete agent turn: Prompt -> Intent Analysis -> Policy Gate -> Tool Call? -> Validate -> Perms -> Exec -> Verify -> Synthesize."""
        # 1. Intent Analysis & Safety Gatekeeping
        intent = self.intent_analyzer.analyze(user_prompt, conversation_history)
        if intent.intent_type == IntentType.DESTRUCTIVE_ACTION and intent.requires_confirmation:
            return AgentTurnResult(
                tool_called=True,
                tool_name=intent.target_tool or "safe_delete_projects",
                arguments=intent.parameters,
                final_response=intent.warning_prompt or "This action is destructive and requires confirmation.",
            )

        if intent.intent_type == IntentType.EXTERNAL_ACTION and intent.requires_confirmation:
            preview = intent.confirmation_preview or {}
            preview_text = (
                "External Action Confirmation Required:\n"
                f"  Recipient : {preview.get('Recipient', 'None')}\n"
                f"  Subject   : {preview.get('Subject', 'None')}\n"
                f"  Message   : {preview.get('Message', 'None')}\n"
                f"  Attachment: {preview.get('Attachment', 'None')}\n\n"
                "Would you like me to send this email?"
            )
            return AgentTurnResult(
                tool_called=True,
                tool_name=intent.target_tool or "send_email",
                arguments=intent.parameters,
                final_response=preview_text,
            )

        # Check for multi-step goal planning (e.g. directory organization)
        from jarvis.capabilities.goal_planner import GoalPlanner
        if GoalPlanner.is_directory_organize_goal(user_prompt):
            target_dir = GoalPlanner.resolve_target_directory(user_prompt)
            planner = GoalPlanner(registry=self.registry, tool_executor=self)
            dir_name = os.path.basename(target_dir.rstrip("\\/")) or target_dir
            plan = planner.create_organization_plan(
                objective=f"Organize {dir_name}",
                directory=target_dir,
            )
            executed_plan = planner.execute_plan(plan)
            return AgentTurnResult(
                tool_called=True,
                tool_name="batch_organize_files",
                arguments={"directory": target_dir},
                final_response=executed_plan.final_summary,
            )

        if GoalPlanner.is_complex_project_goal(user_prompt):
            planner = GoalPlanner(registry=self.registry, tool_executor=self)
            outcome = planner.execute_complex_project_workflow(user_prompt)
            return AgentTurnResult(
                tool_called=True,
                tool_name="run_complex_task",
                arguments={"workflow": "presentation_prep"},
                final_response=outcome["summary"],
            )

        history = list(conversation_history or [])
        history.append({"role": "user", "content": user_prompt})

        system_prompt = self.build_system_prompt()
        ollama_response = self.ollama.chat(history, system_prompt=system_prompt)

        # Check if Ollama requested a valid registered tool
        tool_call = self.extract_tool_call(ollama_response)
        if not tool_call:
            # If Ollama responded with JSON containing a text/message field for an unregistered pseudo-tool
            fallback_text = ollama_response
            try:
                data = json.loads(ollama_response.strip())
                if isinstance(data, dict):
                    args = data.get("arguments") or data
                    if isinstance(args, dict):
                        for k in ("text", "content", "message", "reply", "answer"):
                            if k in args and isinstance(args[k], str):
                                fallback_text = args[k]
                                break
            except Exception:
                pass

            # If Ollama responded with JSON specifying tool: None/null or no text payload, fallback to plain text answer
            if not fallback_text or fallback_text.strip().startswith("{"):
                try:
                    data = json.loads(ollama_response.strip())
                    if isinstance(data, dict) and str(data.get("tool")).lower() in ("none", "null", ""):
                        fallback_text = self.ollama.chat(
                            [{"role": "user", "content": user_prompt}],
                            system_prompt="You are JARVIS. Answer the user's question directly, clearly, and concisely in plain conversational text without JSON."
                        )
                except Exception:
                    pass

            return AgentTurnResult(
                tool_called=False,
                final_response=fallback_text,
            )

        tool_name, args = tool_call

        # Run through secure execution pipeline
        exec_result, verification, perm = self.execute_tool(tool_name, args)

        if not perm.allowed:
            final_msg = f"I cannot proceed with '{tool_name}': {perm.reason}"
            if perm.custom_prompt:
                final_msg = perm.custom_prompt
            elif perm.confirmation_preview:
                preview = perm.confirmation_preview
                final_msg = (
                    "External Action Confirmation Required:\n"
                    f"  Recipient : {preview.get('Recipient', 'None')}\n"
                    f"  Subject   : {preview.get('Subject', 'None')}\n"
                    f"  Message   : {preview.get('Message', 'None')}\n"
                    f"  Attachment: {preview.get('Attachment', 'None')}\n\n"
                    "Would you like me to send this email?"
                )
            return AgentTurnResult(
                tool_called=True,
                tool_name=tool_name,
                arguments=args,
                tool_result=exec_result,
                verification=verification,
                permission_decision=perm,
                final_response=final_msg,
            )

        # Provide tool execution feedback back to Ollama for final response
        feedback_message = (
            f"Tool '{tool_name}' executed.\n"
            f"Success: {exec_result.success}\n"
            f"Output: {json.dumps(exec_result.output)}\n"
            f"Verification: {verification.details}\n"
            "Summarize the result for the user directly and concisely."
        )

        follow_up_messages = list(history)
        follow_up_messages.append({"role": "assistant", "content": ollama_response})
        follow_up_messages.append({"role": "user", "content": feedback_message})

        final_response = self.ollama.chat(follow_up_messages, system_prompt=system_prompt)

        return AgentTurnResult(
            tool_called=True,
            tool_name=tool_name,
            arguments=args,
            tool_result=exec_result,
            verification=verification,
            permission_decision=perm,
            final_response=final_response,
        )
