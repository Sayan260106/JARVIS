"""Scheduled Tasks Manager for Phase 17 — Proactive JARVIS.

Provides:
1. Natural language schedule expression parsing ("Every Monday", "Every day at 9:00 AM", "Every 15 minutes").
2. Cron parsing and next-run evaluation without external heavyweight dependencies.
3. Persistent SQLite task schedule repository (`data/jarvis_proactive.db`).
4. Thread-safe background ticker with zero busy-looping.
"""

from __future__ import annotations
from contextlib import contextmanager
from dataclasses import dataclass, field
import datetime
import json
import os
import re
import sqlite3
import threading
import time
from typing import Any, Callable, Dict, List, Optional
import uuid

from jarvis.subsystems.proactive.schemas import EventType, ScheduleEvent


DAY_NAMES = {
    "monday": 0, "mon": 0,
    "tuesday": 1, "tue": 1, "tues": 1,
    "wednesday": 2, "wed": 2,
    "thursday": 3, "thu": 3, "thur": 3, "thurs": 3,
    "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5,
    "sunday": 6, "sun": 6,
}


@dataclass
class ScheduledTask:
    """Persistent representation of a scheduled job."""
    schedule_id: str = field(default_factory=lambda: f"sched_{uuid.uuid4().hex[:10]}")
    title: str = ""
    schedule_expr: str = ""             # e.g. "Every Monday at 09:00" or "0 9 * * 1" or "interval:600"
    objective: str = ""                 # Objective to execute e.g. "Check Classroom for new assignments"
    target_tool: Optional[str] = None   # Optional specific tool target
    arguments: Dict[str, Any] = field(default_factory=dict)
    next_run: float = field(default_factory=time.time)
    last_run: Optional[float] = None
    enabled: bool = True
    run_count: int = 0
    created_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schedule_id": self.schedule_id,
            "title": self.title,
            "schedule_expr": self.schedule_expr,
            "objective": self.objective,
            "target_tool": self.target_tool,
            "arguments": self.arguments,
            "next_run": self.next_run,
            "last_run": self.last_run,
            "enabled": self.enabled,
            "run_count": self.run_count,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ScheduledTask:
        return cls(
            schedule_id=data.get("schedule_id", f"sched_{uuid.uuid4().hex[:10]}"),
            title=data.get("title", ""),
            schedule_expr=data.get("schedule_expr", ""),
            objective=data.get("objective", ""),
            target_tool=data.get("target_tool"),
            arguments=data.get("arguments", {}),
            next_run=float(data.get("next_run", time.time())),
            last_run=data.get("last_run"),
            enabled=data.get("enabled", True),
            run_count=int(data.get("run_count", 0)),
            created_at=float(data.get("created_at", time.time())),
            metadata=data.get("metadata", {}),
        )


