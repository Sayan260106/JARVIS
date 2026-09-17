"""Web Intelligence Tools for JARVIS.

Implements web search and browser interactions.
"""

from __future__ import annotations
import time
import urllib.parse
import webbrowser
from typing import Any, Dict
from jarvis.tools.base import BaseTool, RiskLevel, ToolParameter, ToolResult, ToolVerification


class BrowserSearchTool(BaseTool):
    """Searches the web via default browser or URL generator."""
    name = "browser_search"
    description = "Searches the web using a search engine query and optionally opens the browser."
    risk_level = RiskLevel.LOW
    parameters = {
        "query": ToolParameter("query", "string", "Search terms or keywords.", required=True),
        "open_in_browser": ToolParameter("open_in_browser", "boolean", "Open search in default system web browser.", required=False, default=False),
        "engine": ToolParameter("engine", "string", "Search engine to use (google, duckduckgo, bing).", required=False, default="google"),
    }

    def execute(self, query: str, open_in_browser: bool = False, engine: str = "google", **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        encoded = urllib.parse.quote_plus(query)

        if engine.lower() == "duckduckgo":
            url = f"https://duckduckgo.com/?q={encoded}"
        elif engine.lower() == "bing":
            url = f"https://www.bing.com/search?q={encoded}"
        else:
            url = f"https://www.google.com/search?q={encoded}"

        opened = False
        if open_in_browser:
            try:
                opened = webbrowser.open(url)
            except Exception as e:
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"Failed to open browser: {e}",
                    duration_ms=(time.perf_counter() - start_t) * 1000,
                )

        return ToolResult(
            success=True,
            output={"query": query, "url": url, "browser_opened": opened},
            duration_ms=(time.perf_counter() - start_t) * 1000,
        )

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        if not result.success:
            return ToolVerification(verified=False, details=f"Browser search failed: {result.error}")
        return ToolVerification(verified=True, details=f"Search URL successfully generated: {result.output.get('url')}")
