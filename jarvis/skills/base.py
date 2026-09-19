"""Base Classes and Contracts for Phase 11 — Workflow / Skill System.

Every skill encapsulates:
1. Capability (semantic intent and domain)
2. Required Tools (from ToolRegistry)
3. Parameters (typed inputs and validation)
4. Preconditions (guard assertions before execution)
5. Execution (discrete tool/logic operations)
6. Verification (ground-truth post-check)
7. Recovery (deterministic recovery strategy if failed)
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from enum import Enum
import time
from typing import Any, Callable, Dict, List, Optional, Tuple


class RecoveryStrategy(str, Enum):
    RETRY = "retry"
    ALTERNATE_TOOL = "alternate_tool"
    FALLBACK_ARGUMENTS = "fallback_arguments"
    STRUCTURAL_REPLAN = "structural_replan"
    ESCALATE_TO_USER = "escalate_to_user"


@dataclass
class SkillParameter:
    """Defines a parameter expected by a skill."""
    name: str
    type_name: str  # "string", "integer", "boolean", "list", "dict", "path"
    description: str
    required: bool = True
    default: Any = None

    def validate(self, value: Any) -> Tuple[bool, Optional[str]]:
        if value is None:
            if self.required:
                return False, f"Missing required parameter '{self.name}'"
            return True, None
        return True, None


@dataclass
class PreconditionResult:
    """Result of checking skill prerequisites."""
    satisfied: bool
    missing_requirements: List[str] = field(default_factory=list)
    recovery_recommendation: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class VerificationResult:
    """Result of verifying skill execution against ground truth."""
    passed: bool
    evidence: str = ""
    explanation: str = ""
    diagnostics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RecoveryAction:
    """Prescribed recovery strategy if a precondition or verification fails."""
    strategy: RecoveryStrategy
    explanation: str
    suggested_params: Dict[str, Any] = field(default_factory=dict)
    alternate_skill: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["strategy"] = self.strategy.value
        return d


@dataclass
class SkillResult:
    """Output telemetry of a skill execution."""
    success: bool
    output: Any = None
    artifacts: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    duration_ms: float = 0.0
    verification: Optional[VerificationResult] = None
    recovery: Optional[RecoveryAction] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "output": self.output,
            "artifacts": self.artifacts,
            "error": self.error,
            "duration_ms": round(self.duration_ms, 2),
            "verification": self.verification.to_dict() if self.verification else None,
            "recovery": self.recovery.to_dict() if self.recovery else None,
        }


class SkillContext:
    """Runtime context shared across composed skills in a workflow."""

    def __init__(
        self,
        registry: Optional[Any] = None,
        working_memory: Optional[Dict[str, Any]] = None,
        tool_executor: Optional[Any] = None,
    ):
        self.registry = registry
        self.memory: Dict[str, Any] = dict(working_memory or {})
        self.tool_executor = tool_executor
        self.step_history: List[Dict[str, Any]] = []

    def set(self, key: str, value: Any) -> None:
        self.memory[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self.memory.get(key, default)

    def record_step(self, skill_name: str, result: SkillResult) -> None:
        self.step_history.append({
            "skill": skill_name,
            "timestamp": time.time(),
            "success": result.success,
            "artifacts": result.artifacts,
        })


class BaseSkill(ABC):
    """Abstract Base Class for all JARVIS skills."""

    name: str = "base.skill"
    domain: str = "base"
    capability: str = "Base skill capability"
    required_tools: List[str] = []
    parameters: Dict[str, SkillParameter] = {}

    def __init__(self, registry: Optional[Any] = None):
        self.registry = registry

    def invoke_tool(self, tool_name: str, **kwargs) -> Optional[Any]:
        """Dispatches to registered tool handling both kwargs and single dict execute() signatures."""
        if not self.registry:
            return None
        tool = self.registry.get(tool_name)
        if not tool:
            return None
        try:
            return tool.execute(**kwargs)
        except TypeError:
            try:
                return tool.execute(kwargs)
            except Exception:
                return None
        except Exception:
            return None

    def check_preconditions(
        self, params: Dict[str, Any], context: SkillContext
    ) -> PreconditionResult:
        """Verifies that prerequisites are met before execution."""
        missing = []
        # 1. Parameter presence check
        for pname, pdef in self.parameters.items():
            if pdef.required and pname not in params and pdef.default is None:
                missing.append(f"Parameter '{pname}' is required")

        # 2. Tool availability check (if registry provided)
        if self.registry:
            for tool_name in self.required_tools:
                if not self.registry.get(tool_name):
                    missing.append(f"Required tool '{tool_name}' not found in registry")

        if missing:
            return PreconditionResult(
                satisfied=False,
                missing_requirements=missing,
                recovery_recommendation="Ensure required tools and arguments are provided before execution.",
            )

        return PreconditionResult(satisfied=True)

    @abstractmethod
    def execute(self, params: Dict[str, Any], context: SkillContext) -> SkillResult:
        """Executes the discrete skill actions."""
        pass

    def verify(
        self, params: Dict[str, Any], result: SkillResult, context: SkillContext
    ) -> VerificationResult:
        """Verifies ground-truth effects of the skill. Default verifies result.success."""
        if not result.success:
            return VerificationResult(
                passed=False,
                explanation=result.error or "Skill execution reported failure.",
            )
        return VerificationResult(
            passed=True,
            explanation=f"Skill '{self.name}' completed and verified.",
            evidence=str(result.output)[:120],
        )

    def recover(
        self,
        failed_phase: str,
        error: str,
        params: Dict[str, Any],
        context: SkillContext,
    ) -> RecoveryAction:
        """Determines recovery strategy if preconditions or verification fails."""
        return RecoveryAction(
            strategy=RecoveryStrategy.RETRY,
            explanation=f"Failed during {failed_phase}: {error}. Attempting retry with default parameters.",
            suggested_params=params,
        )

    def run(self, params: Optional[Dict[str, Any]] = None, context: Optional[SkillContext] = None) -> SkillResult:
        """Runs the complete lifecycle: Preconditions -> Execute -> Verify -> (Recover if needed)."""
        params = dict(params or {})
        # Apply defaults
        for pname, pdef in self.parameters.items():
            if pname not in params and pdef.default is not None:
                params[pname] = pdef.default

        ctx = context or SkillContext(registry=self.registry)
        start_t = time.perf_counter()

        # 1. Preconditions
        pre = self.check_preconditions(params, ctx)
        if not pre.satisfied:
            rec = self.recover("preconditions", "; ".join(pre.missing_requirements), params, ctx)
            return SkillResult(
                success=False,
                error=f"Preconditions not met: {'; '.join(pre.missing_requirements)}",
                duration_ms=(time.perf_counter() - start_t) * 1000,
                recovery=rec,
            )

        # 2. Execute
        try:
            res = self.execute(params, ctx)
        except Exception as e:
            rec = self.recover("execution", str(e), params, ctx)
            return SkillResult(
                success=False,
                error=f"Execution exception: {e}",
                duration_ms=(time.perf_counter() - start_t) * 1000,
                recovery=rec,
            )

        res.duration_ms = (time.perf_counter() - start_t) * 1000

        # 3. Verify
        ver = self.verify(params, res, ctx)
        res.verification = ver
        if not ver.passed:
            res.success = False
            res.recovery = self.recover("verification", ver.explanation, params, ctx)

        # 4. Context memory record
        ctx.record_step(self.name, res)
        return res
