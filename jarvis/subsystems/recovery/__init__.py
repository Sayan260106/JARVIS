"""Autonomous Recovery 2.0 Subsystem for JARVIS (Phase 14).

Exports failure diagnostician, alternate selectors, prerequisite injector,
tool fallback engine, and master recovery engine.
"""

from __future__ import annotations
from typing import Optional

from jarvis.subsystems.recovery.diagnostician import FailureDiagnostician
from jarvis.subsystems.recovery.navigation_engine import AlternateNavigationEngine
from jarvis.subsystems.recovery.planner_adapter import PrerequisiteInjector
from jarvis.subsystems.recovery.recovery_engine import AutonomousRecoveryEngine
from jarvis.subsystems.recovery.schemas import (
    AlternateSelector,
    FailureCategory,
    FailureDiagnosis,
    RecoveryResolution,
)
from jarvis.subsystems.recovery.selector_engine import AlternateSelectorEngine
from jarvis.subsystems.recovery.tool_fallback_engine import ToolFallbackEngine


_default_engine: Optional[AutonomousRecoveryEngine] = None


def get_recovery_engine() -> AutonomousRecoveryEngine:
    """Returns singleton instance of AutonomousRecoveryEngine."""
    global _default_engine
    if _default_engine is None:
        _default_engine = AutonomousRecoveryEngine()
    return _default_engine


__all__ = [
    "AutonomousRecoveryEngine",
    "FailureDiagnostician",
    "AlternateSelectorEngine",
    "PrerequisiteInjector",
    "ToolFallbackEngine",
    "AlternateNavigationEngine",
    "FailureCategory",
    "FailureDiagnosis",
    "AlternateSelector",
    "RecoveryResolution",
    "get_recovery_engine",
]