class NaturalScheduleParser:
    """Parses natural language and cron expressions into deterministic next-run timestamps."""

    @classmethod
    def parse_time(cls, text: str) -> tuple[int, int]:
        """Extracts hour (0-23) and minute (0-59) from text like '9:00 AM', '14:30', '9am'."""
        text = text.lower().strip()
        m = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", text)
        if not m:
            return 9, 0  # Default to 9:00 AM if unspecified

        hour = int(m.group(1))
        minute = int(m.group(2)) if m.group(2) else 0
        ampm = m.group(3)

        if ampm == "pm" and hour < 12:
            hour += 12
        elif ampm == "am" and hour == 12:
            hour = 0

        return hour, minute

    @classmethod
    def calculate_next_run(cls, expression: str, reference_time: Optional[float] = None) -> float:
        """Calculates the UNIX timestamp of the next occurrence based on natural or cron expression."""
        ref = reference_time or time.time()
        dt_ref = datetime.datetime.fromtimestamp(ref)
        expr = expression.strip().lower()

        # 1. Interval expressions: "every X minutes", "every X seconds", "every X hours"
        interval_match = re.search(r"every\s+(\d+)?\s*(second|sec|minute|min|hour|hr)s?", expr)
        if interval_match:
            count = int(interval_match.group(1) or 1)
            unit = interval_match.group(2)
            if unit in ("second", "sec"):
                delta_sec = count
            elif unit in ("minute", "min"):
                delta_sec = count * 60
            elif unit in ("hour", "hr"):
                delta_sec = count * 3600
            else:
                delta_sec = 60
            return ref + delta_sec

        # Explicit interval format: "interval:300"
        if expr.startswith("interval:"):
            try:
                delta_sec = float(expr.split(":")[1])
                return ref + delta_sec
            except Exception:
                return ref + 60.0

        # 2. Weekday recurrence: "every Monday", "every weekday at 9am"
        # Check for specific days
        matched_day = None
        for day_name, day_idx in DAY_NAMES.items():
            if re.search(rf"\b{day_name}\b", expr):
                matched_day = day_idx
                break

        if matched_day is not None:
            hour, minute = cls.parse_time(expr)
            # Find next date with this weekday
            target_date = dt_ref.date()
            days_ahead = (matched_day - target_date.weekday()) % 7
            target_dt = datetime.datetime.combine(
                target_date + datetime.timedelta(days=days_ahead),
                datetime.time(hour=hour, minute=minute)
            )
            # If target time is today but has already passed, schedule for next week
            if target_dt <= dt_ref:
                target_dt += datetime.timedelta(days=7)
            return target_dt.timestamp()

        # "Every weekday" (Mon-Fri)
        if "weekday" in expr:
            hour, minute = cls.parse_time(expr)
            curr = dt_ref
            while True:
                curr = curr + datetime.timedelta(days=1)
                if curr.weekday() < 5:  # Monday to Friday
                    target_dt = datetime.datetime.combine(
                        curr.date(),
                        datetime.time(hour=hour, minute=minute)
                    )
                    return target_dt.timestamp()

        # 3. Daily recurrence: "every day at 9:00", "daily at 18:00", "every morning"
        if "day" in expr or "daily" in expr or "morning" in expr or "evening" in expr or "night" in expr:
            hour, minute = cls.parse_time(expr)
            target_dt = datetime.datetime.combine(
                dt_ref.date(),
                datetime.time(hour=hour, minute=minute)
            )
            if target_dt <= dt_ref:
                target_dt += datetime.timedelta(days=1)
            return target_dt.timestamp()

        # 4. Standard 5-part cron syntax: "minute hour dom month dow"
        parts = expr.split()
        if len(parts) == 5:
            # Simple cron evaluation: minute, hour, day of week
            try:
                min_part, hr_part, _, _, dow_part = parts
                target_minute = 0 if min_part == "*" else int(min_part)
                target_hour = 9 if hr_part == "*" else int(hr_part)

                target_dow = None
                if dow_part != "*":
                    target_dow = int(dow_part) % 7

                if target_dow is not None:
                    target_date = dt_ref.date()
                    days_ahead = (target_dow - target_date.weekday()) % 7
                    target_dt = datetime.datetime.combine(
                        target_date + datetime.timedelta(days=days_ahead),
                        datetime.time(hour=target_hour, minute=target_minute)
                    )
                    if target_dt <= dt_ref:
                        target_dt += datetime.timedelta(days=7)
                    return target_dt.timestamp()
                else:
                    target_dt = datetime.datetime.combine(
                        dt_ref.date(),
                        datetime.time(hour=target_hour, minute=target_minute)
                    )
                    if target_dt <= dt_ref:
                        target_dt += datetime.timedelta(days=1)
                    return target_dt.timestamp()
            except Exception:
                pass

        # Fallback default: 1 hour from reference
        return ref + 3600.0


