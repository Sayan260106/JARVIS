"""Proactive Tools for Phase 17 — Proactive JARVIS.

Integrates scheduled tasks, folder watchers, process monitors, and multi-channel
notifications directly into the JARVIS Tool Registry.
"""

from __future__ import annotations
import os
import time
from typing import Any, Dict, List, Optional

from jarvis.tools.base import (
    BaseTool,
    PermissionLevel,
    RiskLevel,
    ToolParameter,
    ToolResult,
    ToolVerification,
)
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from jarvis.subsystems.proactive.engine import ProactiveEngine
from jarvis.subsystems.proactive.schemas import (
    Event,
    EventType,
    NotificationChannel,
)


class ScheduleTaskTool(BaseTool):
    """Schedules recurring or one-off tasks with natural language or cron expressions."""

    name = "schedule_task"
    description = "Schedules an autonomous task to run on a recurring schedule (e.g. 'Every Monday, check Classroom for new assignments' or 'Every 10 minutes')."
    risk_level = RiskLevel.LOW
    permission_level = PermissionLevel.LEVEL_0_READ

    parameters = {
        "expression": ToolParameter(
            name="expression",
            type="string",
            description="Schedule expression (e.g. 'Every Monday at 9:00 AM', 'Every day at 18:00', 'Every 15 minutes').",
            required=True,
        ),
        "objective": ToolParameter(
            name="objective",
            type="string",
            description="The goal or workflow for JARVIS to execute when triggered.",
            required=True,
        ),
        "title": ToolParameter(
            name="title",
            type="string",
            description="Optional short label for this scheduled task.",
            required=False,
            default="",
        ),
    }

    def __init__(self, engine: Optional[ProactiveEngine] = None):
        super().__init__()
        self.engine = engine

    def _get_engine(self) -> Any:
        if self.engine is not None:
            return self.engine
        from jarvis.subsystems.proactive.engine import ProactiveEngine
        return ProactiveEngine.get_instance()

    def execute(self, expression: str, objective: str, title: str = "", **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        engine = self._get_engine()
        try:
            trigger, sched_task = engine.schedule_task(
                schedule_expr=expression,
                objective=objective,
                title=title or None,
            )
            next_run_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(sched_task.next_run))
            output = {
                "schedule_id": sched_task.schedule_id,
                "trigger_id": trigger.trigger_id,
                "title": sched_task.title,
                "expression": sched_task.schedule_expr,
                "objective": sched_task.objective,
                "next_run": next_run_str,
                "next_run_timestamp": sched_task.next_run,
                "message": f"Successfully scheduled '{sched_task.title}' ({sched_task.schedule_expr}). Next run: {next_run_str}.",
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
                error=f"Failed to schedule task: {e}",
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        if not result.success:
            return ToolVerification(verified=False, details=f"Scheduling failed: {result.error}")
        return ToolVerification(
            verified=True,
            details=f"Task scheduled with ID {result.output.get('schedule_id')} for {result.output.get('next_run')}."
        )


class WatchFolderTool(BaseTool):
    """Sets up an environment watcher monitoring a directory for new or modified files."""

    name = "watch_folder"
    description = "Monitors a directory (e.g. Downloads) for files matching a pattern (e.g. *.pdf) and triggers an autonomous action."
    risk_level = RiskLevel.LOW
    permission_level = PermissionLevel.LEVEL_0_READ

    parameters = {
        "folder_path": ToolParameter(
            name="folder_path",
            type="string",
            description="Directory path to watch (e.g. 'Downloads' or 'C:/Users/.../Downloads').",
            required=True,
        ),
        "file_pattern": ToolParameter(
            name="file_pattern",
            type="string",
            description="Glob filter pattern for files (e.g. '*.pdf', '*.docx', '*.zip'). Default: '*.pdf'",
            required=False,
            default="*.pdf",
        ),
        "target_objective": ToolParameter(
            name="target_objective",
            type="string",
            description="Action for JARVIS to perform when a new file is detected.",
            required=False,
            default="",
        ),
    }

    def __init__(self, engine: Optional[ProactiveEngine] = None):
        super().__init__()
        self.engine = engine

    def _get_engine(self) -> Any:
        if self.engine is not None:
            return self.engine
        from jarvis.subsystems.proactive.engine import ProactiveEngine
        return ProactiveEngine.get_instance()

    def execute(self, folder_path: str, file_pattern: str = "*.pdf", target_objective: str = "", **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        engine = self._get_engine()
        resolved_folder = folder_path
        if folder_path.lower() in ("downloads", "download", "~/downloads"):
            resolved_folder = os.path.join(os.path.expanduser("~"), "Downloads")

        try:
            trigger = engine.watch_folder(
                folder_path=resolved_folder,
                file_pattern=file_pattern,
                target_objective=target_objective or f"Process and verify new {file_pattern} file in {folder_path}",
            )
            output = {
                "trigger_id": trigger.trigger_id,
                "folder_path": resolved_folder,
                "file_pattern": file_pattern,
                "target_objective": trigger.target_objective,
                "message": f"Actively watching '{resolved_folder}' for '{file_pattern}'. Autonomous workflow ready.",
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
                error=f"Failed to start folder watcher: {e}",
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        if not result.success:
            return ToolVerification(verified=False, details=f"Folder watch failed: {result.error}")
        return ToolVerification(
            verified=True,
            details=f"Folder watcher active on {result.output.get('folder_path')} for {result.output.get('file_pattern')}."
        )


class WatchProcessTool(BaseTool):
    """Monitors a running process (e.g. GPU training, build script) and triggers alert on exit."""

    name = "watch_process"
    description = "Monitors a background process (e.g. GPU training, python script) and notifies the user immediately upon completion."
    risk_level = RiskLevel.LOW
    permission_level = PermissionLevel.LEVEL_0_READ

    parameters = {
        "process_name": ToolParameter(
            name="process_name",
            type="string",
            description="Name or pattern of the process to monitor (e.g. 'python.exe', '*train*', 'ffmpeg').",
            required=True,
        ),
        "target_objective": ToolParameter(
            name="target_objective",
            type="string",
            description="Notification or follow-up action to execute when process finishes.",
            required=False,
            default="",
        ),
        "pid": ToolParameter(
            name="pid",
            type="integer",
            description="Optional specific Process ID (PID) to track.",
            required=False,
            default=0,
        ),
    }

    def __init__(self, engine: Optional[ProactiveEngine] = None):
        super().__init__()
        self.engine = engine

    def _get_engine(self) -> Any:
        if self.engine is not None:
            return self.engine
        from jarvis.subsystems.proactive.engine import ProactiveEngine
        return ProactiveEngine.get_instance()

    def execute(self, process_name: str, target_objective: str = "", pid: int = 0, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        engine = self._get_engine()
        try:
            target_pid = pid if pid > 0 else None
            trigger = engine.watch_process(
                process_name_pattern=process_name,
                target_objective=target_objective or f"Notify user when {process_name} finishes",
                pid=target_pid,
            )
            output = {
                "trigger_id": trigger.trigger_id,
                "process_name": process_name,
                "target_pid": target_pid,
                "message": f"Actively monitoring process '{process_name}'. You will be notified immediately when it finishes.",
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
                error=f"Failed to start process monitor: {e}",
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        if not result.success:
            return ToolVerification(verified=False, details=f"Process monitor failed: {result.error}")
        return ToolVerification(
            verified=True,
            details=f"Process watcher registered for '{result.output.get('process_name')}'."
        )


class SendNotificationTool(BaseTool):
    """Sends a rich multi-channel notification (Windows toast, voice TTS, HUD)."""

    name = "send_notification"
    description = "Dispatches a notification across native Windows desktop toast, SAPI5 voice, and visual HUD."
    risk_level = RiskLevel.LOW
    permission_level = PermissionLevel.LEVEL_0_READ

    parameters = {
        "title": ToolParameter(
            name="title",
            type="string",
            description="Header or title of the notification.",
            required=True,
        ),
        "message": ToolParameter(
            name="message",
            type="string",
            description="Body message content.",
            required=True,
        ),
        "channel": ToolParameter(
            name="channel",
            type="string",
            description="Delivery channel: 'ALL', 'TOAST', 'VOICE', or 'HUD'. Default: 'ALL'.",
            required=False,
            default="ALL",
        ),
        "severity": ToolParameter(
            name="severity",
            type="string",
            description="Alert severity: 'INFO', 'SUCCESS', 'WARNING', 'ALERT'. Default: 'INFO'.",
            required=False,
            default="INFO",
        ),
    }

    def __init__(self, engine: Optional[ProactiveEngine] = None):
        super().__init__()
        self.engine = engine

    def _get_engine(self) -> Any:
        if self.engine is not None:
            return self.engine
        from jarvis.subsystems.proactive.engine import ProactiveEngine
        return ProactiveEngine.get_instance()

    def execute(self, title: str, message: str, channel: str = "ALL", severity: str = "INFO", **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        engine = self._get_engine()
        try:
            try:
                ch = NotificationChannel(channel.upper())
            except ValueError:
                ch = NotificationChannel.ALL

            notif = engine.notifier.notify(
                title=title,
                message=message,
                severity=severity.upper(),
                channel=ch,
            )
            output = {
                "notification_id": notif.notification_id,
                "title": notif.title,
                "message": notif.message,
                "channel": notif.channel.value,
                "delivered": notif.delivered,
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
                error=f"Failed to dispatch notification: {e}",
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        if not result.success:
            return ToolVerification(verified=False, details=f"Notification failed: {result.error}")
        return ToolVerification(
            verified=True,
            details=f"Notification delivered via {result.output.get('channel')}."
        )


class ListProactiveRulesTool(BaseTool):
    """Lists all active scheduled tasks, folder watchers, and process monitors."""

    name = "list_proactive_rules"
    description = "Lists all active scheduled tasks, environment watchers, and proactive trigger rules."
    risk_level = RiskLevel.LOW
    permission_level = PermissionLevel.LEVEL_0_READ
    parameters = {}

    def __init__(self, engine: Optional[ProactiveEngine] = None):
        super().__init__()
        self.engine = engine

    def _get_engine(self) -> Any:
        if self.engine is not None:
            return self.engine
        from jarvis.subsystems.proactive.engine import ProactiveEngine
        return ProactiveEngine.get_instance()

    def execute(self, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        engine = self._get_engine()
        try:
            triggers = engine.list_triggers(enabled_only=False)
            schedules = engine.scheduler.list_schedules(enabled_only=False)
            output = {
                "trigger_count": len(triggers),
                "schedule_count": len(schedules),
                "triggers": [t.to_dict() for t in triggers],
                "schedules": [s.to_dict() for s in schedules],
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
                error=f"Failed to list rules: {e}",
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        return ToolVerification(
            verified=result.success,
            details=f"Enumerated {result.output.get('trigger_count', 0)} triggers and {result.output.get('schedule_count', 0)} schedules." if result.success else result.error,
        )


class CancelProactiveRuleTool(BaseTool):
    """Cancels an active scheduled task or watcher."""

    name = "cancel_proactive_rule"
    description = "Cancels or deactivates an active scheduled task, folder watcher, or process monitor by ID."
    risk_level = RiskLevel.LOW
    permission_level = PermissionLevel.LEVEL_0_READ

    parameters = {
        "rule_id": ToolParameter(
            name="rule_id",
            type="string",
            description="The trigger_id or schedule_id to deactivate.",
            required=True,
        ),
    }

    def __init__(self, engine: Optional[ProactiveEngine] = None):
        super().__init__()
        self.engine = engine

    def _get_engine(self) -> Any:
        if self.engine is not None:
            return self.engine
        from jarvis.subsystems.proactive.engine import ProactiveEngine
        return ProactiveEngine.get_instance()

    def execute(self, rule_id: str, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        engine = self._get_engine()
        try:
            # Check if trigger ID or schedule ID
            deleted_trig = engine.cancel_trigger(rule_id)
            deleted_sched = engine.scheduler.cancel_schedule(rule_id)
            success = deleted_trig or deleted_sched
            msg = f"Rule '{rule_id}' cancelled successfully." if success else f"Rule '{rule_id}' not found."
            return ToolResult(
                success=success,
                output={"rule_id": rule_id, "message": msg},
                error=None if success else msg,
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=f"Failed to cancel rule: {e}",
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        return ToolVerification(
            verified=result.success,
            details=result.output.get("message") if result.success else result.error,
        )


class TriggerWorkflowTool(BaseTool):
    """Manually fires a proactive workflow for testing or immediate execution."""

    name = "trigger_proactive_workflow"
    description = "Manually triggers an event-driven proactive workflow for verification or immediate execution."
    risk_level = RiskLevel.LOW
    permission_level = PermissionLevel.LEVEL_0_READ

    parameters = {
        "trigger_id": ToolParameter(
            name="trigger_id",
            type="string",
            description="The trigger_id of the proactive rule to execute.",
            required=True,
        ),
        "event_data": ToolParameter(
            name="event_data",
            type="string",
            description="Optional JSON-encoded dictionary of event payload parameters.",
            required=False,
            default="{}",
        ),
    }

    def __init__(self, engine: Optional[ProactiveEngine] = None):
        super().__init__()
        self.engine = engine

    def _get_engine(self) -> Any:
        if self.engine is not None:
            return self.engine
        from jarvis.subsystems.proactive.engine import ProactiveEngine
        return ProactiveEngine.get_instance()

    def execute(self, trigger_id: str, event_data: str = "{}", **kwargs) -> ToolResult:
        import json
        start_t = time.perf_counter()
        engine = self._get_engine()
        try:
            trigger = engine.trigger_store.get_trigger(trigger_id)
            if not trigger:
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"Trigger ID '{trigger_id}' not found.",
                    duration_ms=(time.perf_counter() - start_t) * 1000,
                )

            payload = {}
            if event_data:
                try:
                    payload = json.loads(event_data)
                except Exception:
                    payload = {"raw": event_data}

            event = Event(
                event_type=trigger.condition.event_type,
                source="manual_tool_trigger",
                payload=payload,
            )
            run = engine.execute_proactive_workflow(trigger, event)
            output = {
                "run_id": run.run_id,
                "status": run.status.value,
                "verified": run.verified,
                "verification_details": run.verification_details,
                "notification_sent": run.notification_sent,
                "steps_executed": len(run.execution_records),
            }
            return ToolResult(
                success=run.status.value in ("SUCCESS", "COMPLETED"),
                output=output,
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=f"Execution error: {e}",
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        if not result.success:
            return ToolVerification(verified=False, details=f"Workflow failed: {result.error}")
        return ToolVerification(
            verified=True,
            details=f"Workflow completed: {result.output.get('steps_executed')} steps executed, verified={result.output.get('verified')}."
        )
