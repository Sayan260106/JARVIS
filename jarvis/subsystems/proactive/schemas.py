"""Data schemas and contracts for Phase 17 — Proactive JARVIS.

Defines:
1. Event models (Scheduled, File System, Process, Telemetry, Manual).
2. Condition rules and predicate evaluation.
3. Proactive triggers and workflows.
4. Telemetry records for Event -> Condition -> JARVIS -> Plan -> Execute -> Verify -> Notify.
5. Multi-channel notification payloads.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
import fnmatch
import os
import time
from typing import Any, Callable, Dict, List, Optional
import uuid


class EventType(str, Enum):
    """Categorization of environmental and system events."""
    SCHEDULED_TIME = "SCHEDULED_TIME"
    FILE_SYSTEM = "FILE_SYSTEM"
    PROCESS_STATUS = "PROCESS_STATUS"
    SYSTEM_METRIC = "SYSTEM_METRIC"
    WEB_POLL = "WEB_POLL"
    MANUAL_TRIGGER = "MANUAL_TRIGGER"


class NotificationChannel(str, Enum):
    """Supported channels for proactive alerts."""
    TOAST = "TOAST"
    VOICE = "VOICE"
    HUD = "HUD"
    ALL = "ALL"


class WorkflowStatus(str, Enum):
    """Execution status for proactive workflow runs."""
    PENDING = "PENDING"
    EVALUATING = "EVALUATING"
    PLANNING = "PLANNING"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    NOTIFYING = "NOTIFYING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


@dataclass
class Event:
    """Base event contract emitted into the proactive event bus."""
    event_id: str = field(default_factory=lambda: f"evt_{uuid.uuid4().hex[:10]}")
    event_type: EventType = EventType.MANUAL_TRIGGER
    timestamp: float = field(default_factory=time.time)
    source: str = "system"
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp,
            "source": self.source,
            "payload": self.payload,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Event:
        evt_type = EventType(data.get("event_type", EventType.MANUAL_TRIGGER.value))
        return cls(
            event_id=data.get("event_id", f"evt_{uuid.uuid4().hex[:10]}"),
            event_type=evt_type,
            timestamp=data.get("timestamp", time.time()),
            source=data.get("source", "system"),
            payload=data.get("payload", {}),
        )


@dataclass
class FileEvent(Event):
    """Emitted when a file system change is observed."""
    event_type: EventType = EventType.FILE_SYSTEM

    @property
    def file_path(self) -> str:
        return self.payload.get("file_path", "")

    @property
    def file_name(self) -> str:
        return self.payload.get("file_name", os.path.basename(self.file_path))

    @property
    def action(self) -> str:
        return self.payload.get("action", "created")  # created, modified, deleted

    @property
    def extension(self) -> str:
        return self.payload.get("extension", os.path.splitext(self.file_name)[1].lower())


@dataclass
class ProcessEvent(Event):
    """Emitted when a monitored process starts, terminates, or crashes."""
    event_type: EventType = EventType.PROCESS_STATUS

    @property
    def process_name(self) -> str:
        return self.payload.get("process_name", "")

    @property
    def pid(self) -> Optional[int]:
        return self.payload.get("pid")

    @property
    def status(self) -> str:
        return self.payload.get("status", "finished")  # started, finished, crashed

    @property
    def exit_code(self) -> Optional[int]:
        return self.payload.get("exit_code")

    @property
    def runtime_seconds(self) -> float:
        return float(self.payload.get("runtime_seconds", 0.0))


@dataclass
class ScheduleEvent(Event):
    """Emitted when a recurring or one-off schedule timer fires."""
    event_type: EventType = EventType.SCHEDULED_TIME

    @property
    def schedule_id(self) -> str:
        return self.payload.get("schedule_id", "")

    @property
    def schedule_title(self) -> str:
        return self.payload.get("title", "")


@dataclass
class NotificationMessage:
    """Standardized multi-channel notification payload."""
    notification_id: str = field(default_factory=lambda: f"notif_{uuid.uuid4().hex[:10]}")
    title: str = "JARVIS Alert"
    message: str = ""
    severity: str = "INFO"  # INFO, SUCCESS, WARNING, ALERT
    channel: NotificationChannel = NotificationChannel.ALL
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    delivered: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "notification_id": self.notification_id,
            "title": self.title,
            "message": self.message,
            "severity": self.severity,
            "channel": self.channel.value,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
            "delivered": self.delivered,
        }


@dataclass
class ConditionRule:
    """Predicate condition evaluated on incoming events."""
    event_type: EventType
    file_pattern: Optional[str] = None       # e.g. "*.pdf", "*.zip"
    folder_path: Optional[str] = None        # e.g. "Downloads", "C:/Users/.../Downloads"
    process_pattern: Optional[str] = None    # e.g. "*train*", "python.exe"
    exit_code: Optional[int] = None          # e.g. 0
    metric_name: Optional[str] = None        # e.g. "gpu_memory_used_mb", "cpu_percent"
    metric_threshold: Optional[float] = None
    metric_operator: str = "<="              # "<=", ">=", "==", "<", ">"
    custom_predicate: Optional[Callable[[Event], bool]] = None

    def evaluate(self, event: Event) -> bool:
        """Determines if the event matches the condition criteria."""
        if event.event_type != self.event_type:
            return False

        # 1. File System conditions
        if self.event_type == EventType.FILE_SYSTEM:
            path = event.payload.get("file_path", "")
            filename = os.path.basename(path)
            if self.folder_path:
                norm_watch_folder = os.path.normcase(os.path.abspath(self.folder_path))
                norm_event_folder = os.path.normcase(os.path.abspath(os.path.dirname(path)))
                # Check direct or subfolder match
                if not (norm_event_folder == norm_watch_folder or norm_event_folder.startswith(norm_watch_folder + os.sep)):
                    return False
            if self.file_pattern:
                if not fnmatch.fnmatch(filename.lower(), self.file_pattern.lower()):
                    return False

        # 2. Process conditions
        elif self.event_type == EventType.PROCESS_STATUS:
            pname = event.payload.get("process_name", "")
            if self.process_pattern:
                if not fnmatch.fnmatch(pname.lower(), self.process_pattern.lower()):
                    return False
            if self.exit_code is not None:
                if event.payload.get("exit_code") != self.exit_code:
                    return False

        # 3. Metric conditions
        elif self.event_type == EventType.SYSTEM_METRIC:
            mname = event.payload.get("metric_name", "")
            if self.metric_name and mname.lower() != self.metric_name.lower():
                return False
            if self.metric_threshold is not None:
                val = float(event.payload.get("value", 0.0))
                thresh = self.metric_threshold
                op = self.metric_operator
                if op == "<=" and not (val <= thresh): return False
                elif op == ">=" and not (val >= thresh): return False
                elif op == "==" and not (val == thresh): return False
                elif op == "<" and not (val < thresh): return False
                elif op == ">" and not (val > thresh): return False

        # 4. Custom predicate if provided
        if self.custom_predicate:
            try:
                if not self.custom_predicate(event):
                    return False
            except Exception:
                return False

        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type.value,
            "file_pattern": self.file_pattern,
            "folder_path": self.folder_path,
            "process_pattern": self.process_pattern,
            "exit_code": self.exit_code,
            "metric_name": self.metric_name,
            "metric_threshold": self.metric_threshold,
            "metric_operator": self.metric_operator,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ConditionRule:
        evt_type = EventType(data.get("event_type", EventType.FILE_SYSTEM.value))
        return cls(
            event_type=evt_type,
            file_pattern=data.get("file_pattern"),
            folder_path=data.get("folder_path"),
            process_pattern=data.get("process_pattern"),
            exit_code=data.get("exit_code"),
            metric_name=data.get("metric_name"),
            metric_threshold=data.get("metric_threshold"),
            metric_operator=data.get("metric_operator", "<="),
        )


@dataclass
class ProactiveTrigger:
    """Specification of an active proactive rule linking Event/Condition to JARVIS workflow."""
    trigger_id: str = field(default_factory=lambda: f"trig_{uuid.uuid4().hex[:10]}")
    title: str = ""
    description: str = ""
    trigger_type: str = "GENERIC"  # SCHEDULE, FOLDER_WATCH, PROCESS_WATCH, METRIC_WATCH
    condition: ConditionRule = field(default_factory=lambda: ConditionRule(event_type=EventType.MANUAL_TRIGGER))
    target_objective: str = ""     # Prompt/objective dispatched to JARVIS upon condition match
    channel: NotificationChannel = NotificationChannel.ALL
    enabled: bool = True
    cooldown_seconds: float = 5.0  # Debounce trigger storm
    created_at: float = field(default_factory=time.time)
    last_triggered_at: Optional[float] = None
    trigger_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_in_cooldown(self, now: Optional[float] = None) -> bool:
        """Check if trigger was executed too recently."""
        if self.last_triggered_at is None:
            return False
        current = now or time.time()
        return (current - self.last_triggered_at) < self.cooldown_seconds

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trigger_id": self.trigger_id,
            "title": self.title,
            "description": self.description,
            "trigger_type": self.trigger_type,
            "condition": self.condition.to_dict(),
            "target_objective": self.target_objective,
            "channel": self.channel.value,
            "enabled": self.enabled,
            "cooldown_seconds": self.cooldown_seconds,
            "created_at": self.created_at,
            "last_triggered_at": self.last_triggered_at,
            "trigger_count": self.trigger_count,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ProactiveTrigger:
        channel_val = data.get("channel", NotificationChannel.ALL.value)
        try:
            channel = NotificationChannel(channel_val)
        except ValueError:
            channel = NotificationChannel.ALL

        cond_data = data.get("condition", {})
        condition = ConditionRule.from_dict(cond_data) if cond_data else ConditionRule(event_type=EventType.MANUAL_TRIGGER)

        return cls(
            trigger_id=data.get("trigger_id", f"trig_{uuid.uuid4().hex[:10]}"),
            title=data.get("title", ""),
            description=data.get("description", ""),
            trigger_type=data.get("trigger_type", "GENERIC"),
            condition=condition,
            target_objective=data.get("target_objective", ""),
            channel=channel,
            enabled=data.get("enabled", True),
            cooldown_seconds=float(data.get("cooldown_seconds", 5.0)),
            created_at=float(data.get("created_at", time.time())),
            last_triggered_at=data.get("last_triggered_at"),
            trigger_count=int(data.get("trigger_count", 0)),
            metadata=data.get("metadata", {}),
        )


@dataclass
class WorkflowRun:
    """Detailed telemetry record tracking an event through the 7-stage pipeline:
    Event -> Condition -> JARVIS -> Plan -> Execute -> Verify -> Notify
    """
    run_id: str = field(default_factory=lambda: f"run_{uuid.uuid4().hex[:10]}")
    trigger_id: str = ""
    event: Optional[Event] = None
    condition_matched: bool = False
    objective: str = ""
    plan_steps: List[Dict[str, Any]] = field(default_factory=list)
    execution_results: List[Dict[str, Any]] = field(default_factory=list)
    verified: bool = False
    verification_details: str = ""
    notification_sent: bool = False
    notification_id: Optional[str] = None
    status: WorkflowStatus = WorkflowStatus.PENDING
    started_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    duration_ms: float = 0.0
    error: Optional[str] = None

    @property
    def execution_records(self) -> List[Dict[str, Any]]:
        return self.execution_results

    @execution_records.setter
    def execution_records(self, val: List[Dict[str, Any]]):
        self.execution_results = val

    def mark_completed(self, status: WorkflowStatus, error: Optional[str] = None):
        self.completed_at = time.time()
        self.status = status
        self.duration_ms = (self.completed_at - self.started_at) * 1000.0
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "trigger_id": self.trigger_id,
            "event": self.event.to_dict() if self.event else None,
            "condition_matched": self.condition_matched,
            "objective": self.objective,
            "plan_steps": self.plan_steps,
            "execution_results": self.execution_results,
            "verified": self.verified,
            "verification_details": self.verification_details,
            "notification_sent": self.notification_sent,
            "notification_id": self.notification_id,
            "status": self.status.value,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_ms": self.duration_ms,
            "error": self.error,
        }
