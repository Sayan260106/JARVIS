"""Skill Registry for Phase 11 — Workflow / Skill System.

Provides namespaced registration, lookup, and discovery of skills.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from jarvis.skills.base import BaseSkill


class SkillRegistry:
    """Central registry of all modular skills in JARVIS."""

    _instance: Optional["SkillRegistry"] = None

    def __init__(self, tool_registry: Optional[Any] = None):
        self.tool_registry = tool_registry
        self._skills: Dict[str, BaseSkill] = {}

    @classmethod
    def get_instance(cls, tool_registry: Optional[Any] = None) -> "SkillRegistry":
        if cls._instance is None:
            cls._instance = SkillRegistry(tool_registry=tool_registry)
        return cls._instance

    def register(self, skill: BaseSkill) -> None:
        """Registers a skill instance."""
        if self.tool_registry and not skill.registry:
            skill.registry = self.tool_registry
        self._skills[skill.name.lower()] = skill

    def get(self, name: str) -> Optional[BaseSkill]:
        """Retrieves a skill by name (e.g. 'classroom.find_material' or 'pdf.summarize')."""
        return self._skills.get(name.strip().lower())

    def list_skills(self) -> List[BaseSkill]:
        """Returns all registered skills."""
        return list(self._skills.values())

    def list_skill_names(self) -> List[str]:
        """Returns all registered skill names."""
        return sorted(list(self._skills.keys()))

    def list_by_domain(self, domain: str) -> List[BaseSkill]:
        """Returns all skills belonging to a domain (e.g. 'classroom', 'pdf', 'vscode')."""
        clean = domain.strip().lower()
        return [s for s in self._skills.values() if s.domain.lower() == clean]

    def get_prompt_description(self) -> str:
        """Generates a structured overview of available skills for LLM planning."""
        lines = ["Available Skills:"]
        domains: Dict[str, List[BaseSkill]] = {}
        for skill in self._skills.values():
            domains.setdefault(skill.domain, []).append(skill)

        for dom, skills in sorted(domains.items()):
            lines.append(f"Domain: {dom}/")
            for s in skills:
                param_str = ", ".join([f"{p}: {d.type_name}" for p, d in s.parameters.items()])
                lines.append(f"  - {s.name}({param_str}): {s.capability}")
        return "\n".join(lines)
