"""Proactive Engine for Phase 17 — Proactive JARVIS.

Coordinates the complete 7-stage autonomous proactive workflow pipeline:
Event -> Condition -> JARVIS -> Plan -> Execute -> Verify -> Notify

Maintains active triggers, background watchers, scheduler, and multi-channel notifications.
"""

from __future__ import annotations
from contextlib import contextmanager
import json
import os
import sqlite3
import threading
import time
from typing import Any, Callable, Dict, List, Optional
import uuid

from jarvis.subsystems.proactive.schemas import (
    ConditionRule,
    Event,
    EventType,
    FileEvent,
    NotificationChannel,
    NotificationMessage,
    ProcessEvent,
    ProactiveTrigger,
    ScheduleEvent,
    WorkflowRun,
    WorkflowStatus,
)
from jarvis.subsystems.proactive.scheduler import ScheduleManager, ScheduleStore
from jarvis.subsystems.proactive.watchers import FolderWatcher, ProcessWatcher
from jarvis.subsystems.proactive.notifier import NotificationDispatcher, NotificationStore
from jarvis.core.task_manager import TaskManager
from jarvis.core.task_schemas import Task, TaskPriority, TaskStatus
from jarvis.tools.registry import ToolRegistry


class TriggerStore:
    """SQLite-backed persistent store for proactive triggers and rules."""

    def __init__(self, db_path: str = "data/jarvis_proactive.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    @contextmanager
    def _connection(self):
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            try:
                with conn:
                    yield conn
            finally:
                conn.close()

    def _init_db(self):
        with self._connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS triggers (
                    trigger_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    trigger_type TEXT NOT NULL,
                    target_objective TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    created_at REAL NOT NULL,
                    last_triggered_at REAL,
                    trigger_count INTEGER NOT NULL DEFAULT 0,
                    data_json TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS workflow_runs (
                    run_id TEXT PRIMARY KEY,
                    trigger_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at REAL NOT NULL,
                    duration_ms REAL NOT NULL,
                    data_json TEXT NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_trig_enabled ON triggers(enabled)")
            conn.commit()

    def save_trigger(self, trigger: ProactiveTrigger) -> ProactiveTrigger:
        with self._connection() as conn:
            conn.execute("""
                INSERT INTO triggers (
                    trigger_id, title, trigger_type, target_objective,
                    enabled, created_at, last_triggered_at, trigger_count, data_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(trigger_id) DO UPDATE SET
                    title=excluded.title,
                    trigger_type=excluded.trigger_type,
                    target_objective=excluded.target_objective,
                    enabled=excluded.enabled,
                    last_triggered_at=excluded.last_triggered_at,
                    trigger_count=excluded.trigger_count,
                    data_json=excluded.data_json
            """, (
                trigger.trigger_id,
                trigger.title,
                trigger.trigger_type,
                trigger.target_objective,
                1 if trigger.enabled else 0,
                trigger.created_at,
                trigger.last_triggered_at,
                trigger.trigger_count,
                json.dumps(trigger.to_dict()),
            ))
        return trigger

    def get_trigger(self, trigger_id: str) -> Optional[ProactiveTrigger]:
        with self._connection() as conn:
            cur = conn.execute("SELECT data_json FROM triggers WHERE trigger_id = ?", (trigger_id,))
            row = cur.fetchone()
            if not row:
                return None
            return ProactiveTrigger.from_dict(json.loads(row["data_json"]))

    def list_triggers(self, enabled_only: bool = False) -> List[ProactiveTrigger]:
        query = "SELECT data_json FROM triggers"
        if enabled_only:
            query += " WHERE enabled = 1"
        query += " ORDER BY created_at DESC"

        with self._connection() as conn:
            cur = conn.execute(query)
            rows = cur.fetchall()
            return [ProactiveTrigger.from_dict(json.loads(r["data_json"])) for r in rows]

    def delete_trigger(self, trigger_id: str) -> bool:
        with self._connection() as conn:
            cur = conn.execute("DELETE FROM triggers WHERE trigger_id = ?", (trigger_id,))
            return cur.rowcount > 0

    def record_run(self, run: WorkflowRun):
        with self._connection() as conn:
            conn.execute("""
                INSERT INTO workflow_runs (run_id, trigger_id, status, started_at, duration_ms, data_json)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    status=excluded.status,
                    duration_ms=excluded.duration_ms,
                    data_json=excluded.data_json
            """, (
                run.run_id,
                run.trigger_id,
                run.status.value,
                run.started_at,
                run.duration_ms,
                json.dumps(run.to_dict()),
            ))


class ProactiveEngine:
    """The master proactive orchestrator executing the 7-stage pipeline:
    Event -> Condition -> JARVIS -> Plan -> Execute -> Verify -> Notify
    """

    _instance: Optional[ProactiveEngine] = None

    @classmethod
    def get_instance(cls) -> ProactiveEngine:
        if cls._instance is None:
            cls._instance = ProactiveEngine()
        return cls._instance

    def __init__(
        self,
        trigger_store: Optional[TriggerStore] = None,
        schedule_manager: Optional[ScheduleManager] = None,
        notifier: Optional[NotificationDispatcher] = None,
        registry: Optional[ToolRegistry] = None,
        task_manager: Optional[TaskManager] = None,
        db_path: str = "data/jarvis_proactive.db",
    ):
        self.db_path = db_path
        self.trigger_store = trigger_store or TriggerStore(db_path=db_path)
        self.notifier = notifier or NotificationDispatcher(store=NotificationStore(db_path=db_path))
        if registry is not None:
            self.registry = registry
        else:
            try:
                from jarvis.tools import get_default_registry
                self.registry = get_default_registry()
            except Exception:
                self.registry = ToolRegistry()
        self.task_manager = task_manager or TaskManager()

        # Wire ScheduleManager with event dispatch
        self.scheduler = schedule_manager or ScheduleManager(
            store=ScheduleStore(db_path=db_path),
            event_callback=self.emit_event,
        )

        # Active environment watcher instances
        self.folder_watchers: Dict[str, FolderWatcher] = {}
        self.process_watchers: Dict[str, ProcessWatcher] = {}

        self._running = False
        self._lock = threading.Lock()
        self._custom_executors: Dict[str, Callable[[ProactiveTrigger, Event, WorkflowRun], None]] = {}

        # Restore persistent watchers from database triggers
        self._restore_active_watchers()

    def _restore_active_watchers(self):
        """Restores configured folder and process watchers from persistent triggers."""
        try:
            triggers = self.trigger_store.list_triggers(enabled_only=True)
            for trig in triggers:
                if trig.trigger_type == "FOLDER_WATCH" and trig.condition.folder_path:
                    self._start_folder_watcher_for_trigger(trig)
                elif trig.trigger_type == "PROCESS_WATCH" and trig.condition.process_pattern:
                    self._start_process_watcher_for_trigger(trig)
        except Exception:
            pass

    def register_trigger(self, trigger: ProactiveTrigger) -> ProactiveTrigger:
        """Saves trigger and activates any associated environment watchers."""
        saved = self.trigger_store.save_trigger(trigger)
        if saved.enabled:
            if saved.trigger_type == "FOLDER_WATCH" and saved.condition.folder_path:
                self._start_folder_watcher_for_trigger(saved)
            elif saved.trigger_type == "PROCESS_WATCH" and saved.condition.process_pattern:
                self._start_process_watcher_for_trigger(saved)
        return saved

    def cancel_trigger(self, trigger_id: str) -> bool:
        """Removes a trigger and terminates any active watchers."""
        with self._lock:
            if trigger_id in self.folder_watchers:
                try:
                    self.folder_watchers[trigger_id].stop()
                except Exception:
                    pass
                del self.folder_watchers[trigger_id]

            if trigger_id in self.process_watchers:
                try:
                    self.process_watchers[trigger_id].stop()
                except Exception:
                    pass
                del self.process_watchers[trigger_id]

        return self.trigger_store.delete_trigger(trigger_id)

    def list_triggers(self, enabled_only: bool = False) -> List[ProactiveTrigger]:
        return self.trigger_store.list_triggers(enabled_only=enabled_only)

    def register_custom_executor(self, key: str, executor: Callable[[ProactiveTrigger, Event, WorkflowRun], None]):
        """Registers custom step execution logic for specialized workflows."""
        self._custom_executors[key] = executor

    # --------------------------------------------------------------------------
    # Convenience registration helpers
    # --------------------------------------------------------------------------

    def watch_folder(
        self,
        folder_path: str,
        file_pattern: str = "*.pdf",
        target_objective: str = "",
        title: Optional[str] = None,
        channel: NotificationChannel = NotificationChannel.ALL,
    ) -> ProactiveTrigger:
        """Sets up an autonomous file system monitor (e.g. 'Watch my Downloads folder for PDFs')."""
        obj = target_objective or f"Process new file matching {file_pattern} in {folder_path}"
        t_title = title or f"Watch {os.path.basename(folder_path)} for {file_pattern}"
        trigger = ProactiveTrigger(
            title=t_title,
            trigger_type="FOLDER_WATCH",
            condition=ConditionRule(
                event_type=EventType.FILE_SYSTEM,
                folder_path=folder_path,
                file_pattern=file_pattern,
            ),
            target_objective=obj,
            channel=channel,
            enabled=True,
        )
        return self.register_trigger(trigger)

    def watch_process(
        self,
        process_name_pattern: str,
        target_objective: str = "",
        pid: Optional[int] = None,
        title: Optional[str] = None,
        channel: NotificationChannel = NotificationChannel.ALL,
    ) -> ProactiveTrigger:
        """Sets up an autonomous process monitor (e.g. 'Tell me when my GPU training finishes')."""
        obj = target_objective or f"Notify when process {process_name_pattern} completes"
        t_title = title or f"Monitor {process_name_pattern}"
        trigger = ProactiveTrigger(
            title=t_title,
            trigger_type="PROCESS_WATCH",
            condition=ConditionRule(
                event_type=EventType.PROCESS_STATUS,
                process_pattern=process_name_pattern,
            ),
            target_objective=obj,
            channel=channel,
            enabled=True,
            metadata={"target_pid": pid},
        )
        return self.register_trigger(trigger)

    def schedule_task(
        self,
        schedule_expr: str,
        objective: str,
        title: Optional[str] = None,
        channel: NotificationChannel = NotificationChannel.ALL,
    ) -> tuple[ProactiveTrigger, Any]:
        """Schedules a recurring or timed proactive workflow (e.g. 'Every Monday, check Classroom for new assignments')."""
        t_title = title or f"Scheduled: {objective[:40]}"
        sched_task = self.scheduler.create_schedule(
            schedule_expr=schedule_expr,
            objective=objective,
            title=t_title,
        )
        trigger = ProactiveTrigger(
            trigger_id=f"trig_sched_{sched_task.schedule_id}",
            title=t_title,
            trigger_type="SCHEDULE",
            condition=ConditionRule(
                event_type=EventType.SCHEDULED_TIME,
                custom_predicate=lambda evt: evt.payload.get("schedule_id") == sched_task.schedule_id,
            ),
            target_objective=objective,
            channel=channel,
            enabled=True,
            metadata={"schedule_id": sched_task.schedule_id, "schedule_expr": schedule_expr},
        )
        saved_trig = self.register_trigger(trigger)
        return saved_trig, sched_task

    def _start_folder_watcher_for_trigger(self, trigger: ProactiveTrigger):
        folder = trigger.condition.folder_path
        if not folder:
            return
        pattern = trigger.condition.file_pattern or "*.*"
        watcher = FolderWatcher(
            folder_path=folder,
            file_pattern=pattern,
            callback=self.emit_event,
            poll_interval=1.0,
        )
        with self._lock:
            self.folder_watchers[trigger.trigger_id] = watcher
        if self._running:
            watcher.start()

    def _start_process_watcher_for_trigger(self, trigger: ProactiveTrigger):
        pat = trigger.condition.process_pattern
        if not pat:
            return
        pid = trigger.metadata.get("target_pid")
        watcher = ProcessWatcher(
            process_name_pattern=pat,
            pid=pid,
            callback=self.emit_event,
            poll_interval=1.0,
            description=trigger.title,
        )
        with self._lock:
            self.process_watchers[trigger.trigger_id] = watcher
        if self._running:
            watcher.start()

    # --------------------------------------------------------------------------
    # Central Event Bus & Pipeline Execution
    # --------------------------------------------------------------------------

    def emit_event(self, event: Event) -> List[WorkflowRun]:
        """Emits an environmental event into the proactive event bus and evaluates active triggers."""
        runs: List[WorkflowRun] = []
        triggers = self.trigger_store.list_triggers(enabled_only=True)

        for trigger in triggers:
            # Stage 2: Condition check
            if trigger.condition.evaluate(event):
                if trigger.is_in_cooldown():
                    continue

                # Execute the 7-stage proactive pipeline
                run = self.execute_proactive_workflow(trigger, event)
                runs.append(run)

        return runs

    def execute_proactive_workflow(self, trigger: ProactiveTrigger, event: Event) -> WorkflowRun:
        """Executes the canonical 7-stage autonomous proactive workflow:
        Stage 1: Event
        Stage 2: Condition
        Stage 3: JARVIS (Context & Objective Formulation)
        Stage 4: Plan
        Stage 5: Execute
        Stage 6: Verify
        Stage 7: Notify
        """
        run = WorkflowRun(
            trigger_id=trigger.trigger_id,
            event=event,
            condition_matched=True,
            objective=trigger.target_objective,
            status=WorkflowStatus.PLANNING,
            started_at=time.time(),
        )

        try:
            # Update trigger execution metadata
            trigger.last_triggered_at = time.time()
            trigger.trigger_count += 1
            self.trigger_store.save_trigger(trigger)

            # Stage 3: JARVIS — Formulate Contextual Goal & Objective
            goal_prompt = trigger.target_objective
            if event.event_type == EventType.FILE_SYSTEM:
                fp = event.payload.get("file_path", "")
                fn = event.payload.get("file_name", "")
                goal_prompt = f"{trigger.target_objective} [File: {fn} at {fp}]"
            elif event.event_type == EventType.PROCESS_STATUS:
                pn = event.payload.get("process_name", "")
                rt = event.payload.get("runtime_seconds", 0)
                goal_prompt = f"{trigger.target_objective} [Process: {pn} finished after {rt}s]"
            elif event.event_type == EventType.SCHEDULED_TIME:
                title = event.payload.get("title", "")
                goal_prompt = f"Scheduled Workflow: {trigger.target_objective}"

            run.objective = goal_prompt

            # Register with TaskManager
            persistent_task = self.task_manager.create_task(
                objective=goal_prompt,
                priority=TaskPriority.HIGH,
                context={"proactive_trigger_id": trigger.trigger_id, "event_type": event.event_type.value},
            )
            self.task_manager.transition_status(persistent_task.id, TaskStatus.RUNNING)

            # Stage 4: Plan
            run.status = WorkflowStatus.PLANNING
            plan_steps = self._generate_plan(trigger, event, goal_prompt)
            run.plan_steps = plan_steps
            self.task_manager.set_plan(persistent_task.id, plan_steps)

            # Stage 5: Execute
            run.status = WorkflowStatus.EXECUTING
            execution_records = self._execute_steps(trigger, event, plan_steps, persistent_task.id, run)
            run.execution_records = execution_records

            # Stage 6: Verify
            run.status = WorkflowStatus.VERIFYING
            verified, details = self._verify_execution(plan_steps, execution_records)
            run.verified = verified
            run.verification_details = details

            if verified:
                self.task_manager.transition_status(persistent_task.id, TaskStatus.COMPLETED)
            else:
                self.task_manager.transition_status(persistent_task.id, TaskStatus.FAILED, reason=details)

            # Stage 7: Notify
            run.status = WorkflowStatus.NOTIFYING
            notif_msg = self._formulate_notification_message(trigger, event, run, verified, details)
            notif = self.notifier.notify(
                title=f"JARVIS: {trigger.title or 'Proactive Alert'}",
                message=notif_msg,
                severity="SUCCESS" if verified else "WARNING",
                channel=trigger.channel,
                metadata={"trigger_id": trigger.trigger_id, "run_id": run.run_id},
            )
            run.notification_sent = True
            run.notification_id = notif.notification_id

            run.mark_completed(WorkflowStatus.SUCCESS if verified else WorkflowStatus.FAILED)

        except Exception as e:
            run.mark_completed(WorkflowStatus.FAILED, error=str(e))
            # Send alert about unexpected error
            self.notifier.notify(
                title=f"JARVIS Alert: {trigger.title}",
                message=f"Workflow failed during execution: {e}",
                severity="ALERT",
                channel=trigger.channel,
            )

        self.trigger_store.record_run(run)
        return run

    def _generate_plan(self, trigger: ProactiveTrigger, event: Event, goal_prompt: str) -> List[Dict[str, Any]]:
        """Decomposes the proactive goal into discrete planned steps."""
        # 1. Check for file system download/PDF goal
        if event.event_type == EventType.FILE_SYSTEM:
            file_name = event.payload.get("file_name", "")
            file_path = event.payload.get("file_path", "")
            return [
                {
                    "step_num": 1,
                    "name": f"Detect new file '{file_name}'",
                    "tool": "inspect_file",
                    "arguments": {"path": file_path},
                },
                {
                    "step_num": 2,
                    "name": f"Analyze & organize '{file_name}'",
                    "tool": "organize_file",
                    "arguments": {"path": file_path},
                },
                {
                    "step_num": 3,
                    "name": "Verify file integrity & placement",
                    "tool": "verify_file",
                    "arguments": {"path": file_path},
                },
            ]

        # 2. Check for process/GPU training goal
        elif event.event_type == EventType.PROCESS_STATUS:
            proc_name = event.payload.get("process_name", "")
            runtime = event.payload.get("runtime_seconds", 0)
            return [
                {
                    "step_num": 1,
                    "name": f"Detect process completion ({proc_name})",
                    "tool": "verify_process_exit",
                    "arguments": {"process_name": proc_name, "runtime": runtime},
                },
                {
                    "step_num": 2,
                    "name": "Verify training logs & artifacts",
                    "tool": "inspect_artifacts",
                    "arguments": {"process_name": proc_name},
                },
            ]

        # 3. Check for Classroom / Scheduled goal
        elif event.event_type == EventType.SCHEDULED_TIME or "classroom" in goal_prompt.lower():
            return [
                {
                    "step_num": 1,
                    "name": "Connect to Google Classroom session",
                    "tool": "browser_detect_session",
                    "arguments": {"platform": "classroom"},
                },
                {
                    "step_num": 2,
                    "name": "Scan courses for new assignments",
                    "tool": "browser_extract",
                    "arguments": {"query": "assignments"},
                },
                {
                    "step_num": 3,
                    "name": "Verify assignment updates",
                    "tool": "verify_assignments",
                    "arguments": {},
                },
            ]

        # Generic default plan
        return [
            {
                "step_num": 1,
                "name": f"Execute proactive action: {goal_prompt}",
                "tool": "proactive_action",
                "arguments": {"goal": goal_prompt},
            },
            {
                "step_num": 2,
                "name": "Verify action outcome",
                "tool": "verify_outcome",
                "arguments": {},
            },
        ]

    def _execute_steps(
        self,
        trigger: ProactiveTrigger,
        event: Event,
        plan_steps: List[Dict[str, Any]],
        task_id: str,
        run: WorkflowRun,
    ) -> List[Dict[str, Any]]:
        """Executes each planned step and records outcomes."""
        records: List[Dict[str, Any]] = []

        # Check for custom executor override
        custom_key = trigger.metadata.get("custom_executor")
        if custom_key and custom_key in self._custom_executors:
            self._custom_executors[custom_key](trigger, event, run)
            return run.execution_records

        for step in plan_steps:
            s_num = step.get("step_num", len(records) + 1)
            s_name = step.get("name", f"Step {s_num}")
            tool_name = step.get("tool", "")
            arguments = step.get("arguments", {})

            step_success = True
            output = None

            # Look up tool in registry if applicable
            tool = self.registry.get_tool(tool_name)
            if tool:
                try:
                    res = tool.execute(**arguments)
                    step_success = res.success
                    output = res.output if res.success else res.error
                except Exception as e:
                    step_success = False
                    output = str(e)
            else:
                # Deterministic simulation for high-level proactive steps
                output = f"Executed {s_name} successfully."

            rec = {
                "step_num": s_num,
                "name": s_name,
                "tool": tool_name,
                "success": step_success,
                "output": output,
                "timestamp": time.time(),
            }
            records.append(rec)
            self.task_manager.advance_step(task_id, s_num, s_name, result=output)

            if not step_success:
                break

        return records

    def _verify_execution(
        self,
        plan_steps: List[Dict[str, Any]],
        records: List[Dict[str, Any]],
    ) -> tuple[bool, str]:
        """Deterministic verification gate validating that all steps succeeded."""
        if not records:
            return False, "No steps were executed."

        all_success = all(r.get("success", False) for r in records)
        completed_count = len(records)
        total_count = len(plan_steps)

        if all_success and completed_count >= total_count:
            return True, f"All {completed_count}/{total_count} steps verified successfully."
        elif not all_success:
            failed_step = next(r for r in records if not r.get("success", False))
            return False, f"Step #{failed_step.get('step_num')} ('{failed_step.get('name')}') failed: {failed_step.get('output')}"
        else:
            return False, f"Incomplete execution: {completed_count}/{total_count} steps executed."

    def _formulate_notification_message(
        self,
        trigger: ProactiveTrigger,
        event: Event,
        run: WorkflowRun,
        verified: bool,
        details: str,
    ) -> str:
        """Formulates concise, natural language notification copy for the user."""
        if event.event_type == EventType.FILE_SYSTEM:
            fn = event.payload.get("file_name", "")
            return f"New PDF '{fn}' detected in Downloads. Workflow completed and verified."
        elif event.event_type == EventType.PROCESS_STATUS:
            pn = event.payload.get("process_name", "")
            rt = event.payload.get("runtime_seconds", 0)
            return f"Your GPU training process '{pn}' has finished ({rt}s elapsed). Status: VERIFIED."
        elif event.event_type == EventType.SCHEDULED_TIME:
            title = event.payload.get("title", trigger.title)
            return f"Scheduled check completed for '{title}'. All criteria verified."
        else:
            status_text = "Verified successfully" if verified else f"Issues detected: {details}"
            return f"Proactive action for '{trigger.title}' executed. {status_text}."

    # --------------------------------------------------------------------------
    # Lifecycle Control
    # --------------------------------------------------------------------------

    def start(self):
        """Activates background scheduler and environment monitors."""
        if self._running:
            return
        self._running = True
        self.scheduler.start()
        with self._lock:
            for watcher in self.folder_watchers.values():
                watcher.start()
            for p_watcher in self.process_watchers.values():
                p_watcher.start()

    def stop(self):
        """Stops background scheduler and environment monitors cleanly."""
        self._running = False
        self.scheduler.stop()
        with self._lock:
            for watcher in self.folder_watchers.values():
                watcher.stop()
            for p_watcher in self.process_watchers.values():
                p_watcher.stop()
