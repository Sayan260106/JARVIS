"""JARVIS Interfaces: Native Desktop GUI, Terminal TUI, Web HUD, Voice, CLI."""

from jarvis.interfaces.desktop_gui import JarvisDesktopApp, launch_desktop
from jarvis.interfaces.desktop_tui import DesktopTUI, run_desktop_tui
from jarvis.interfaces.web_server import JarvisDashboardServer

__all__ = [
    "JarvisDesktopApp",
    "launch_desktop",
    "DesktopTUI",
    "run_desktop_tui",
    "JarvisDashboardServer",
]
