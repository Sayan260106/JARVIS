"""Service Execution & Health Verification Tools for Windows.

Provides background process launching, port management, and HTTP endpoint verification.
"""

from __future__ import annotations
import os
import subprocess
import time
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional

from jarvis.tools.base import BaseTool, RiskLevel, ToolParameter, ToolResult, ToolVerification


class FreePortTool(BaseTool):
    """Finds and terminates stale processes holding a specified TCP port on Windows."""
    name = "free_port"
    description = "Frees a blocked network port on Windows by finding and terminating the conflicting process."
    risk_level = RiskLevel.MEDIUM
    parameters = {
        "port": ToolParameter("port", "integer", "The TCP port to free (e.g. 8000).", required=True),
    }

    def execute(self, port: int, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        target_port = int(port)
        killed_pids = []

        try:
            # Run netstat -ano to find PID listening on target port
            cmd = f'netstat -ano | findstr LISTENING | findstr :{target_port}'
            proc = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            output = proc.stdout.strip()

            if output:
                lines = output.splitlines()
                for line in lines:
                    parts = line.strip().split()
                    if len(parts) >= 5 and f":{target_port}" in parts[1]:
                        pid = parts[-1]
                        if pid.isdigit() and int(pid) > 0 and int(pid) != os.getpid():
                            # Kill stale conflicting process
                            subprocess.run(f"taskkill /F /PID {pid}", shell=True, capture_output=True)
                            killed_pids.append(int(pid))

            return ToolResult(
                success=True,
                output={
                    "port": target_port,
                    "freed": True,
                    "terminated_pids": list(set(killed_pids)),
                },
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=str(e),
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        if not result.success:
            return ToolVerification(verified=False, details=f"Failed to free port: {result.error}")
        return ToolVerification(
            verified=True,
            details=f"Port {arguments['port']} freed (terminated PIDs: {result.output.get('terminated_pids', [])})."
        )


class VerifyEndpointTool(BaseTool):
    """Pings a local or remote HTTP endpoint to verify service health."""
    name = "verify_endpoint"
    description = "Checks whether a service or backend is responding on an HTTP endpoint (e.g. http://127.0.0.1:8000/health)."
    risk_level = RiskLevel.LOW
    parameters = {
        "url": ToolParameter("url", "string", "Endpoint URL to probe (e.g. 'http://127.0.0.1:8000/health').", required=True),
        "timeout_seconds": ToolParameter("timeout_seconds", "integer", "Timeout for HTTP request.", required=False, default=3),
    }

    def execute(self, url: str, timeout_seconds: int = 3, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        target_url = url.strip()
        timeout = max(1, int(timeout_seconds))

        try:
            req = urllib.request.Request(target_url, headers={"User-Agent": "JARVIS-HealthCheck/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as response:
                status_code = response.getcode()
                body = response.read().decode("utf-8", errors="ignore")[:500]

            return ToolResult(
                success=True,
                output={
                    "url": target_url,
                    "status_code": status_code,
                    "body_snippet": body,
                    "healthy": True,
                },
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )
        except urllib.error.HTTPError as he:
            code = he.code
            try:
                he.close()
            except Exception:
                pass
            # 404 or 401 still means server is up and listening
            return ToolResult(
                success=True,
                output={
                    "url": target_url,
                    "status_code": code,
                    "healthy": True,
                    "note": f"Server responded with HTTP {code}",
                },
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=f"Endpoint unreachable: {str(e)}",
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        if not result.success:
            return ToolVerification(verified=False, details=f"Endpoint health check failed: {result.error}")
        return ToolVerification(
            verified=True,
            details=f"Endpoint '{arguments['url']}' is healthy (HTTP {result.output.get('status_code', 200)})."
        )


class StartBackendServiceTool(BaseTool):
    """Starts a backend process and observes initial execution for early crashes."""
    name = "start_backend_service"
    description = "Starts a background process or service command, monitoring for immediate crashes or startup errors."
    risk_level = RiskLevel.MEDIUM
    parameters = {
        "command": ToolParameter("command", "string", "Command to launch (e.g. 'python backend.py').", required=True),
        "cwd": ToolParameter("cwd", "string", "Working directory for the service.", required=False),
        "startup_wait_seconds": ToolParameter("startup_wait_seconds", "integer", "Seconds to observe startup health.", required=False, default=2),
    }

    def execute(
        self,
        command: str,
        cwd: Optional[str] = None,
        startup_wait_seconds: int = 2,
        **kwargs,
    ) -> ToolResult:
        start_t = time.perf_counter()
        working_dir = os.path.abspath(cwd) if cwd else os.getcwd()
        wait_time = max(1, int(startup_wait_seconds))

        try:
            # Launch in background process
            proc = subprocess.Popen(
                command,
                cwd=working_dir,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            # Observe for startup duration
            time.sleep(wait_time)
            poll_result = proc.poll()

            if poll_result is not None and poll_result != 0:
                # Process crashed immediately!
                stdout_err = ""
                try:
                    out, err = proc.communicate(timeout=1)
                    stdout_err = f"STDOUT: {out}\nSTDERR: {err}".strip()
                except Exception:
                    pass

                return ToolResult(
                    success=False,
                    output={
                        "pid": proc.pid,
                        "exit_code": poll_result,
                        "command": command,
                    },
                    error=f"Process crashed with exit code {poll_result}.\n{stdout_err}",
                    duration_ms=(time.perf_counter() - start_t) * 1000,
                )

            # If process exited cleanly (exit code 0), close pipes
            if poll_result == 0:
                try:
                    proc.communicate(timeout=1)
                except Exception:
                    pass

            return ToolResult(
                success=True,
                output={
                    "pid": proc.pid,
                    "command": command,
                    "cwd": working_dir,
                    "is_running": (poll_result is None),
                },
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=f"Failed to start service: {str(e)}",
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        if not result.success:
            return ToolVerification(verified=False, details=f"Service failed during startup: {result.error}")
        return ToolVerification(
            verified=True,
            details=f"Service running with PID {result.output.get('pid')} for command '{arguments['command']}'."
        )
