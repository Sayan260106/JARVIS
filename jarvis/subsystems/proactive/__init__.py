"""Phase 17 — Proactive JARVIS Subsystem.

Provides:
- ProactiveEngine (Event -> Condition -> JARVIS -> Plan -> Execute -> Verify -> Notify)
- ScheduleManager & NaturalScheduleParser
- FolderWatcher & ProcessWatcher
- NotificationDispatcher
- Event, Trigger, and Workflow schemas
"""

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
from jarvis.subsystems.proactive.scheduler import (
    NaturalScheduleParser,
    ScheduledTask,
    ScheduleManager,
    ScheduleStore,
)
from jarvis.subsystems.proactive.watchers import (
    FolderWatcher,
    ProcessWatcher,
)
from jarvis.subsystems.proactive.notifier import (
    NotificationDispatcher,
    NotificationStore,
)
from jarvis.subsystems.proactive.engine import (
    ProactiveEngine,
    TriggerStore,
)

__all__ = [
    "ConditionRule",
    "Event",
    "EventType",
    "FileEvent",
    "FolderWatcher",
    "NaturalScheduleParser",
    "NotificationChannel",
    "NotificationDispatcher",
    "NotificationMessage",
    "NotificationStore",
    "ProcessEvent",
    "ProcessWatcher",
    "ProactiveEngine",
    "ProactiveTrigger",
    "ScheduledTask",
    "ScheduleEvent",
    "ScheduleManager",
    "ScheduleStore",
    "TriggerStore",
    "WorkflowRun",
    "WorkflowStatus",
]
