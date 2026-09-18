"""Desktop Terminal Interface (TUI) for JARVIS (Phase 12).

Renders the exact wireframe dashboard requested:
- Header with SYSTEM STATUS: ONLINE
- Arc reactor / Listening status orb
- Split panels: ACTIVE TASK (progress bar) and SYSTEM (CPU/RAM/Services)
- Recent conversational exchange
"""

from __future__ import annotations
import os
import sys
from typing import Optional

from jarvis.core.ui_state import UIStateManager, default_ui_state
from jarvis.capabilities.conversation import ConversationEngine


class DesktopTUI:
    """Renders the desktop TUI dashboard."""

    def __init__(self, state_manager: Optional[UIStateManager] = None):
        self.state = state_manager or default_ui_state

    def render(self) -> str:
        """Construct the complete wireframe layout string."""
        d = self.state.to_dict()
        task = d["active_task"]
        sys_m = d["system_metrics"]
        messages = d["messages"][-2:] if len(d["messages"]) >= 2 else d["messages"]

        # 58 inside characters wide
        w = 58
        lines = []

        lines.append("┌" + "─" * w + "┐")
        lines.append("│" + "J A R V I S".center(w) + "│")
        lines.append("│" + f"SYSTEM STATUS: {d['system_status']}".center(w) + "│")
        lines.append("├" + "─" * w + "┤")
        lines.append("│" + " " * w + "│")
        lines.append("│" + "◉".center(w) + "│")
        lines.append("│" + d["agent_state"].center(w) + "│")
        lines.append("│" + " " * w + "│")
        lines.append("│" + d["speech_quote"].center(w) + "│")
        lines.append("│" + " " * w + "│")

        # Split panels: Left = 25 chars, Right = 32 chars
        lines.append("├" + "─" * 25 + "┬" + "─" * 32 + "┤")
        lines.append("│" + " ACTIVE TASK".ljust(25) + "│" + " SYSTEM".ljust(32) + "│")
        lines.append("│" + " " * 25 + "│" + " " * 32 + "│")

        task_name = f" {task['name'][:23]}"
        cpu_line = f" CPU      {sys_m['cpu']}%"
        lines.append("│" + task_name.ljust(25) + "│" + cpu_line.ljust(32) + "│")

        bar_line = f" {task['progress_bar']}"
        ram_line = f" RAM      {sys_m['ram']}%"
        lines.append("│" + bar_line.ljust(25) + "│" + ram_line.ljust(32) + "│")

        step_line = f" {task['step_label']}"
        ollama_line = f" Ollama   {sys_m['ollama']}"
        lines.append("│" + step_line.ljust(25) + "│" + ollama_line.ljust(32) + "│")

        empty_left = " " * 25
        browser_line = f" Browser  {sys_m['browser']}"
        lines.append("│" + empty_left + "│" + browser_line.ljust(32) + "│")

        network_line = f" Network  {sys_m['network']}"
        lines.append("│" + empty_left + "│" + network_line.ljust(32) + "│")

        lines.append("├" + "─" * w + "┤")
        lines.append("│" + " " * w + "│")

        for m in messages:
            msg_line = f"  {m['sender']}: {m['text']}"
            if len(msg_line) > w - 2:
                msg_line = msg_line[: w - 5] + "..."
            lines.append("│" + msg_line.ljust(w) + "│")
            lines.append("│" + " " * w + "│")

        lines.append("└" + "─" * w + "┘")

        return "\n".join(lines)

    def display(self):
        """Prints the dashboard to stdout with encoding safety."""
        content = self.render()
        try:
            print(content)
        except UnicodeEncodeError:
            # Fallback to ascii replacement characters if terminal does not support unicode boxes
            safe_content = (
                content.replace("┌", "+")
                .replace("┐", "+")
                .replace("└", "+")
                .replace("┘", "+")
                .replace("├", "+")
                .replace("┤", "+")
                .replace("┬", "+")
                .replace("┴", "+")
                .replace("─", "-")
                .replace("│", "|")
                .replace("◉", "(*)")
                .replace("█", "#")
                .replace("░", "-")
                .replace("●", "*")
            )
            print(safe_content)


def run_desktop_tui():
    """Interactive CLI runner for the Desktop TUI."""
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    tui = DesktopTUI()
    engine = ConversationEngine()
    print("\nStarting JARVIS Desktop Interface...\n")
    tui.display()

    while True:
        try:
            user_input = input("\nYou > ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit"):
                print("JARVIS: System standing down. Goodbye, sir.")
                break

            tui.state.set_agent_state("THINKING...", quote="Analyzing request...")
            tui.state.add_message("You", user_input)

            response = engine.process_turn(user_input)

            tui.state.set_agent_state("LISTENING...", quote="Awaiting next instruction.")
            tui.state.add_message("JARVIS", response)

            tui.display()

        except (KeyboardInterrupt, EOFError):
            print("\nShutting down desktop interface.")
            break


if __name__ == "__main__":
    run_desktop_tui()
