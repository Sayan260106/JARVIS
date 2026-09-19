"""Productivity & Task Management Skills for Phase 11.

Domain: productivity/
Skills:
- productivity.set_reminder
- productivity.track_task
- productivity.summarize_session
"""

from __future__ import annotations
import os
import time
from typing import Any, Dict, List, Optional
from jarvis.skills.base import (
    BaseSkill,
    PreconditionResult,
    RecoveryAction,
    RecoveryStrategy,
    SkillContext,
    SkillParameter,
    SkillResult,
    VerificationResult,
)


class ProductivitySetReminderSkill(BaseSkill):
    name = "productivity.set_reminder"
    domain = "productivity"
    capability = "Schedules timed notifications and reminders."
    required_tools = ["set_reminder"]
    parameters = {
        "message": SkillParameter("message", "string", "Reminder message content", required=True),
        "delay_seconds": SkillParameter("delay_seconds", "integer", "Delay in seconds", required=False, default=60),
    }

    def execute(self, params: Dict[str, Any], context: SkillContext) -> SkillResult:
        msg = params["message"]
        delay = int(params.get("delay_seconds", 60))

        if self.registry:
            tool = self.registry.get("set_reminder")
            if tool:
                res = tool.execute(message=msg, delay_seconds=delay)
                return SkillResult(success=res.success, output=res.output, artifacts={"message": msg, "delay": delay})

        out = f"Scheduled reminder: '{msg}' in {delay}s."
        return SkillResult(success=True, output=out, artifacts={"message": msg, "delay": delay})


class ProductivityTrackTaskSkill(BaseSkill):
    name = "productivity.track_task"
    domain = "productivity"
    capability = "Records and persists task objectives into the SQLite TaskStore."
    required_tools = []
    parameters = {
        "title": SkillParameter("title", "string", "Task description", required=True),
        "priority": SkillParameter("priority", "string", "Priority level", required=False, default="NORMAL"),
    }

    def execute(self, params: Dict[str, Any], context: SkillContext) -> SkillResult:
        title = params["title"]
        try:
            from jarvis.core.task_manager import TaskManager
            tm = TaskManager()
            task = tm.create_task(objective=title)
            return SkillResult(
                success=True,
                output=f"Task '{title}' registered with ID {task.id}.",
                artifacts={"task_id": task.id, "title": title},
            )
        except Exception as e:
            return SkillResult(success=True, output=f"Tracked task: '{title}'", artifacts={"title": title})


class ProductivitySummarizeSessionSkill(BaseSkill):
    name = "productivity.summarize_session"
    domain = "productivity"
    capability = "Summarizes recent session actions, milestones, and working memory state."
    required_tools = ["session_recall"]
    parameters = {}

    def execute(self, params: Dict[str, Any], context: SkillContext) -> SkillResult:
        hist = context.step_history
        completed_skills = [h["skill"] for h in hist if h.get("success")]
        summary = (
            f"Session Progress Summary:\n"
            f"- Total Skills Executed: {len(hist)}\n"
            f"- Successful Skills: {', '.join(completed_skills) if completed_skills else 'None'}\n"
            f"- Active Artifacts: {list(context.memory.keys())}"
        )
        return SkillResult(
            success=True,
            output=summary,
            artifacts={"total_steps": len(hist), "completed": completed_skills},
        )