class ScheduleStore:
    """SQLite-backed persistent store for scheduled tasks."""

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
                CREATE TABLE IF NOT EXISTS schedules (
                    schedule_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    schedule_expr TEXT NOT NULL,
                    objective TEXT NOT NULL,
                    target_tool TEXT,
                    next_run REAL NOT NULL,
                    last_run REAL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    run_count INTEGER NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL,
                    data_json TEXT NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sched_next ON schedules(enabled, next_run)")
            conn.commit()

    def save(self, task: ScheduledTask) -> ScheduledTask:
        with self._connection() as conn:
            conn.execute("""
                INSERT INTO schedules (
                    schedule_id, title, schedule_expr, objective, target_tool,
                    next_run, last_run, enabled, run_count, created_at, data_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(schedule_id) DO UPDATE SET
                    title=excluded.title,
                    schedule_expr=excluded.schedule_expr,
                    objective=excluded.objective,
                    target_tool=excluded.target_tool,
                    next_run=excluded.next_run,
                    last_run=excluded.last_run,
                    enabled=excluded.enabled,
                    run_count=excluded.run_count,
                    data_json=excluded.data_json
            """, (
                task.schedule_id,
                task.title,
                task.schedule_expr,
                task.objective,
                task.target_tool,
                task.next_run,
                task.last_run,
                1 if task.enabled else 0,
                task.run_count,
                task.created_at,
                json.dumps(task.to_dict()),
            ))
        return task

    def get(self, schedule_id: str) -> Optional[ScheduledTask]:
        with self._connection() as conn:
            cur = conn.execute("SELECT data_json FROM schedules WHERE schedule_id = ?", (schedule_id,))
            row = cur.fetchone()
            if not row:
                return None
            return ScheduledTask.from_dict(json.loads(row["data_json"]))

    def list_all(self, enabled_only: bool = False) -> List[ScheduledTask]:
        query = "SELECT data_json FROM schedules"
        if enabled_only:
            query += " WHERE enabled = 1"
        query += " ORDER BY next_run ASC"

        with self._connection() as conn:
            cur = conn.execute(query)
            rows = cur.fetchall()
            return [ScheduledTask.from_dict(json.loads(r["data_json"])) for r in rows]

    def delete(self, schedule_id: str) -> bool:
        with self._connection() as conn:
            cur = conn.execute("DELETE FROM schedules WHERE schedule_id = ?", (schedule_id,))
            return cur.rowcount > 0


class ScheduleManager:
    """Coordinates scheduled task registration, background evaluation, and event dispatching."""

    def __init__(
        self,
        store: Optional[ScheduleStore] = None,
        event_callback: Optional[Callable[[ScheduleEvent], None]] = None,
        poll_interval: float = 1.0,
    ):
        self.store = store or ScheduleStore()
        self.event_callback = event_callback
        self.poll_interval = poll_interval
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def create_schedule(
        self,
        schedule_expr: str,
        objective: str,
        title: Optional[str] = None,
        target_tool: Optional[str] = None,
        arguments: Optional[Dict[str, Any]] = None,
    ) -> ScheduledTask:
        """Parses schedule expression, computes initial next_run, and stores persistently."""
        next_run = NaturalScheduleParser.calculate_next_run(schedule_expr)
        task_title = title or objective[:50]
        task = ScheduledTask(
            title=task_title,
            schedule_expr=schedule_expr,
            objective=objective,
            target_tool=target_tool,
            arguments=arguments or {},
            next_run=next_run,
            enabled=True,
        )
        return self.store.save(task)

    def cancel_schedule(self, schedule_id: str) -> bool:
        """Removes a scheduled task."""
        return self.store.delete(schedule_id)

    def list_schedules(self, enabled_only: bool = False) -> List[ScheduledTask]:
        """Lists tracked schedules."""
        return self.store.list_all(enabled_only=enabled_only)

    def start(self):
        """Starts background ticker thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, name="JARVIS-ScheduleTicker", daemon=True)
        self._thread.start()

    def stop(self):
        """Stops background ticker thread."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def _run_loop(self):
        """Periodic background evaluation checking for due schedules."""
        while self._running:
            try:
                self.check_due_schedules()
            except Exception:
                pass
            time.sleep(self.poll_interval)

    def check_due_schedules(self, current_time: Optional[float] = None) -> List[ScheduleEvent]:
        """Checks and triggers any due scheduled tasks."""
        now = current_time or time.time()
        due_events: List[ScheduleEvent] = []
        tasks = self.store.list_all(enabled_only=True)

        for task in tasks:
            if task.next_run <= now:
                # Trigger schedule
                evt = ScheduleEvent(
                    source="scheduler",
                    payload={
                        "schedule_id": task.schedule_id,
                        "title": task.title,
                        "objective": task.objective,
                        "schedule_expr": task.schedule_expr,
                        "target_tool": task.target_tool,
                        "arguments": task.arguments,
                    }
                )
                due_events.append(evt)

                # Update task state and calculate subsequent next_run
                task.last_run = now
                task.run_count += 1
                task.next_run = NaturalScheduleParser.calculate_next_run(task.schedule_expr, reference_time=now)
                self.store.save(task)

                if self.event_callback:
                    try:
                        self.event_callback(evt)
                    except Exception:
                        pass

        return due_events
