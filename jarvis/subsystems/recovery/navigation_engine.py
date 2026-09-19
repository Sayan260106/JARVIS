"""Alternate Navigation Engine for Autonomous Recovery 2.0 (Phase 14).

Formulates alternative navigation routes when page transitions, links, or URLs fail.
"""

from __future__ import annotations
import urllib.parse
from typing import List, Optional

from jarvis.core.schemas import PlanStep, SubsystemType


class AlternateNavigationEngine:
    """Computes alternative browser navigation routes and recovery steps."""

    def derive_alternate_navigation(self, step: PlanStep, target_url: str) -> List[PlanStep]:
        """Generates alternate navigation steps such as direct URL navigation or search navigation."""
        steps: List[PlanStep] = []

        parsed = urllib.parse.urlparse(target_url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"

        # 1. State refresh: reload or navigate to base domain
        if base_url and base_url != target_url:
            steps.append(
                PlanStep.create(
                    description=f"Navigate to base portal '{base_url}' to establish session",
                    subsystem=SubsystemType.WEB,
                    tool_name="browser_navigate",
                    arguments={"url": base_url},
                    expected_outcome=f"Session established at {base_url}.",
                )
            )

        # 2. Browser refresh step
        steps.append(
            PlanStep.create(
                description=f"Refresh browser state and DOM elements",
                subsystem=SubsystemType.WEB,
                tool_name="browser_get_state",
                arguments={},
                expected_outcome="Browser DOM and active elements refreshed.",
            )
        )

        return steps
