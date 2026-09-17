"""Playwright Browser Tools for JARVIS.

Standardized BaseTool implementations for browser manipulation.
"""

from __future__ import annotations
import os
import time
from typing import Any, Dict, Optional

from jarvis.tools.base import BaseTool, RiskLevel, ToolParameter, ToolResult, ToolVerification
from jarvis.subsystems.web.browser_controller import get_browser_controller


class BrowserOpenTool(BaseTool):
    """Launches or connects to the browser (Microsoft Edge/Chromium)."""
    name = "browser_open"
    description = "Launches Microsoft Edge browser using Playwright."
    risk_level = RiskLevel.LOW
    parameters = {
        "headless": ToolParameter("headless", "boolean", "Run in background headless mode (default: True).", required=False, default=True),
        "channel": ToolParameter("channel", "string", "Browser channel ('msedge' or 'chromium').", required=False, default="msedge"),
    }

    def execute(self, headless: bool = True, channel: str = "msedge", **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        try:
            ctrl = get_browser_controller()
            out = ctrl.open(headless=headless, channel=channel)
            return ToolResult(success=True, output=out, duration_ms=(time.perf_counter() - start_t) * 1000)
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e), duration_ms=(time.perf_counter() - start_t) * 1000)

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        return ToolVerification(verified=result.success, details="Browser session active." if result.success else result.error)


class BrowserNewTabTool(BaseTool):
    """Opens a new tab/page in the active browser session."""
    name = "browser_new_tab"
    description = "Opens a new browser tab/page, optionally navigating to an initial URL."
    risk_level = RiskLevel.LOW
    parameters = {
        "url": ToolParameter("url", "string", "Initial URL for new tab.", required=False),
    }

    def execute(self, url: Optional[str] = None, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        try:
            ctrl = get_browser_controller()
            out = ctrl.new_tab(url=url)
            return ToolResult(success=True, output=out, duration_ms=(time.perf_counter() - start_t) * 1000)
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e), duration_ms=(time.perf_counter() - start_t) * 1000)

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        return ToolVerification(verified=result.success, details=f"Active tabs: {result.output.get('tab_count') if result.success else 0}")


class BrowserSearchPageTool(BaseTool):
    """Searches using browser page navigation."""
    name = "browser_search_page"
    description = "Performs a web search inside the browser tab using Google, Bing, or DuckDuckGo."
    risk_level = RiskLevel.LOW
    parameters = {
        "query": ToolParameter("query", "string", "Search query terms.", required=True),
        "engine": ToolParameter("engine", "string", "Search engine (google, bing, duckduckgo).", required=False, default="google"),
    }

    def execute(self, query: str, engine: str = "google", **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        try:
            ctrl = get_browser_controller()
            out = ctrl.search(query=query, engine=engine)
            return ToolResult(success=True, output=out, duration_ms=(time.perf_counter() - start_t) * 1000)
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e), duration_ms=(time.perf_counter() - start_t) * 1000)

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        return ToolVerification(verified=result.success, details=f"Search loaded: {result.output.get('title') if result.success else result.error}")


class BrowserNavigateTool(BaseTool):
    """Navigates active browser tab to a specified URL."""
    name = "browser_navigate"
    description = "Navigates current browser tab to a specified URL."
    risk_level = RiskLevel.LOW
    parameters = {
        "url": ToolParameter("url", "string", "Destination web address.", required=True),
    }

    def execute(self, url: str, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        try:
            ctrl = get_browser_controller()
            out = ctrl.navigate(url=url)
            return ToolResult(success=True, output=out, duration_ms=(time.perf_counter() - start_t) * 1000)
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e), duration_ms=(time.perf_counter() - start_t) * 1000)

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        return ToolVerification(verified=result.success, details=f"Navigated to '{result.output.get('url') if result.success else result.error}'.")


class BrowserClickTool(BaseTool):
    """Clicks an element on the webpage."""
    name = "browser_click"
    description = "Clicks a link, button, or element on the page using a CSS or text selector."
    risk_level = RiskLevel.MEDIUM
    parameters = {
        "selector": ToolParameter("selector", "string", "CSS selector or text to click (e.g. 'a.download', 'text=Official Notification').", required=True),
    }

    def execute(self, selector: str, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        try:
            ctrl = get_browser_controller()
            out = ctrl.click(selector=selector)
            return ToolResult(success=True, output=out, duration_ms=(time.perf_counter() - start_t) * 1000)
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e), duration_ms=(time.perf_counter() - start_t) * 1000)

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        return ToolVerification(verified=result.success, details=f"Clicked '{arguments['selector']}'.")


class BrowserTypeTool(BaseTool):
    """Types text into an input field on the page."""
    name = "browser_type"
    description = "Types text into a form input field or search bar on the active page."
    risk_level = RiskLevel.LOW
    parameters = {
        "selector": ToolParameter("selector", "string", "CSS selector for input field.", required=True),
        "text": ToolParameter("text", "string", "Text string to type.", required=True),
        "clear_first": ToolParameter("clear_first", "boolean", "Clear existing text before typing.", required=False, default=False),
    }

    def execute(self, selector: str, text: str, clear_first: bool = False, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        try:
            ctrl = get_browser_controller()
            out = ctrl.type(selector=selector, text=text, clear_first=clear_first)
            return ToolResult(success=True, output=out, duration_ms=(time.perf_counter() - start_t) * 1000)
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e), duration_ms=(time.perf_counter() - start_t) * 1000)

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        return ToolVerification(verified=result.success, details=f"Typed {arguments.get('text')} into '{arguments['selector']}'.")


