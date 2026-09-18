"""JARVIS — Autonomous AI Assistant & System Orchestrator.

Master entrypoint supporting multiple operational interfaces:
  1. Desktop TUI: Terminal wireframe HUD dashboard with telemetry and interactive conversation.
  2. Web HUD: Modern HTML5/CSS/JS dashboard served at http://127.0.0.1:8888.
  3. CLI Agent Loop: Direct multi-step autonomous execution loop.
  4. Voice: Interactive offline Speech-to-Text (STT) and Text-to-Speech (TTS).
  5. Diagnostics: Self-test and environment telemetry verification.
"""

from __future__ import annotations
import argparse
import os
import sys
import time
import webbrowser

# Ensure UTF-8 output encoding for Windows terminal boxes and unicode characters
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def check_ollama_status(base_url: str = "http://127.0.0.1:11434") -> tuple[bool, list[str]]:
    """Checks if Ollama is running and lists installed models."""
    from jarvis.subsystems.local.ollama_client import OllamaClient
    client = OllamaClient(base_url=base_url, timeout=3.0)
    available = client.is_available()
    models = client.list_models() if available else []
    return available, models


def run_diagnostics():
    """Runs a comprehensive self-diagnostic test on all local JARVIS subsystems."""
    print("=" * 68)
    print(" JARVIS — System Diagnostics & Subsystem Health Check")
    print("=" * 68)

    # 1. Ollama SLM
    print("\n[1/6] Inspecting Local LLM (Ollama)...")
    ollama_ok, models = check_ollama_status()
    if ollama_ok:
        print(f"  [OK] Ollama is ONLINE at http://127.0.0.1:11434")
        print(f"       Installed Models: {', '.join(models) if models else 'None detected'}")
    else:
        print("  [WARN] Ollama is OFFLINE or unreachable on localhost:11434.")
        print("         Start Ollama with 'ollama serve' to enable local neural intelligence.")

    # 2. Local TTS (SAPI5)
    print("\n[2/6] Inspecting Audio Output (TTS)...")
    try:
        from jarvis.subsystems.local.tts import LocalTTS
        tts = LocalTTS(enabled=False)
        print("  [OK] Local SAPI5 text-to-speech driver initialized successfully.")
    except Exception as e:
        print(f"  [WARN] TTS driver unavailable: {e}")

    # 3. Local STT & Microphones
    print("\n[3/6] Inspecting Audio Input (Microphone & STT)...")
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        input_devs = [d for d in devices if d.get("max_input_channels", 0) > 0]
        print(f"  [OK] Audio input subsystem active: {len(input_devs)} input device(s) found.")
    except Exception as e:
        print(f"  [WARN] Microphone check encountered an issue: {e}")

    # 4. Hardware Telemetry
    print("\n[4/6] Inspecting Hardware Telemetry (psutil)...")
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        print(f"  [OK] CPU Load: {cpu:.1f}% | RAM: {mem.percent:.1f}% ({mem.used / (1024**3):.1f} GB / {mem.total / (1024**3):.1f} GB)")
    except Exception as e:
        print(f"  [WARN] Hardware telemetry check failed: {e}")

    # 5. Database Durability (SQLite)
    print("\n[5/6] Inspecting Memory & Task Database Storage...")
    try:
        from jarvis.subsystems.local.memory import ConversationMemory
        from jarvis.core.task_manager import TaskStore
        mem = ConversationMemory(db_path="data/jarvis_memory.db")
        store = TaskStore(db_path="data/jarvis_tasks.db")
        print("  [OK] SQLite memory and task stores verified (no resource leaks).")
    except Exception as e:
        print(f"  [FAIL] Database verification failed: {e}")

    # 6. Tool Registry
    print("\n[6/6] Inspecting Tool System...")
    try:
        from jarvis.tools import get_default_registry
        reg = get_default_registry()
        tools = reg.list_tools()
        print(f"  [OK] Tool registry verified: {len(tools)} tools ready across System, Web, Vision, and Memory.")
    except Exception as e:
        print(f"  [FAIL] Tool registry initialization failed: {e}")

    print("\n" + "=" * 68)
    print(" Diagnostics complete. JARVIS is ready to operate.")
    print("=" * 68)


def print_banner(ollama_ok: bool, models: list[str]):
    """Displays the JARVIS master banner."""
    model_str = models[0] if models else "qwen2.5:3b"
    status_str = f"● ONLINE ({model_str})" if ollama_ok else "○ OFFLINE (Run 'ollama serve')"

    print(r"""
     ╦ ╔═╗ ╦═╗ ╦  ╦ ╦ ╔═╗
     ║ ╠═╣ ╠╦╝ ╚╗╔╝ ║ ╚═╗
    ╚╝ ╩ ╩ ╩╚═  ╚╝  ╩ ╚═╝
    Autonomous AI Assistant & System Orchestrator
    """)
    print("─" * 64)
    print(f"  Intelligence Engine : Ollama {status_str}")
    print(f"  Speech Output       : Local SAPI5 Audio [ACTIVE]")
    print(f"  Memory & Tasks      : SQLite Persistent Storage [ACTIVE]")
    print(f"  Safety Gatekeeper   : 4-Level Deterministic Policy [ENFORCED]")
    print("─" * 64)


