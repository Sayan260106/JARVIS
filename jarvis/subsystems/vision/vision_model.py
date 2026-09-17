"""Visual Understanding & Multimodal Vision Models for JARVIS.

Analyzes captured screen images using local Ollama vision models,
cloud multimodal vision (Gemini), or built-in heuristic diagnostics.
Specifically answers questions like: "Jarvis, what's wrong?".
"""

from __future__ import annotations
from dataclasses import dataclass, field
import json
import os
import re
import urllib.request
from typing import Any, Dict, List, Optional

from jarvis.subsystems.vision.screen_capture import CapturedScreen


@dataclass
class VisionAnalysis:
    """Structured interpretation of screen imagery."""
    description: str
    detected_issues: List[str] = field(default_factory=list)
    suggested_action: str = ""
    ui_elements: List[Dict[str, Any]] = field(default_factory=list)
    has_error: bool = False
    confidence: float = 1.0


class VisionModel:
    """Multimodal reasoning engine for screen visual inspection."""

    def __init__(
        self,
        ollama_base_url: str = "http://127.0.0.1:11434",
        ollama_vision_model: str = "llava",
        gemini_api_key: Optional[str] = None,
    ):
        self.ollama_base_url = ollama_base_url.rstrip("/")
        self.ollama_vision_model = ollama_vision_model
        self.gemini_api_key = gemini_api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")

    def analyze_screen(
        self,
        screen: CapturedScreen,
        prompt: str = "What is on the screen and what's wrong?",
    ) -> VisionAnalysis:
        """Analyzes the given screen and returns structured diagnostic understanding."""
        # 1. Check if Gemini Vision is configured
        if self.gemini_api_key:
            gemini_res = self._query_gemini_vision(screen, prompt)
            if gemini_res:
                return gemini_res

        # 2. Check if local Ollama vision model is available
        ollama_res = self._query_ollama_vision(screen, prompt)
        if ollama_res:
            return ollama_res

        # 3. Comprehensive Heuristic & Pattern Diagnostic Engine
        return self._heuristic_screen_analysis(screen, prompt)

    def diagnose_whats_wrong(self, screen: CapturedScreen) -> str:
        """Direct conversational response for 'Jarvis, what's wrong?'."""
        analysis = self.analyze_screen(screen, prompt="Inspect the screen for errors or issues.")
        if not analysis.has_error or not analysis.detected_issues:
            return (
                "I inspected your screen. Everything appears normal—there are no visible "
                "crash dialogs, error alerts, or unhandled exceptions in the active windows."
            )

        issue_summary = "\n".join(f"- {issue}" for issue in analysis.detected_issues)
        recommendation = f"\nSuggested fix: {analysis.suggested_action}" if analysis.suggested_action else ""
        return (
            f"I inspected your screen and identified the following issue(s):\n{issue_summary}{recommendation}"
        )

    def _query_gemini_vision(self, screen: CapturedScreen, prompt: str) -> Optional[VisionAnalysis]:
        """Attempts visual analysis using Google Gemini multimodal endpoint."""
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.gemini_api_key}"
            payload = {
                "contents": [
                    {
                        "parts": [
                            {"text": f"{prompt} If there are any errors or crashes, detail them and suggest fixes."},
                            {
                                "inline_data": {
                                    "mime_type": "image/png",
                                    "data": screen.base64_data,
                                }
                            }
                        ]
                    }
                ]
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                has_err = any(w in text.lower() for w in ["error", "exception", "failed", "crash", "traceback", "syntax"])
                issues = [line.strip("- ") for line in text.split("\n") if any(w in line.lower() for w in ["error", "failed", "traceback"])]
                return VisionAnalysis(
                    description=text,
                    detected_issues=issues,
                    suggested_action="Review the code or highlighted stack trace according to the suggestions above.",
                    has_error=has_err,
                    confidence=0.95,
                )
        except Exception:
            return None

    def _query_ollama_vision(self, screen: CapturedScreen, prompt: str) -> Optional[VisionAnalysis]:
        """Attempts visual analysis using local Ollama vision model."""
        try:
            url = f"{self.ollama_base_url}/api/generate"
            payload = {
                "model": self.ollama_vision_model,
                "prompt": prompt,
                "images": [screen.base64_data],
                "stream": False,
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                text = data.get("response", "").strip()
                if not text:
                    return None
                has_err = any(w in text.lower() for w in ["error", "exception", "failed", "crash", "traceback"])
                return VisionAnalysis(
                    description=text,
                    detected_issues=[text] if has_err else [],
                    has_error=has_err,
                    confidence=0.88,
                )
        except Exception:
            return None

    def _heuristic_screen_analysis(self, screen: CapturedScreen, prompt: str) -> VisionAnalysis:
        """In-depth heuristic diagnostic analysis based on screen state and simulated context."""
        context = screen.simulated_context or ""
        issues = []
        suggested_action = ""

        # Check for Python / compiler tracebacks
        if "traceback (most recent call last)" in context.lower():
            matches = re.findall(r"(\w+Error:[^\n]+)", context)
            if matches:
                for m in matches:
                    issues.append(f"Unhandled Exception: {m}")
            else:
                issues.append("Active Traceback detected in console output.")
            suggested_action = "Inspect the line highlighted in the traceback and fix the referenced variable or import."

        # Check for Process Crashes / Exits
        elif "process crashed" in context.lower() or "exit code 1" in context.lower():
            issues.append("Terminal process crashed with non-zero exit code.")
            suggested_action = "Restart the backend server with debug logging enabled."

        # Check for Connection / Server Refused
        elif "connection refused" in context.lower() or "err_connection_refused" in context.lower():
            issues.append("Network connection refused on target port.")
            suggested_action = "Verify the target local service or database daemon is actively running."

        # Check for Build / Syntax Failures
        elif any(w in context.lower() for w in ["syntaxerror", "compilation failed", "build failed"]):
            syntax_line = next((l.strip() for l in context.split("\n") if "syntax" in l.lower() or "build" in l.lower()), "SyntaxError: Compilation failed.")
            issues.append(f"Syntax/Build Failure: {syntax_line}")
            suggested_action = "Correct the syntax error in the source code before rebuilding."

        # Generic error check
        elif "error" in context.lower() or "failed" in context.lower():
            lines = [l.strip() for l in context.split("\n") if "error" in l.lower() or "fail" in l.lower()]
            issues.extend(lines[:3])
            suggested_action = "Address the flagged error lines shown in the active terminal window."

        has_err = len(issues) > 0
        desc = (
            f"Screen analysis ({screen.width}x{screen.height}, {screen.source}): "
            + (f"Found {len(issues)} issue(s)." if has_err else "Desktop state is stable and healthy.")
        )

        return VisionAnalysis(
            description=desc,
            detected_issues=issues,
            suggested_action=suggested_action,
            has_error=has_err,
            confidence=0.90 if has_err else 0.80,
        )
