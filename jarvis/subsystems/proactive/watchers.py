"""Proactive Environment Watchers for Phase 17 — Proactive JARVIS.

Includes:
1. FolderWatcher: Monitors directories (e.g. Downloads) for new/completed files (*.pdf).
2. ProcessWatcher: Monitors background processes (e.g. GPU training scripts) for completion.
3. MetricWatcher: Monitors hardware metrics and resource thresholds.
"""

from __future__ import annotations
import fnmatch
import os
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Set
import uuid

import psutil

from jarvis.subsystems.proactive.schemas import (
    Event,
    EventType,
    FileEvent,
    ProcessEvent,
)


class FolderWatcher:
    """Monitors a file system directory for file additions or modifications.

    Includes smart filtering to ignore partial browser downloads (.crdownload, .tmp, .part)
    until they are fully written and finalized.
    """

    IGNORABLE_EXTENSIONS = {".crdownload", ".tmp", ".part", ".downloading"}

    def __init__(
        self,
        folder_path: str,
        file_pattern: str = "*.*",
        callback: Optional[Callable[[FileEvent], None]] = None,
        poll_interval: float = 1.0,
        recursive: bool = False,
    ):
        self.watcher_id = f"watch_dir_{uuid.uuid4().hex[:8]}"
        self.folder_path = os.path.abspath(folder_path)
        self.file_pattern = file_pattern
        self.callback = callback
        self.poll_interval = poll_interval
        self.recursive = recursive

        self._known_files: Dict[str, float] = {}  # path -> mtime
        self._running = False
        self._thread: Optional[threading.Thread] = None

        # Snapshot current directory state so existing files aren't mistakenly triggered as "new"
        self._initialize_snapshot()

    def _initialize_snapshot(self):
        """Records initial file state without firing events."""
        if not os.path.exists(self.folder_path):
            return
        for root, _, files in os.walk(self.folder_path):
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext in self.IGNORABLE_EXTENSIONS:
                    continue
                path = os.path.join(root, f)
                try:
                    self._known_files[path] = os.path.getmtime(path)
                except Exception:
                    pass
            if not self.recursive:
                break

    def poll_once(self) -> List[FileEvent]:
        """Scans the directory once and returns newly created or modified FileEvents."""
        events: List[FileEvent] = []
        if not os.path.exists(self.folder_path):
            return events

        current_files: Dict[str, float] = {}

        for root, _, files in os.walk(self.folder_path):
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext in self.IGNORABLE_EXTENSIONS:
                    continue

                if not fnmatch.fnmatch(f.lower(), self.file_pattern.lower()):
                    continue

                full_path = os.path.join(root, f)
                try:
                    mtime = os.path.getmtime(full_path)
                    size = os.path.getsize(full_path)
                    current_files[full_path] = mtime

                    # Check if file is newly discovered
                    if full_path not in self._known_files:
                        evt = FileEvent(
                            source=f"folder_watcher:{self.watcher_id}",
                            payload={
                                "file_path": full_path,
                                "file_name": f,
                                "action": "created",
                                "extension": ext,
                                "size_bytes": size,
                                "mtime": mtime,
                            }
                        )
                        events.append(evt)
                        if self.callback:
                            try:
                                self.callback(evt)
                            except Exception:
                                pass
                    elif mtime > self._known_files[full_path] + 0.1:
                        evt = FileEvent(
                            source=f"folder_watcher:{self.watcher_id}",
                            payload={
                                "file_path": full_path,
                                "file_name": f,
                                "action": "modified",
                                "extension": ext,
                                "size_bytes": size,
                                "mtime": mtime,
                            }
                        )
                        events.append(evt)
                        if self.callback:
                            try:
                                self.callback(evt)
                            except Exception:
                                pass
                except Exception:
                    pass

            if not self.recursive:
                break

        self._known_files.update(current_files)
        return events

    def start(self):
        """Starts background polling thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, name=f"JARVIS-Watcher-{self.watcher_id}", daemon=True)
        self._thread.start()

    def stop(self):
        """Stops background polling thread."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def _run_loop(self):
        while self._running:
            try:
                self.poll_once()
            except Exception:
                pass
            time.sleep(self.poll_interval)


class ProcessWatcher:
    """Monitors running operating system processes (e.g. GPU training, compiler, scripts)
    and emits an event when the process finishes, exits, or crashes.
    """

    def __init__(
        self,
        process_name_pattern: str = "",
        pid: Optional[int] = None,
        callback: Optional[Callable[[ProcessEvent], None]] = None,
        poll_interval: float = 1.0,
        description: str = "GPU Training / Process",
    ):
        self.watcher_id = f"watch_proc_{uuid.uuid4().hex[:8]}"
        self.pattern = process_name_pattern.lower()
        self.target_pid = pid
        self.callback = callback
        self.poll_interval = poll_interval
        self.description = description

        self._monitored_pid: Optional[int] = pid
        self._resolved_name: str = process_name_pattern
        self._start_time: float = time.time()
        self._detected_running = False
        self._completed = False
        self._running = False
        self._thread: Optional[threading.Thread] = None

        # Resolve PID if not directly supplied
        if self._monitored_pid is None and self.pattern:
            self._find_target_process()

    def _find_target_process(self) -> Optional[int]:
        """Locates active PID matching process_name_pattern or commandline."""
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                name = (proc.info.get("name") or "").lower()
                cmdline = " ".join(proc.info.get("cmdline") or []).lower()

                if fnmatch.fnmatch(name, self.pattern) or self.pattern in name or self.pattern in cmdline:
                    self._monitored_pid = proc.info["pid"]
                    self._resolved_name = proc.info.get("name") or self.pattern
                    self._detected_running = True
                    try:
                        self._start_time = proc.create_time()
                    except Exception:
                        self._start_time = time.time()
                    return self._monitored_pid
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return None

    def poll_once(self) -> Optional[ProcessEvent]:
        """Checks target process status. If it was running and has now exited, emits ProcessEvent."""
        if self._completed:
            return None

        # If not yet found, try to locate it
        if self._monitored_pid is None:
            pid = self._find_target_process()
            if pid is None:
                return None

        # Check if process is still running
        try:
            proc = psutil.Process(self._monitored_pid)
            if proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE:
                self._detected_running = True
                return None
            else:
                # Process exists as zombie or stopped
                return self._emit_completion(exit_code=0)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            # Process has terminated!
            if self._detected_running or self.target_pid is not None:
                return self._emit_completion(exit_code=0)
            return None

    def _emit_completion(self, exit_code: int = 0) -> ProcessEvent:
        """Constructs and emits process termination event."""
        self._completed = True
        runtime = max(0.1, time.time() - self._start_time)
        evt = ProcessEvent(
            source=f"process_watcher:{self.watcher_id}",
            payload={
                "process_name": self._resolved_name,
                "pid": self._monitored_pid,
                "status": "finished",
                "exit_code": exit_code,
                "runtime_seconds": round(runtime, 2),
                "description": self.description,
            }
        )
        if self.callback:
            try:
                self.callback(evt)
            except Exception:
                pass
        return evt

    def start(self):
        if self._running or self._completed:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, name=f"JARVIS-ProcWatcher-{self.watcher_id}", daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def _run_loop(self):
        while self._running and not self._completed:
            try:
                evt = self.poll_once()
                if evt:
                    break
            except Exception:
                pass
            time.sleep(self.poll_interval)
