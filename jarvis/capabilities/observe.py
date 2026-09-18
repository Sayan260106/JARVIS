"""4. OBSERVE & VERIFY Capabilities — 'Did the action actually work?'"""

import os
from typing import Any, Optional
import json
from jarvis.capabilities.base import ObserveCapability, VerifyCapability
from jarvis.core.schemas import PlanStep, Observation, VerificationResult
from jarvis.tools.base import BaseTool, ToolResult, ToolVerification
from jarvis.tools import get_default_registry


class DefaultObserveCapability(ObserveCapability):
    """Collects runtime telemetry, output streams, and status into an Observation."""

    def observe(self, step: PlanStep, raw_result: Any, duration_ms: float) -> Observation:
        exit_code = 0
        output_str = ""
        error_str = None
        telemetry = {}

        if isinstance(raw_result, ToolResult):
            exit_code = 0 if raw_result.success else 1
            error_str = raw_result.error
            if isinstance(raw_result.output, (dict, list)):
                output_str = json.dumps(raw_result.output)
            else:
                output_str = str(raw_result.output if raw_result.output is not None else "")
            if isinstance(raw_result.output, dict):
                telemetry = {k: v for k, v in raw_result.output.items() if isinstance(v, (int, float, str, bool))}
        elif isinstance(raw_result, dict):
            exit_code = raw_result.get("exit_code", 0)
            error_str = raw_result.get("error")
            output_str = json.dumps(raw_result)
            telemetry = {k: v for k, v in raw_result.items() if k not in ("exit_code", "error") and isinstance(v, (int, float, str, bool))}
        elif isinstance(raw_result, Exception):
            exit_code = 1
            error_str = str(raw_result)
            output_str = f"Exception: {error_str}"
        else:
            output_str = str(raw_result if raw_result is not None else "")

        obs = Observation(
            step_id=step.step_id,
            exit_code=exit_code,
            output=output_str,
            error=error_str,
            telemetry=telemetry,
            duration_ms=duration_ms,
        )
        step.observation = obs
        return obs


class DefaultVerifyCapability(VerifyCapability):
    """Evaluates the observation against the step's expected outcome and tool ground truth to determine PASS/FAIL."""

    def __init__(self, registry: Optional[Any] = None):
        self.registry = registry

    def verify(self, step: PlanStep, observation: Observation) -> VerificationResult:
        # Check basic execution failure
        if observation.exit_code != 0 or observation.error is not None:
            ver = VerificationResult(
                passed=False,
                evidence=f"Exit code: {observation.exit_code}, Error: {observation.error}",
                reason=f"Step '{step.description}' failed with non-zero exit code or error output: {observation.error}",
            )
            step.verification = ver
            return ver

        # Tool-specific ground truth verification if tool is registered
        reg = self.registry or get_default_registry()
        tool = reg.get(step.tool_name) if hasattr(reg, "get") else None

        if isinstance(tool, BaseTool):
            # Parse output payload back for tool verification
            parsed_out = None
            if observation.output:
                try:
                    parsed_out = json.loads(observation.output)
                except Exception:
                    parsed_out = observation.output

            tool_res = ToolResult(
                success=True,
                output=parsed_out,
                error=observation.error,
                duration_ms=observation.duration_ms,
            )
            tool_ver: ToolVerification = tool.verify(step.arguments, tool_res)
            ver = VerificationResult(
                passed=tool_ver.verified,
                evidence=tool_ver.details,
                reason=tool_ver.details if tool_ver.verified else f"Ground-truth verification failed: {tool_ver.details}",
            )
            step.verification = ver
            return ver

        if not observation.output.strip():
            ver = VerificationResult(
                passed=False,
                evidence="Empty output",
                reason=f"Step '{step.description}' produced an unexpected empty response.",
            )
            step.verification = ver
            return ver

        ver = VerificationResult(
            passed=True,
            evidence=f"Exit code 0, Output length: {len(observation.output)} chars",
            reason=f"Step '{step.description}' satisfied execution and verification criteria.",
        )
        step.verification = ver
        return ver

