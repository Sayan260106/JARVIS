"""Productivity & Hardware Monitoring Tools for Windows.

Implements folder creation, process inspection, hardware metrics, and reminders.
"""

from __future__ import annotations
import os
import threading
import time
from typing import Any, Dict, List, Optional
from jarvis.tools.base import BaseTool, RiskLevel, ToolParameter, ToolResult, ToolVerification


class CreateFolderTool(BaseTool):
    """Creates a new folder / directory."""
    name = "create_folder"
    description = "Creates a new folder or directory at the specified path."
    risk_level = RiskLevel.MEDIUM
    parameters = {
        "path": ToolParameter("path", "string", "Directory path to create (e.g. 'GATE 2027').", required=True),
    }

    def execute(self, path: str, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        abs_path = os.path.abspath(path)
        try:
            os.makedirs(abs_path, exist_ok=True)
            return ToolResult(
                success=True,
                output={"path": abs_path, "created": True},
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=str(e),
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        abs_path = os.path.abspath(arguments["path"])
        if not os.path.exists(abs_path) or not os.path.isdir(abs_path):
            return ToolVerification(verified=False, details=f"Folder '{abs_path}' was not created.")
        return ToolVerification(verified=True, details=f"Folder verified at '{abs_path}'.")


class CheckProcessTool(BaseTool):
    """Checks whether a named process or service is actively running."""
    name = "check_process"
    description = "Checks if a specific program or process (e.g. 'ollama', 'spotify', 'code') is currently running."
    risk_level = RiskLevel.LOW
    parameters = {
        "process_name": ToolParameter("process_name", "string", "Name of process to inspect (e.g. 'ollama').", required=True),
    }

    def execute(self, process_name: str, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        import psutil
        clean_target = process_name.strip().lower()
        matching_procs = []

        try:
            for p in psutil.process_iter(["pid", "name"]):
                try:
                    pname = p.info["name"]
                    if pname and clean_target in pname.lower():
                        matching_procs.append({
                            "pid": p.info["pid"],
                            "name": pname,
                        })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            is_running = len(matching_procs) > 0
            return ToolResult(
                success=True,
                output={
                    "process_name": process_name,
                    "is_running": is_running,
                    "matching_instances": matching_procs,
                    "count": len(matching_procs),
                },
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=str(e),
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        if not result.success:
            return ToolVerification(verified=False, details=f"Process check failed: {result.error}")
        pname = arguments["process_name"]
        running = result.output.get("is_running", False)
        status = "running" if running else "not running"
        return ToolVerification(verified=True, details=f"Process '{pname}' status verified as {status}.")


class GetHardwareMetricsTool(BaseTool):
    """Retrieves specific RAM usage and CPU metrics."""
    name = "get_hardware_metrics"
    description = "Queries real-time hardware metrics: RAM used/total in GB, RAM usage %, and CPU load %."
    risk_level = RiskLevel.LOW
    parameters = {
        "metric": ToolParameter(
            "metric",
            "string",
            "Target metric to query: 'ram', 'cpu', or 'all' (default: 'all').",
            required=False,
            default="all",
        ),
    }

    def execute(self, metric: str = "all", **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        import psutil

        try:
            mem = psutil.virtual_memory()
            cpu_percent = psutil.cpu_percent(interval=0.1)

            data = {
                "ram_used_gb": round(mem.used / (1024**3), 2),
                "ram_total_gb": round(mem.total / (1024**3), 2),
                "ram_percent": mem.percent,
                "cpu_percent": cpu_percent,
                "cpu_cores": psutil.cpu_count(logical=True),
            }

            if metric.lower() == "ram":
                output = {
                    "ram_used_gb": data["ram_used_gb"],
                    "ram_total_gb": data["ram_total_gb"],
                    "ram_percent": data["ram_percent"],
                    "summary": f"RAM Usage: {data['ram_used_gb']} GB of {data['ram_total_gb']} GB ({data['ram_percent']}%)",
                }
            elif metric.lower() == "cpu":
                output = {
                    "cpu_percent": data["cpu_percent"],
                    "cpu_cores": data["cpu_cores"],
                    "summary": f"CPU Load: {data['cpu_percent']}% across {data['cpu_cores']} logical cores",
                }
            else:
                output = {
                    **data,
                    "summary": f"RAM: {data['ram_used_gb']}/{data['ram_total_gb']} GB ({data['ram_percent']}%), CPU: {data['cpu_percent']}%",
                }

            return ToolResult(
                success=True,
                output=output,
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=str(e),
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        if not result.success:
            return ToolVerification(verified=False, details=f"Metrics retrieval failed: {result.error}")
        return ToolVerification(verified=True, details="Hardware metrics verified.")


class SetReminderTool(BaseTool):
    """Schedules a reminder alert in the background."""
    name = "set_reminder"
    description = "Schedules an alert or reminder after a delay in seconds (e.g. 60) or minutes."
    risk_level = RiskLevel.LOW
    parameters = {
        "message": ToolParameter("message", "string", "Reminder text to announce.", required=True),
        "delay_seconds": ToolParameter("delay_seconds", "integer", "Wait time before reminding.", required=False, default=60),
    }

    def __init__(self, alert_callback=None):
        super().__init__()
        self.alert_callback = alert_callback
        self.active_reminders: List[Dict[str, Any]] = []

    def _trigger_reminder(self, message: str):
        """Called in background thread when delay expires."""
        print(f"\n[JARVIS REMINDER]: {message}")
        if self.alert_callback:
            try:
                self.alert_callback(message)
            except Exception:
                pass
        else:
            try:
                from jarvis.subsystems.local.tts import LocalTTS
                tts = LocalTTS()
                tts.speak(f"Reminder: {message}")
            except Exception:
                pass

    def execute(self, message: str, delay_seconds: int = 60, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        seconds = max(1, int(delay_seconds))
        target_time = time.time() + seconds

        # Start timer in background daemon thread
        timer = threading.Timer(seconds, self._trigger_reminder, args=[message])
        timer.daemon = True
        timer.start()

        reminder_info = {
            "message": message,
            "delay_seconds": seconds,
            "target_timestamp": target_time,
            "scheduled_at": time.strftime("%H:%M:%S", time.localtime()),
        }
        self.active_reminders.append(reminder_info)

        return ToolResult(
            success=True,
            output=reminder_info,
            duration_ms=(time.perf_counter() - start_t) * 1000,
        )

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        if not result.success:
            return ToolVerification(verified=False, details="Failed to schedule reminder timer.")
        return ToolVerification(
            verified=True,
            details=f"Reminder for '{arguments['message']}' scheduled to fire in {arguments.get('delay_seconds', 60)}s."
        )