class BrowserScrollTool(BaseTool):
    """Scrolls the page up or down."""
    name = "browser_scroll"
    description = "Scrolls current page up or down by a given pixel delta."
    risk_level = RiskLevel.LOW
    parameters = {
        "direction": ToolParameter("direction", "string", "'down' or 'up'.", required=False, default="down"),
        "amount": ToolParameter("amount", "integer", "Pixel scroll delta (default: 500).", required=False, default=500),
    }

    def execute(self, direction: str = "down", amount: int = 500, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        try:
            ctrl = get_browser_controller()
            out = ctrl.scroll(direction=direction, amount=amount)
            return ToolResult(success=True, output=out, duration_ms=(time.perf_counter() - start_t) * 1000)
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e), duration_ms=(time.perf_counter() - start_t) * 1000)

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        return ToolVerification(verified=result.success, details=f"Scrolled {arguments.get('direction', 'down')}.")


class BrowserExtractTool(BaseTool):
    """Extracts text, HTML, or links from the page."""
    name = "browser_extract"
    description = "Extracts text content, HTML, or list of link URLs (e.g. PDF documents) from the active webpage."
    risk_level = RiskLevel.LOW
    parameters = {
        "selector": ToolParameter("selector", "string", "CSS selector to target (default: 'body').", required=False, default="body"),
        "attribute": ToolParameter("attribute", "string", "'text', 'html', or 'links'.", required=False, default="text"),
    }

    def execute(self, selector: str = "body", attribute: str = "text", **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        try:
            ctrl = get_browser_controller()
            out = ctrl.extract(selector=selector, attribute=attribute)
            return ToolResult(success=True, output=out, duration_ms=(time.perf_counter() - start_t) * 1000)
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e), duration_ms=(time.perf_counter() - start_t) * 1000)

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        return ToolVerification(verified=result.success, details="Extracted page content successfully." if result.success else result.error)


class BrowserScreenshotTool(BaseTool):
    """Captures a screenshot of the current page."""
    name = "browser_screenshot"
    description = "Captures a full or viewport screenshot of the current webpage to an image file."
    risk_level = RiskLevel.LOW
    parameters = {
        "path": ToolParameter("path", "string", "Destination file path for image.", required=False),
    }

    def execute(self, path: Optional[str] = None, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        try:
            ctrl = get_browser_controller()
            out = ctrl.screenshot(path=path)
            return ToolResult(success=True, output=out, duration_ms=(time.perf_counter() - start_t) * 1000)
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e), duration_ms=(time.perf_counter() - start_t) * 1000)

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        return ToolVerification(verified=result.success, details=f"Screenshot saved to {result.output.get('path') if result.success else result.error}")


class BrowserBackTool(BaseTool):
    """Navigates back in browser history."""
    name = "browser_back"
    description = "Navigates back one step in browser tab history."
    risk_level = RiskLevel.LOW
    parameters = {}

    def execute(self, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        try:
            ctrl = get_browser_controller()
            out = ctrl.back()
            return ToolResult(success=True, output=out, duration_ms=(time.perf_counter() - start_t) * 1000)
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e), duration_ms=(time.perf_counter() - start_t) * 1000)

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        return ToolVerification(verified=result.success, details="Navigated back.")


class BrowserCloseTabTool(BaseTool):
    """Closes current tab or browser."""
    name = "browser_close_tab"
    description = "Closes current browser tab or ends browser session."
    risk_level = RiskLevel.LOW
    parameters = {}

    def execute(self, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        try:
            ctrl = get_browser_controller()
            out = ctrl.close_tab()
            return ToolResult(success=True, output=out, duration_ms=(time.perf_counter() - start_t) * 1000)
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e), duration_ms=(time.perf_counter() - start_t) * 1000)

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        return ToolVerification(verified=result.success, details="Tab closed.")


class BrowserDownloadTool(BaseTool):
    """Downloads a file (e.g. PDF notification) from a URL to a local destination."""
    name = "browser_download"
    description = "Downloads a file or document from a web URL and saves it to local disk."
    risk_level = RiskLevel.MEDIUM
    parameters = {
        "url": ToolParameter("url", "string", "URL of document to download.", required=True),
        "save_path": ToolParameter("save_path", "string", "Local path to save downloaded file.", required=True),
    }

    def execute(self, url: str, save_path: str, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        try:
            ctrl = get_browser_controller()
            out = ctrl.download(url=url, save_path=save_path)
            return ToolResult(success=True, output=out, duration_ms=(time.perf_counter() - start_t) * 1000)
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e), duration_ms=(time.perf_counter() - start_t) * 1000)

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        if not result.success:
            return ToolVerification(verified=False, details=f"Download failed: {result.error}")
        p = result.output.get("saved_path", "")
        exists = os.path.exists(p)
        size = result.output.get("size_bytes", 0)
        return ToolVerification(verified=exists and size > 0, details=f"File saved ({size} bytes) to '{p}'.")
