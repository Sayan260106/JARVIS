"""Lightweight HTTP Server for JARVIS Desktop Web HUD (Phase 12).

Serves the Web Dashboard and provides JSON REST endpoints:
- GET  /api/status -> Live UI state, active task progress & hardware telemetry
- POST /api/chat   -> Dispatches query to ConversationEngine and updates state
"""

from __future__ import annotations
import http.server
import json
import mimetypes
import os
import socketserver
import threading
from typing import Optional

from jarvis.core.ui_state import UIStateManager, default_ui_state
from jarvis.capabilities.conversation import ConversationEngine

DASHBOARD_DIR = os.path.join(os.path.dirname(__file__), "web_dashboard")


class JarvisHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    """Custom HTTP handler serving dashboard files and dynamic REST endpoints."""

    def __init__(self, *args, state_manager: Optional[UIStateManager] = None, engine: Optional[ConversationEngine] = None, **kwargs):
        self.state_manager = state_manager or default_ui_state
        self.engine = engine or ConversationEngine()
        super().__init__(*args, directory=DASHBOARD_DIR, **kwargs)

    def do_GET(self):
        if self.path == "/api/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Connection", "close")
            self.end_headers()
            data = json.dumps(self.state_manager.to_dict()).encode("utf-8")
            self.wfile.write(data)
            self.close_connection = True
            return

        if self.path == "/api/proactive":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Connection", "close")
            self.end_headers()
            try:
                from jarvis.subsystems.proactive.engine import ProactiveEngine
                engine = ProactiveEngine.get_instance()
                triggers = [t.to_dict() for t in engine.list_triggers()]
                schedules = [s.to_dict() for s in engine.scheduler.list_schedules()]
            except Exception:
                triggers = []
                schedules = []

            payload = {
                "active_monitors": self.state_manager.active_monitors,
                "scheduled_tasks": schedules,
                "triggers": triggers,
                "recent_notifications": self.state_manager.recent_notifications,
            }
            self.wfile.write(json.dumps(payload).encode("utf-8"))
            self.close_connection = True
            return

        # Serve static assets from DASHBOARD_DIR
        return super().do_GET()


    def do_POST(self):
        if self.path == "/api/chat":
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len)
            try:
                payload = json.loads(body.decode("utf-8"))
                user_msg = payload.get("message", "").strip()
            except Exception:
                user_msg = ""

            if user_msg:
                self.state_manager.add_message("You", user_msg)
                self.state_manager.set_agent_state("THINKING...", quote="Processing instruction...")

                response = self.engine.process_turn(user_msg)

                self.state_manager.add_message("JARVIS", response)
                self.state_manager.set_agent_state("LISTENING...", quote="How may I assist you?")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Connection", "close")
            self.end_headers()
            data = json.dumps(self.state_manager.to_dict()).encode("utf-8")
            self.wfile.write(data)
            self.close_connection = True
            return

        self.send_error(404, "Endpoint not found")


class JarvisDashboardServer:
    """Manages the background or foreground Web HUD server."""

    def __init__(
        self,
        port: int = 8888,
        state_manager: Optional[UIStateManager] = None,
        engine: Optional[ConversationEngine] = None,
    ):
        self.port = port
        self.state_manager = state_manager or default_ui_state
        self.engine = engine or ConversationEngine(speak_output=False)
        self.httpd: Optional[socketserver.TCPServer] = None
        self._thread: Optional[threading.Thread] = None


    def start(self, in_background: bool = True):
        """Starts the server."""
        handler_factory = lambda *args, **kwargs: JarvisHTTPRequestHandler(
            *args, state_manager=self.state_manager, engine=self.engine, **kwargs
        )
        socketserver.TCPServer.allow_reuse_address = True
        self.httpd = socketserver.TCPServer(("", self.port), handler_factory)

        if in_background:
            self._thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
            self._thread.start()
            print(f"[JARVIS Web HUD] Active at http://127.0.0.1:{self.port}")
        else:
            print(f"[JARVIS Web HUD] Running at http://127.0.0.1:{self.port} (Press Ctrl+C to exit)...")
            try:
                self.httpd.serve_forever()
            except KeyboardInterrupt:
                self.stop()

    def stop(self):
        """Shuts down the server."""
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.httpd = None
            print("[JARVIS Web HUD] Stopped.")


def run_web_dashboard():
    """Main entry point when executed via python -m jarvis.interfaces.web_server."""
    server = JarvisDashboardServer(port=8888)
    server.start(in_background=False)


if __name__ == "__main__":
    run_web_dashboard()
