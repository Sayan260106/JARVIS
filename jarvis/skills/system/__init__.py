"""Operating System Control Skills for Phase 11.

Domain: system/
Skills:
- system.get_metrics
- system.control_window
- system.manage_process
"""

from __future__ import annotations
import os
from typing import Any, Dict, List, Optional
import psutil
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
from jarvis.subsystems.system.windows_executor import WindowsExecutor


class SystemGetMetricsSkill(BaseSkill):
    name = "system.get_metrics"
    domain = "system"
    capability = "Retrieves CPU load, RAM utilization, and disk storage metrics."
    required_tools = ["get_hardware_metrics"]
    parameters = {}

    def execute(self, params: Dict[str, Any], context: SkillContext) -> SkillResult:
        if self.registry:
            tool = self.registry.get("get_hardware_metrics")
            if tool:
                res = tool.execute()
                if res.success:
                    context.set("system_metrics", res.output)
                    return SkillResult(success=True, output=res.output, artifacts=res.output if isinstance(res.output, dict) else {})

        cpu = psutil.cpu_percent(interval=0.05)
        mem = psutil.virtual_memory()
        metrics = {
            "cpu_percent": cpu,
            "ram_percent": mem.percent,
            "ram_used_gb": round(mem.used / (1024**3), 2),
            "ram_total_gb": round(mem.total / (1024**3), 2),
        }
        context.set("system_metrics", metrics)
        return SkillResult(success=True, output=metrics, artifacts=metrics)


class SystemControlWindowSkill(BaseSkill):
    name = "system.control_window"
    domain = "system"
    capability = "Focuses, minimizes, maximizes, or restores application windows."
    required_tools = ["window_control", "focus_window"]
    parameters = {
        "title": SkillParameter("title", "string", "Window title or application name", required=True),
        "state": SkillParameter("state", "string", "Action ('focus', 'minimize', 'maximize', 'restore')", required=False, default="focus"),
    }

    def execute(self, params: Dict[str, Any], context: SkillContext) -> SkillResult:
        title = params["title"]
        state = params.get("state", "focus").lower()

        if state == "focus":
            success, msg = WindowsExecutor.focus_window(title)
        else:
            success, msg = WindowsExecutor.set_window_state(title, state)

        return SkillResult(
            success=success,
            output=msg,
            artifacts={"window": title, "state": state},
        )


class SystemManageProcessSkill(BaseSkill):
    name = "system.manage_process"
    domain = "system"
    capability = "Inspects process status or terminates running tasks."
    required_tools = ["check_process", "stop_process"]
    parameters = {
        "process_name": SkillParameter("process_name", "string", "Process executable name (e.g. 'ollama', 'node')", required=True),
        "action": SkillParameter("action", "string", "Action ('check' or 'stop')", required=False, default="check"),
    }

    def execute(self, params: Dict[str, Any], context: SkillContext) -> SkillResult:
        pname = params["process_name"]
        act = params.get("action", "check").lower()

        if act == "check":
            running = False
            for p in psutil.process_iter(["name"]):
                if p.info["name"] and pname.lower() in p.info["name"].lower():
                    running = True
                    break
            msg = f"Process '{pname}' is {'RUNNING' if running else 'STOPPED'}."
            return SkillResult(success=True, output=msg, artifacts={"process": pname, "running": running})
        else:
            success, msg = WindowsExecutor.stop_process(pname)
            return SkillResult(success=success, output=msg, artifacts={"process": pname, "stopped": success})
