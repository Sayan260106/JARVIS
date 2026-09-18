"""Test Suite for JARVIS Desktop UI, Terminal TUI & Web Dashboard (Phase 12).

Verifies:
- Desktop TUI matching exact ASCII wireframe layout
- Active task progress bar calculations (████████████░░ 82%)
- Hardware metrics telemetry (CPU, RAM, Ollama, Browser, Network)
- Web HUD server endpoints (GET /api/status, POST /api/chat)
"""

import json
import os
import unittest
import urllib.request

from jarvis.core.ui_state import UIStateManager, ActiveTaskInfo
from jarvis.interfaces.desktop_tui import DesktopTUI
from jarvis.interfaces.web_server import JarvisDashboardServer


class TestDesktopUIAndDashboard(unittest.TestCase):
    """Tests UI state management, Terminal TUI formatting, and Web HUD endpoints."""

    def setUp(self):
        self.state = UIStateManager()

    def test_active_task_progress_bar(self):
        """Verify graphical progress bar rendering matches wireframe formatting."""
        task = ActiveTaskInfo(
            name="ORCA-X verification",
            progress_pct=82,
            current_step=9,
            total_steps=12,
        )
        bar = task.render_bar(width=16)
        # 82% of 16 = 13 filled blocks
        self.assertIn("82%", bar)
        self.assertIn("█", bar)
        self.assertIn("░", bar)

    def test_desktop_tui_wireframe_structure(self):
        """Verify DesktopTUI renders all sections of the user wireframe."""
        tui = DesktopTUI(state_manager=self.state)
        rendered = tui.render()

        # 1. Header
        self.assertIn("J A R V I S", rendered)
        self.assertIn("SYSTEM STATUS: ONLINE", rendered)

        # 2. Status Orb & Greeting
        self.assertIn("◉", rendered)
        self.assertIn("LISTENING...", rendered)
        self.assertIn('"How may I assist you?"', rendered)

        # 3. Active Task & Progress
        self.assertIn("ACTIVE TASK", rendered)
        self.assertIn("ORCA-X verification", rendered)
        self.assertIn("82%", rendered)
        self.assertIn("Step 9/12", rendered)

        # 4. System Telemetry
        self.assertIn("SYSTEM", rendered)
        self.assertIn("CPU", rendered)
        self.assertIn("RAM", rendered)
        self.assertIn("Ollama   ● ONLINE", rendered)
        self.assertIn("Browser  ● READY", rendered)
        self.assertIn("Network  ● ONLINE", rendered)

        # 5. Conversation Stream
        self.assertIn("You: Verify the realtime API", rendered)
        self.assertIn("JARVIS: Certainly. I'm checking the endpoint now.", rendered)

    def test_web_hud_server_endpoints(self):
        """Verify Web HUD server starts, responds to GET /api/status, and POST /api/chat."""
        from jarvis.capabilities.conversation import ConversationEngine
        engine = ConversationEngine(enable_tools=False, speak_output=False)
        server = JarvisDashboardServer(port=8899, state_manager=self.state, engine=engine)
        server.start(in_background=True)


        try:
            # 1. Test GET /api/status
            req = urllib.request.Request("http://127.0.0.1:8899/api/status")
            with urllib.request.urlopen(req, timeout=3.0) as res:
                self.assertEqual(res.status, 200)
                data = json.loads(res.read().decode("utf-8"))
                self.assertEqual(data["system_status"], "ONLINE")
                self.assertIn("active_task", data)
                self.assertEqual(data["active_task"]["name"], "ORCA-X verification")
                self.assertIn("system_metrics", data)

            # 2. Test POST /api/chat
            chat_payload = json.dumps({"message": "Thank you Jarvis"}).encode("utf-8")
            post_req = urllib.request.Request(
                "http://127.0.0.1:8899/api/chat",
                data=chat_payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(post_req, timeout=3.0) as res:
                self.assertEqual(res.status, 200)
                resp_data = json.loads(res.read().decode("utf-8"))
                # Verify that our message was added to the history
                last_msg = resp_data["messages"][-1]
                self.assertEqual(last_msg["sender"], "JARVIS")
                self.assertIn("pleasure to be of service, sir", last_msg["text"].lower())

            # 3. Test Static index.html asset serving
            index_req = urllib.request.Request("http://127.0.0.1:8899/index.html")
            with urllib.request.urlopen(index_req, timeout=3.0) as res:
                self.assertEqual(res.status, 200)
                html = res.read().decode("utf-8")
                self.assertIn("J A R V I S", html)

        finally:
            server.stop()


if __name__ == "__main__":
    unittest.main()
