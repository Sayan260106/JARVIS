"""Multi-Channel Notification Dispatcher for Phase 17 — Proactive JARVIS.

Supports:
1. Native Windows Desktop Notifications (PowerShell Burp / Toast).
2. Local Voice Audio Notifications (SAPI5 via LocalTTS).
3. Real-time UI HUD alerts (Desktop GUI & Web HUD synchronization).
4. Persistent SQLite notification history (`data/jarvis_proactive.db`).
"""

from __future__ import annotations
from contextlib import contextmanager
import json
import os
import sqlite3
import subprocess
import threading
import time
from typing import Any, Dict, List, Optional

from jarvis.subsystems.proactive.schemas import NotificationChannel, NotificationMessage
from jarvis.core.ui_state import UIStateManager, default_ui_state


class NotificationStore:
    """SQLite repository for delivered and unread notifications."""

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
                CREATE TABLE IF NOT EXISTS notifications (
                    notification_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    message TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    delivered INTEGER NOT NULL DEFAULT 1,
                    read INTEGER NOT NULL DEFAULT 0,
                    data_json TEXT NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_notif_time ON notifications(timestamp DESC)")
            conn.commit()

    def record(self, notif: NotificationMessage) -> NotificationMessage:
        with self._connection() as conn:
            conn.execute("""
                INSERT INTO notifications (
                    notification_id, title, message, severity, channel,
                    timestamp, delivered, read, data_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)
                ON CONFLICT(notification_id) DO UPDATE SET
                    delivered=excluded.delivered,
                    data_json=excluded.data_json
            """, (
                notif.notification_id,
                notif.title,
                notif.message,
                notif.severity,
                notif.channel.value,
                notif.timestamp,
                1 if notif.delivered else 0,
                json.dumps(notif.to_dict()),
            ))
        return notif

    def list_recent(self, limit: int = 20) -> List[NotificationMessage]:
        with self._connection() as conn:
            cur = conn.execute("SELECT data_json FROM notifications ORDER BY timestamp DESC LIMIT ?", (limit,))
            rows = cur.fetchall()
            return [NotificationMessage(**json.loads(r["data_json"])) for r in rows]


class NotificationDispatcher:
    """Dispatches notifications across native Windows toasts, local voice TTS, and HUD."""

    def __init__(
        self,
        store: Optional[NotificationStore] = None,
        ui_state: Optional[UIStateManager] = None,
        tts_enabled: bool = True,
    ):
        self.store = store or NotificationStore()
        self.ui_state = ui_state or default_ui_state
        self.tts_enabled = tts_enabled
        self._tts_instance = None

    def _get_tts(self):
        if self._tts_instance is None and self.tts_enabled:
            try:
                from jarvis.subsystems.local.tts import LocalTTS
                self._tts_instance = LocalTTS(enabled=True)
            except Exception:
                pass
        return self._tts_instance

    def notify(
        self,
        title: str,
        message: str,
        severity: str = "INFO",
        channel: NotificationChannel = NotificationChannel.ALL,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> NotificationMessage:
        """Dispatches an alert to configured channels and records in persistent history."""
        notif = NotificationMessage(
            title=title,
            message=message,
            severity=severity,
            channel=channel,
            timestamp=time.time(),
            metadata=metadata or {},
        )

        channels_to_dispatch = {
            NotificationChannel.ALL: ["toast", "voice", "hud"],
            NotificationChannel.TOAST: ["toast"],
            NotificationChannel.VOICE: ["voice"],
            NotificationChannel.HUD: ["hud"],
        }.get(channel, ["hud"])

        # 1. UI HUD Update
        if "hud" in channels_to_dispatch:
            try:
                alert_text = f"[{title}] {message}"
                self.ui_state.add_message("JARVIS (Alert)", alert_text)
                self.ui_state.set_agent_state("ALERT", quote=alert_text[:80])
            except Exception:
                pass

        # 2. Voice Audio Announcement
        if "voice" in channels_to_dispatch and self.tts_enabled:
            try:
                tts = self._get_tts()
                if tts:
                    tts.speak(f"{title}. {message}")
            except Exception:
                pass

        # 3. Native Windows Toast
        if "toast" in channels_to_dispatch:
            self._send_windows_toast(title, message)

        notif.delivered = True
        self.store.record(notif)
        return notif

    def _send_windows_toast(self, title: str, message: str):
        """Sends native Windows notification via PowerShell Burp or WinRT without external dependencies."""
        safe_title = title.replace('"', '`"').replace("'", "''")
        safe_msg = message.replace('"', '`"').replace("'", "''")

        # PowerShell script using Windows Forms / BalloonTip notification
        ps_script = f"""
[void] [System.Reflection.Assembly]::LoadWithPartialName("System.Windows.Forms")
$objNotifyIcon = New-Object System.Windows.Forms.NotifyIcon
$objNotifyIcon.Icon = [System.Drawing.SystemIcons]::Information
$objNotifyIcon.BalloonTipIcon = "Info"
$objNotifyIcon.BalloonTipTitle = "{safe_title}"
$objNotifyIcon.BalloonTipText = "{safe_msg}"
$objNotifyIcon.Visible = $True
$objNotifyIcon.ShowBalloonTip(5000)
Start-Sleep -Seconds 1
$objNotifyIcon.Dispose()
"""
        def _runner():
            try:
                subprocess.run(
                    ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    timeout=6,
                )
            except Exception:
                pass

        # Run in background daemon thread to never block execution
        threading.Thread(target=_runner, daemon=True).start()
