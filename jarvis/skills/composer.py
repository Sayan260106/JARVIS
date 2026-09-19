"""Skill Composer for Phase 11 — Workflow / Skill System.

Enables composing modular skills into end-to-end multi-step pipelines:
Example:
    classroom.find_material()
    classroom.download_material()
    pdf.summarize()
    vscode.open_file()

Supports automatic artifact/parameter piping between skills,
execution monitoring, verification, and compilation to ExecutionPlan steps.
"""

from __future__ import annotations
from dataclasses import dataclass, field
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from jarvis.skills.base import (
    BaseSkill,
    RecoveryAction,
    RecoveryStrategy,
    SkillContext,
    SkillResult,
    VerificationResult,
)
from jarvis.skills.registry import SkillRegistry
from jarvis.core.schemas import ExecutionPlan, PlanStep, SubsystemType, TaskObjective


@dataclass
class ComposedSkillStep:
    """A configured step in a composite skill workflow."""
    skill_name: str
    params: Dict[str, Any] = field(default_factory=dict)
    pipe_artifacts: Dict[str, str] = field(default_factory=dict)  # maps context key -> param name


@dataclass
class CompositionExecutionReport:
    """Report summarizing the end-to-end execution of composed skills."""
    success: bool
    total_steps: int
    completed_steps: int
    step_results: List[Dict[str, Any]] = field(default_factory=list)
    final_output: Any = None
    duration_ms: float = 0.0
    failed_skill: Optional[str] = None
    recovery_action: Optional[RecoveryAction] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "total_steps": self.total_steps,
            "completed_steps": self.completed_steps,
            "step_results": self.step_results,
            "final_output": self.final_output,
            "duration_ms": round(self.duration_ms, 2),
            "failed_skill": self.failed_skill,
            "recovery_action": self.recovery_action.to_dict() if self.recovery_action else None,
        }


class SkillComposer:
    """Composes, validates, and coordinates chains of modular skills."""

    def __init__(self, skill_registry: Optional[SkillRegistry] = None):
        self.registry = skill_registry or SkillRegistry.get_instance()

    def compose(
        self,
        steps: List[Tuple[str, Dict[str, Any]]],
        pipe_rules: Optional[Dict[str, str]] = None,
    ) -> List[ComposedSkillStep]:
        """Creates a validated list of ComposedSkillStep items."""
        composed = []
        default_pipes = {
            "downloaded_file_path": "file_path",
            "latest_document_path": "file_path",
            "material_title": "query",
            "url": "url",
            "target_course": "course",
        }
        active_pipes = dict(default_pipes)
        if pipe_rules:
            active_pipes.update(pipe_rules)

        for name, params in steps:
            skill = self.registry.get(name)
            if not skill:
                raise ValueError(f"Unknown skill '{name}' cannot be composed.")
            composed.append(
                ComposedSkillStep(
                    skill_name=name,
                    params=dict(params),
                    pipe_artifacts=active_pipes,
                )
            )
        return composed

    def execute_chain(
        self,
        steps: List[ComposedSkillStep] | List[Tuple[str, Dict[str, Any]]],
        context: Optional[SkillContext] = None,
    ) -> CompositionExecutionReport:
        """Executes composed skills sequentially, piping outputs into inputs."""
        ctx = context or SkillContext(registry=self.registry.tool_registry)
        start_t = time.perf_counter()

        # Normalize steps
        norm_steps: List[ComposedSkillStep] = []
        if steps and isinstance(steps[0], tuple):
            norm_steps = self.compose(steps)  # type: ignore
        else:
            norm_steps = list(steps)  # type: ignore

        results: List[Dict[str, Any]] = []
        last_output = None

        for idx, step in enumerate(norm_steps, 1):
            skill = self.registry.get(step.skill_name)
            if not skill:
                return CompositionExecutionReport(
                    success=False,
                    total_steps=len(norm_steps),
                    completed_steps=idx - 1,
                    failed_skill=step.skill_name,
                    final_output=f"Skill '{step.skill_name}' not registered.",
                    duration_ms=(time.perf_counter() - start_t) * 1000,
                )

            # Auto-pipe context variables into missing required parameters
            effective_params = dict(step.params)
            for ctx_key, param_name in step.pipe_artifacts.items():
                if param_name in skill.parameters and param_name not in effective_params:
                    val = ctx.get(ctx_key)
                    if val is not None:
                        effective_params[param_name] = val

            # Run skill lifecycle
            res = skill.run(params=effective_params, context=ctx)
            results.append({
                "step": idx,
                "skill": step.skill_name,
                "params": effective_params,
                "success": res.success,
                "output": res.output,
                "artifacts": res.artifacts,
            })

            # Pass artifacts into context memory
            for k, v in res.artifacts.items():
                ctx.set(k, v)

            last_output = res.output

            # If skill failed, check recovery
            if not res.success:
                return CompositionExecutionReport(
                    success=False,
                    total_steps=len(norm_steps),
                    completed_steps=idx - 1,
                    step_results=results,
                    final_output=res.error or "Step execution failed.",
                    duration_ms=(time.perf_counter() - start_t) * 1000,
                    failed_skill=step.skill_name,
                    recovery_action=res.recovery,
                )

        return CompositionExecutionReport(
            success=True,
            total_steps=len(norm_steps),
            completed_steps=len(norm_steps),
            step_results=results,
            final_output=last_output,
            duration_ms=(time.perf_counter() - start_t) * 1000,
        )

    def compile_to_plan(
        self,
        objective: TaskObjective,
        composed_steps: List[ComposedSkillStep] | List[Tuple[str, Dict[str, Any]]],
    ) -> ExecutionPlan:
        """Translates a chain of skills into discrete PlanSteps for the central agent loop."""
        norm_steps = self.compose(composed_steps) if (composed_steps and isinstance(composed_steps[0], tuple)) else composed_steps
        plan_steps: List[PlanStep] = []
        prev_step_id: Optional[str] = None

        domain_to_subsystem = {
            "browser": SubsystemType.WEB,
            "classroom": SubsystemType.WEB,
            "vscode": SubsystemType.SYSTEM,
            "files": SubsystemType.SYSTEM,
            "pdf": SubsystemType.DOCUMENT,
            "research": SubsystemType.LOCAL,
            "coding": SubsystemType.SYSTEM,
            "system": SubsystemType.SYSTEM,
            "productivity": SubsystemType.LOCAL,
        }

        for idx, step in enumerate(norm_steps, 1):  # type: ignore
            skill = self.registry.get(step.skill_name)
            domain = skill.domain if skill else "system"
            subsystem = domain_to_subsystem.get(domain, SubsystemType.SYSTEM)
            tool_name = skill.required_tools[0] if skill and skill.required_tools else "run_command"

            p_step = PlanStep.create(
                description=f"[{skill.domain.upper() if skill else 'SKILL'}] {skill.capability if skill else step.skill_name}",
                subsystem=subsystem,
                tool_name=tool_name,
                arguments=dict(step.params),
                expected_outcome=f"Skill '{step.skill_name}' verified and artifacts produced.",
                depends_on=[prev_step_id] if prev_step_id else [],
            )
            plan_steps.append(p_step)
            prev_step_id = p_step.step_id

        return ExecutionPlan.create(objective=objective, steps=plan_steps)
