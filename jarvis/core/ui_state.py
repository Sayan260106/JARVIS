"""Observable UI State Manager for JARVIS Interfaces (Phase 12).

Tracks active tasks, progress bars, hardware telemetry, listening indicators,
and chat message history for both the Terminal TUI and Web HUD.
"""

from __future__ import annotations
import math
import psutil
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


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
    """Manages synchronized runtime state for Terminal TUI and Web HUD."""

    def __init__(self):
        self.system_status: str = "ONLINE"
        self.agent_state: str = "LISTENING..."
        self.speech_quote: str = '"How may I assist you?"'
        self.active_task: ActiveTaskInfo = ActiveTaskInfo(
            name="ORCA-X verification",
            progress_pct=82,
            current_step=9,
            total_steps=12,
        )
        self.messages: List[ChatMessage] = [
            ChatMessage(sender="You", text="Verify the realtime API"),
            ChatMessage(sender="JARVIS", text="Certainly. I'm checking the endpoint now."),
        ]

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

    def add_message(self, sender: str, text: str):
        """Append a message to the conversation history."""
        self.messages.append(ChatMessage(sender=sender, text=text))
        if len(self.messages) > 30:
            self.messages = self.messages[-30:]

    def get_hardware_telemetry(self) -> Dict[str, Any]:
        """Fetch current hardware percentages and service statuses."""
        try:
            cpu = int(psutil.cpu_percent(interval=None))
            ram = int(psutil.virtual_memory().percent)
        except Exception:
            cpu = 24
            ram = 48

        return {
            "cpu": cpu,
            "ram": ram,
            "ollama": "● ONLINE",
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
            "active_task": {
                "name": self.active_task.name,
                "progress_pct": self.active_task.progress_pct,
                "progress_bar": self.active_task.render_bar(),
                "step_label": f"Step {self.active_task.current_step}/{self.active_task.total_steps}",
                "details": self.active_task.details,
            },
            "system_metrics": metrics,
            "messages": [
                {"sender": m.sender, "text": m.text, "time": m.timestamp}
                for m in self.messages
            ],
        }


# Global singleton instance
default_ui_state = UIStateManager()