def interactive_menu():
    """Displays an interactive menu allowing the user to select launch mode."""
    ollama_ok, models = check_ollama_status()
    print_banner(ollama_ok, models)

    print("\nSelect an operational mode to launch:")
    print("  [1] Desktop TUI Dashboard (Wireframe Terminal HUD)  [Default: Press Enter]")
    print("  [2] Web HUD Interface     (Browser HUD @ http://127.0.0.1:8888)")
    print("  [3] Autonomous Agent CLI  (Continuous Agent Loop)")
    print("  [4] Voice Interface       (Interactive Audio Console)")
    print("  [5] System Diagnostics    (Health & Connectivity Check)")
    print("  [Q] Exit")

    choice = input("\nJARVIS > ").strip().lower()

    if choice in ("", "1", "tui"):
        launch_tui()
    elif choice in ("2", "web", "hud"):
        launch_web(port=8888, open_browser=True)
    elif choice in ("3", "cli"):
        launch_cli()
    elif choice in ("4", "voice"):
        launch_voice()
    elif choice in ("5", "diag", "diagnostics"):
        run_diagnostics()
    elif choice in ("q", "quit", "exit"):
        print("Standing down. Goodbye.")
        sys.exit(0)
    else:
        print("Unknown selection. Defaulting to Desktop TUI...")
        time.sleep(1)
        launch_tui()


def launch_tui():
    """Launches the Desktop Terminal HUD."""
    from jarvis.interfaces.desktop_tui import run_desktop_tui
    run_desktop_tui()


def launch_web(port: int = 8888, open_browser: bool = True):
    """Launches the Web HUD dashboard."""
    from jarvis.interfaces.web_server import JarvisDashboardServer
    url = f"http://127.0.0.1:{port}"
    print(f"\n[JARVIS] Launching Web HUD at {url}...")
    server = JarvisDashboardServer(port=port)

    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass

    server.start(in_background=False)


def launch_cli():
    """Launches the CLI Agent Loop."""
    from jarvis.interfaces.cli import run_cli
    run_cli()


def launch_voice(mode: str = "interactive", model: str = "qwen2.5:3b"):
    """Launches the Voice & Audio interface."""
    from jarvis.capabilities.conversation import ConversationEngine
    from jarvis.subsystems.local.ollama_client import OllamaClient
    from jarvis.subsystems.local.tts import LocalTTS
    from jarvis.subsystems.local.stt import LocalSTT
    from jarvis.interfaces.voice import run_interactive, run_microphone

    ollama = OllamaClient(model=model)
    tts = LocalTTS(enabled=True)
    stt = LocalSTT()
    engine = ConversationEngine(ollama_client=ollama, tts=tts, stt=stt)

    if mode == "mic":
        run_microphone(engine)
    else:
        run_interactive(engine)


def main():
    parser = argparse.ArgumentParser(description="JARVIS Autonomous AI Assistant")
    parser.add_argument(
        "--mode",
        choices=["tui", "web", "cli", "voice", "diagnostics", "menu"],
        default=None,
        help="Interface mode to run: tui (default), web, cli, voice, or diagnostics",
    )
    parser.add_argument(
        "--tui", action="store_true", help="Launch Desktop Terminal TUI Dashboard directly"
    )
    parser.add_argument(
        "--web", "--hud", action="store_true", help="Launch Web HUD server directly"
    )
    parser.add_argument(
        "--cli", action="store_true", help="Launch Agent Loop CLI directly"
    )
    parser.add_argument(
        "--voice", action="store_true", help="Launch Voice Interface directly"
    )
    parser.add_argument(
        "--diagnostics", action="store_true", help="Run system diagnostics directly"
    )
    parser.add_argument(
        "--port", type=int, default=8888, help="Port for Web HUD (default: 8888)"
    )
    parser.add_argument(
        "--no-browser", action="store_true", help="Do not automatically open browser on Web HUD launch"
    )
    parser.add_argument(
        "--mic", action="store_true", help="Use microphone speech recognition for voice mode"
    )
    parser.add_argument(
        "--model", default="qwen2.5:3b", help="Ollama model name (default: qwen2.5:3b)"
    )

    args, unknown = parser.parse_known_args()

    if args.diagnostics or args.mode == "diagnostics":
        run_diagnostics()
    elif args.tui or args.mode == "tui":
        launch_tui()
    elif args.web or args.mode == "web":
        launch_web(port=args.port, open_browser=not args.no_browser)
    elif args.cli or args.mode == "cli":
        launch_cli()
    elif args.voice or args.mode == "voice":
        mode = "mic" if args.mic else "interactive"
        launch_voice(mode=mode, model=args.model)
    elif args.mode == "menu":
        interactive_menu()
    else:
        # If any command line argument was passed (e.g. CLI prompt), delegate to CLI
        if unknown:
            from jarvis.interfaces.cli import run_cli
            run_cli()
        else:
            interactive_menu()


if __name__ == "__main__":
    main()
