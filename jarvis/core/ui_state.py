"""Observable UI State Manager for JARVIS Interfaces (Phase 12 & Phase 16).

Tracks active tasks, granular step checklists, progress bars, hardware telemetry,
listening indicators, and chat message history for Native Desktop GUI, Terminal TUI, and Web HUD.
"""

from __future__ import annotations
from enum import Enum
import math
import psutil
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class StepStatus(str, Enum):
    """Execution status for granular plan checklist steps."""
    COMPLETED = "COMPLETED"     # ✓ Finished successfully
    IN_PROGRESS = "IN_PROGRESS" # ● Currently executing
    PENDING = "PENDING"         # ○ Queued for execution
    FAILED = "FAILED"           # ✗ Failed execution


@dataclass
class StepItem:
    """Individual item in a live task execution plan."""
    label: str
    status: StepStatus = StepStatus.PENDING
    timestamp: float = field(default_factory=time.time)

    def icon(self) -> str:
        if self.status == StepStatus.COMPLETED:
            return "✓"
        elif self.status == StepStatus.IN_PROGRESS:
            return "●"
        elif self.status == StepStatus.FAILED:
            return "✗"
        return "○"

    def render_line(self) -> str:
        return f"{self.icon()} {self.label}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "label": self.label,
            "status": self.status.value,
            "icon": self.icon(),
            "time": self.timestamp,
        }


@dataclass
class ChatMessage:
    sender: str
    text: str
    timestamp: float = field(default_factory=time.time)


@dataclass
class ActiveTaskInfo:
    name: str = "Idle"
    progress_pct: int = 0
    current_step: int = 0
    total_steps: int = 0
    details: str = ""

    def render_bar(self, width: int = 16) -> str:
        """Render a graphical progress bar e.g. ████████████░░ 82%."""
        filled = int((self.progress_pct / 100.0) * width)
        bar = "█" * filled + "░" * (width - filled)
        return f"{bar} {self.progress_pct}%"


class UIStateManager:
    """Manages synchronized runtime state for Native GUI, Terminal TUI, and Web HUD."""

    def __init__(self):
        self.system_status: str = "ONLINE"
        self.agent_state: str = "LISTENING..."
        self.speech_quote: str = '"How may I assist you?"'
        self.active_task_count: int = 1
        self.ollama_status: str = "● ONLINE"

        self.active_task: ActiveTaskInfo = ActiveTaskInfo(
            name="ORCA-X verification",
            progress_pct=82,
            current_step=9,
            total_steps=12,
            details="Verifying realtime API...",
        )

        # Live step checklist matching Phase 16 design
        self.task_steps: List[StepItem] = [
            StepItem(label="Chrome opened", status=StepStatus.COMPLETED),
            StepItem(label="Classroom opened", status=StepStatus.COMPLETED),
            StepItem(label="ECE course found", status=StepStatus.COMPLETED),
            StepItem(label="Lecture PDF found", status=StepStatus.COMPLETED),
            StepItem(label="Downloading...", status=StepStatus.IN_PROGRESS),
        ]

        self.messages: List[ChatMessage] = [
            ChatMessage(sender="You", text="Verify the realtime API"),
            ChatMessage(sender="JARVIS", text="Certainly. I'm checking the endpoint now."),
        ]
        # Phase 17 Proactive State
        self.active_monitors: List[str] = ["Downloads (*.pdf)"]
        self.scheduled_tasks: List[str] = ["Every Monday: Classroom scan"]
        self.recent_notifications: List[Dict[str, Any]] = []

    def set_agent_state(self, state: str, quote: Optional[str] = None):
        """Update listening/thinking status and displayed speech quote."""
        self.agent_state = state
        if quote:
            self.speech_quote = f'"{quote.strip()}"'

    def update_task(self, name: str, current_step: int, total_steps: int, details: str = ""):
        """Update the active task progress."""
        pct = int((current_step / max(total_steps, 1)) * 100)
        self.active_task = ActiveTaskInfo(
            name=name,
            progress_pct=min(pct, 100),
            current_step=current_step,
            total_steps=total_steps,
            details=details,
        )

    def set_steps(self, steps: List[Any]):
        """Replace current step checklist."""
        converted = []
        for s in steps:
            if isinstance(s, StepItem):
                converted.append(s)
            elif isinstance(s, dict):
                label = s.get("label", "")
                st = s.get("status", "PENDING")
                st_enum = StepStatus[st] if st in StepStatus.__members__ else StepStatus.PENDING
                converted.append(StepItem(label=label, status=st_enum))
            elif isinstance(s, str):
                converted.append(StepItem(label=s, status=StepStatus.PENDING))
        self.task_steps = converted

    def add_step(self, label: str, status: StepStatus | str = StepStatus.IN_PROGRESS):
        """Append a new step to the checklist."""
        st_enum = status if isinstance(status, StepStatus) else (
            StepStatus[status] if status in StepStatus.__members__ else StepStatus.IN_PROGRESS
        )
        self.task_steps.append(StepItem(label=label, status=st_enum))

    def update_step(self, index: int, status: StepStatus | str, label: Optional[str] = None):
        """Update an existing step by index."""
        if 0 <= index < len(self.task_steps):
            st_enum = status if isinstance(status, StepStatus) else (
                StepStatus[status] if status in StepStatus.__members__ else StepStatus.COMPLETED
            )
            self.task_steps[index].status = st_enum
            if label:
                self.task_steps[index].label = label

    def clear_steps(self):
        """Clear the task step checklist."""
        self.task_steps.clear()

    def add_message(self, sender: str, text: str):
        """Append a message to the conversation history."""
        self.messages.append(ChatMessage(sender=sender, text=text))
        if len(self.messages) > 30:
            self.messages = self.messages[-30:]

    def add_notification(self, title: str, message: str, severity: str = "INFO"):
        """Append a proactive notification to the HUD state."""
        notif = {
            "title": title,
            "message": message,
            "severity": severity,
            "time": time.time(),
        }
        self.recent_notifications.append(notif)
        if len(self.recent_notifications) > 20:
            self.recent_notifications = self.recent_notifications[-20:]

    def get_hardware_telemetry(self) -> Dict[str, Any]:
        """Fetch current hardware percentages and service statuses."""
        try:
            cpu = int(psutil.cpu_percent(interval=None))
            ram = int(psutil.virtual_memory().percent)
        except Exception:
            cpu = 31
            ram = 48

        return {
            "cpu": cpu,
            "ram": ram,
            "tasks": self.active_task_count,
            "ollama": self.ollama_status,
            "browser": "● READY",
            "network": "● ONLINE",
        }

    def to_dict(self) -> Dict[str, Any]:
        """Export state representation for JSON APIs and Dashboards."""
        metrics = self.get_hardware_telemetry()
        return {
            "system_status": self.system_status,
            "agent_state": self.agent_state,
            "speech_quote": self.speech_quote,
            "active_task_count": self.active_task_count,
            "active_task": {
                "name": self.active_task.name,
                "progress_pct": self.active_task.progress_pct,
                "progress_bar": self.active_task.render_bar(),
                "step_label": f"Step {self.active_task.current_step}/{self.active_task.total_steps}",
                "details": self.active_task.details,
            },
            "task_steps": [s.to_dict() for s in self.task_steps],
            "active_monitors": self.active_monitors,
            "scheduled_tasks": self.scheduled_tasks,
            "recent_notifications": self.recent_notifications,
            "system_metrics": metrics,
            "messages": [
                {"sender": m.sender, "text": m.text, "time": m.timestamp}
                for m in self.messages
            ],
        }


# Global singleton instance
default_ui_state = UIStateManager()
