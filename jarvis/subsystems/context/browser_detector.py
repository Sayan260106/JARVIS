"""Active Browser URL Detection for Phase 10.

Extracts current URL and page metadata from active web browsers:
- Microsoft Edge
- Google Chrome
- Brave
- Mozilla Firefox
- Opera / Vivaldi
"""

from __future__ import annotations
import re
import subprocess
import urllib.parse
from typing import Optional, Tuple
from jarvis.subsystems.context.schemas import BrowserContext


KNOWN_BROWSER_PROCESSES = {
    "msedge.exe": "Microsoft Edge",
    "chrome.exe": "Google Chrome",
    "brave.exe": "Brave",
    "firefox.exe": "Mozilla Firefox",
    "opera.exe": "Opera",
    "vivaldi.exe": "Vivaldi",
}


class BrowserDetector:
    """Detects active browser presence and extracts the active tab URL."""

    @classmethod
    def is_browser_process(cls, process_name: str) -> bool:
        if not process_name:
            return False
        return process_name.strip().lower() in KNOWN_BROWSER_PROCESSES

    @classmethod
    def get_browser_name(cls, process_name: str) -> str:
        clean = process_name.strip().lower() if process_name else ""
        return KNOWN_BROWSER_PROCESSES.get(clean, "Web Browser")

    @classmethod
    def detect_context(
        cls,
        process_name: str,
        window_title: str,
        hwnd: int = 0,
    ) -> BrowserContext:
        """Inspects foreground window to determine browser URL and metadata."""
        if not cls.is_browser_process(process_name):
            return BrowserContext(is_browser_active=False)

        browser_name = cls.get_browser_name(process_name)
        page_title = cls._clean_page_title(window_title, browser_name)

        # 1. Try URL extraction from window title (some configurations / tabs include URL or domain)
        url_from_title = cls._extract_url_from_title(window_title)
        if url_from_title:
            domain = cls._extract_domain(url_from_title)
            return BrowserContext(
                is_browser_active=True,
                browser_name=browser_name,
                current_url=url_from_title,
                page_title=page_title,
                domain=domain,
                detection_method="window_title",
            )

        # 2. Try UI Automation query for address bar
        if hwnd > 0:
            uia_url = cls._query_address_bar_via_uia(hwnd)
            if uia_url:
                domain = cls._extract_domain(uia_url)
                return BrowserContext(
                    is_browser_active=True,
                    browser_name=browser_name,
                    current_url=uia_url,
                    page_title=page_title,
                    domain=domain,
                    detection_method="uia",
                )

        # 3. Fallback: Browser is active, infer approximate domain or search query from page title
        domain = cls._infer_domain_from_title(window_title)
        fallback_url = f"https://{domain}" if domain else ""

        return BrowserContext(
            is_browser_active=True,
            browser_name=browser_name,
            current_url=fallback_url,
            page_title=page_title,
            domain=domain,
            detection_method="page_title_inference",
        )

    @classmethod
    def _clean_page_title(cls, title: str, browser_name: str) -> str:
        """Strips browser suffix from window title."""
        if not title:
            return ""
        # Patterns like "GitHub - Where the world builds software - Google Chrome"
        suffixes = [
            f" - {browser_name}",
            f" — {browser_name}",
            " - Personal - Microsoft Edge",
            " - Work - Microsoft Edge",
            " - Google Chrome",
            " - Microsoft Edge",
            " - Mozilla Firefox",
            " - Brave",
        ]
        res = title
        for s in suffixes:
            if res.endswith(s):
                res = res[: -len(s)].strip()
                break
        return res

    @classmethod
    def _extract_url_from_title(cls, title: str) -> Optional[str]:
        """Checks if the window title directly contains a recognizable URL."""
        if not title:
            return None
        match = re.search(r"https?://[^\s\)\"\'\,]+", title)
        if match:
            return match.group(0)
        # Check for www. or .com/.org domain in title
        m_dom = re.search(r"\b([a-zA-Z0-9-]+\.(?:com|org|net|io|gov|edu|ai|co|app)(?:/[^\s\)\"\']*)?)\b", title, re.I)
        if m_dom:
            return f"https://{m_dom.group(1)}"
        return None

    @classmethod
    def _extract_domain(cls, url: str) -> str:
        if not url:
            return ""
        try:
            parsed = urllib.parse.urlparse(url if "://" in url else f"https://{url}")
            return parsed.netloc or parsed.path.split("/")[0]
        except Exception:
            return ""

    @classmethod
    def _infer_domain_from_title(cls, title: str) -> str:
        """Infers popular web domains from title cues."""
        if not title:
            return ""
        lower = title.lower()
        mapping = {
            "github": "github.com",
            "google search": "google.com",
            "google docs": "docs.google.com",
            "google drive": "drive.google.com",
            "google classroom": "classroom.google.com",
            "youtube": "youtube.com",
            "wikipedia": "wikipedia.org",
            "stackoverflow": "stackoverflow.com",
            "stack overflow": "stackoverflow.com",
            "reddit": "reddit.com",
            "twitter": "x.com",
            "arxiv": "arxiv.org",
            "hugging face": "huggingface.co",
            "chatgpt": "chatgpt.com",
            "claude": "claude.ai",
        }
        for k, v in mapping.items():
            if k in lower:
                return v
        return ""

    @classmethod
    def _query_address_bar_via_uia(cls, hwnd: int) -> Optional[str]:
        """Queries the address bar of a browser window using PowerShell UIAutomation."""
        # PowerShell script with timeout limit
        ps_code = f"""
$ErrorActionPreference = 'SilentlyContinue'
Add-Type -AssemblyName UIAutomationClient
$elem = [System.Windows.Automation.AutomationElement]::FromHandle([IntPtr]{hwnd})
if ($elem -ne $null) {{
    $cond = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty, [System.Windows.Automation.ControlType]::Edit)
    $edits = $elem.FindAll([System.Windows.Automation.TreeScope]::Descendants, $cond)
    foreach ($e in $edits) {{
        $name = $e.Current.Name
        if ($name -match 'Address' -or $name -match 'Search' -or $e.Current.AutomationId -match 'address') {{
            $pattern = $null
            if ($e.TryGetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern, [ref]$pattern)) {{
                $val = $pattern.Current.Value
                if ($val -and $val.Length -gt 2) {{
                    Write-Output $val
                    exit 0
                }}
            }}
        }}
    }}
}}
"""
        try:
            res = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_code],
                capture_output=True,
                text=True,
                timeout=1.5,
            )
            raw = res.stdout.strip()
            if raw and not raw.startswith("Error"):
                val = raw.splitlines()[0].strip()
                if "://" not in val and "." in val:
                    val = f"https://{val}"
                return val
        except Exception:
            pass
        return None
