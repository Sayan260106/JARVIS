"""4. OBSERVE & VERIFY Capabilities — 'Did the action actually work?'"""

from typing import Any
import json
from jarvis.capabilities.base import ObserveCapability, VerifyCapability
from jarvis.core.schemas import PlanStep, Observation, VerificationResult


class DefaultObserveCapability(ObserveCapability):
    """Collects runtime telemetry, output streams, and status into an Observation."""

    def observe(self, step: PlanStep, raw_result: Any, duration_ms: float) -> Observation:
        exit_code = 0
        output_str = ""
        error_str = None
        telemetry = {}

        if isinstance(raw_result, dict):
            exit_code = raw_result.get("exit_code", 0)
            error_str = raw_result.get("error")
            output_str = json.dumps(raw_result)
            telemetry = {k: v for k, v in raw_result.items() if k not in ("exit_code", "error")}
        elif isinstance(raw_result, Exception):
            exit_code = 1
            error_str = str(raw_result)
            output_str = f"Exception: {error_str}"
        else:
            output_str = str(raw_result)

        return Observation(
            step_id=step.step_id,
            exit_code=exit_code,
            output=output_str,
            error=error_str,
            telemetry=telemetry,
            duration_ms=duration_ms,
        )


class DefaultVerifyCapability(VerifyCapability):
    """Evaluates the observation against the step's expected outcome to determine PASS/FAIL."""

    def verify(self, step: PlanStep, observation: Observation) -> VerificationResult:
        if observation.exit_code != 0 or observation.error is not None:
            return VerificationResult(
                passed=False,
                evidence=f"Exit code: {observation.exit_code}, Error: {observation.error}",
                reason=f"Step '{step.description}' failed with non-zero exit code or error output.",
            )

        if not observation.output.strip():
            return VerificationResult(
                passed=False,
                evidence="Empty output",
                reason=f"Step '{step.description}' produced an unexpected empty response.",
            )

        return VerificationResult(
            passed=True,
            evidence=f"Exit code 0, Output length: {len(observation.output)} chars",
            reason=f"Step '{step.description}' satisfied execution and verification criteria.",
        )
