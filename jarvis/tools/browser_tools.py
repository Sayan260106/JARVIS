"""Playwright Browser Tools for JARVIS.

Standardized BaseTool implementations for browser automation, state inspection,
semantic DOM navigation, and document/PDF extraction.
"""

from __future__ import annotations
import os
import time
from typing import Any, Dict, Optional

from jarvis.tools.base import BaseTool, RiskLevel, ToolParameter, ToolResult, ToolVerification
from jarvis.subsystems.web.browser_controller import get_browser_controller


class BrowserOpenTool(BaseTool):
    """Launches or connects to the browser (Chrome / Edge / Chromium) with optional user profile."""
    name = "browser_open"
    description = "Launches Chrome/Edge browser with optional institutional profile or user data directory."
    risk_level = RiskLevel.LOW
    parameters = {
        "headless": ToolParameter("headless", "boolean", "Run in background headless mode (default: True).", required=False, default=True),
        "channel": ToolParameter("channel", "string", "Browser channel ('chrome' or 'msedge').", required=False, default="chrome"),
        "profile_name": ToolParameter("profile_name", "string", "Profile name or alias (e.g. 'institutional', 'Default', 'Profile 1').", required=False),
        "user_data_dir": ToolParameter("user_data_dir", "string", "Optional Chrome user data directory path.", required=False),
        "use_persistent": ToolParameter("use_persistent", "boolean", "Use persistent browser context preserving logins.", required=False, default=False),
    }

    def execute(
        self,
        headless: bool = True,
        channel: str = "chrome",
        profile_name: Optional[str] = None,
        user_data_dir: Optional[str] = None,
        use_persistent: bool = False,
        **kwargs,
    ) -> ToolResult:
        start_t = time.perf_counter()
        try:
            ctrl = get_browser_controller()
            out = ctrl.open(
                headless=headless,
                channel=channel,
                profile_name=profile_name,
                user_data_dir=user_data_dir,
                use_persistent=use_persistent,
            )
            return ToolResult(success=True, output=out, duration_ms=(time.perf_counter() - start_t) * 1000)
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e), duration_ms=(time.perf_counter() - start_t) * 1000)

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        return ToolVerification(verified=result.success, details="Browser session active." if result.success else result.error)


class BrowserGetStateTool(BaseTool):
    """Retrieves full, structured browser state (URL, open tabs, visible elements, auth state)."""
    name = "browser_get_state"
    description = "Captures real-time browser state: active URL, page title, open tabs, visible semantic elements, and login state."
    risk_level = RiskLevel.LOW
    parameters = {}

    def execute(self, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        try:
            ctrl = get_browser_controller()
            out = ctrl.get_state()
            return ToolResult(success=True, output=out, duration_ms=(time.perf_counter() - start_t) * 1000)
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e), duration_ms=(time.perf_counter() - start_t) * 1000)

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        if not result.success:
            return ToolVerification(verified=False, details=f"Failed to get browser state: {result.error}")
        return ToolVerification(verified=True, details=f"State captured: '{result.output.get('title')}' ({result.output.get('url')}).")


class BrowserInspectDOMTool(BaseTool):
    """Inspects visible accessible elements on page without pixel coordinates."""
    name = "browser_inspect_dom"
    description = "Inspects visible DOM interactive elements (links, buttons, course cards, headings) matching an optional text query."
    risk_level = RiskLevel.LOW
    parameters = {
        "query": ToolParameter("query", "string", "Optional search filter (e.g. 'ECE', 'Lecture', 'Classroom').", required=False),
        "max_elements": ToolParameter("max_elements", "integer", "Maximum elements to return (default: 30).", required=False, default=30),
    }

    def execute(self, query: Optional[str] = None, max_elements: int = 30, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        try:
            ctrl = get_browser_controller()
            out = ctrl.inspect_dom(query=query, max_elements=max_elements)
            return ToolResult(success=True, output=out, duration_ms=(time.perf_counter() - start_t) * 1000)
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e), duration_ms=(time.perf_counter() - start_t) * 1000)

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        return ToolVerification(verified=result.success, details=f"Found {result.output.get('count', 0)} matching elements.")


class BrowserManageTabsTool(BaseTool):
    """Manages browser tabs (list, switch, new, close)."""
    name = "browser_manage_tabs"
    description = "Manages browser tabs: 'list', 'switch' (by index), 'new' (with URL), or 'close'."
    risk_level = RiskLevel.LOW
    parameters = {
        "action": ToolParameter("action", "string", "Tab action: 'list', 'switch', 'new', or 'close'.", required=True),
        "index": ToolParameter("index", "integer", "Target tab index (required for 'switch' and 'close').", required=False),
        "url": ToolParameter("url", "string", "Initial URL (optional for 'new').", required=False),
    }

    def execute(self, action: str, index: Optional[int] = None, url: Optional[str] = None, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        ctrl = get_browser_controller()
        act = action.strip().lower()

        try:
            if act == "list":
                tabs = ctrl.list_tabs()
                return ToolResult(success=True, output={"tabs": tabs, "count": len(tabs)}, duration_ms=(time.perf_counter() - start_t) * 1000)
            elif act == "switch":
                if index is None:
                    return ToolResult(success=False, output=None, error="Missing required 'index' for switch action.", duration_ms=(time.perf_counter() - start_t) * 1000)
                out = ctrl.switch_tab(index=index)
                return ToolResult(success=out.get("status") == "switched", output=out, duration_ms=(time.perf_counter() - start_t) * 1000)
            elif act == "new":
                out = ctrl.new_tab(url=url)
                return ToolResult(success=True, output=out, duration_ms=(time.perf_counter() - start_t) * 1000)
            elif act == "close":
                out = ctrl.close_tab(index=index)
                return ToolResult(success=True, output=out, duration_ms=(time.perf_counter() - start_t) * 1000)
            else:
                return ToolResult(success=False, output=None, error=f"Unknown tab action '{action}'.", duration_ms=(time.perf_counter() - start_t) * 1000)
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e), duration_ms=(time.perf_counter() - start_t) * 1000)

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        return ToolVerification(verified=result.success, details=f"Tab action '{arguments['action']}' completed.")


class BrowserNavigateTool(BaseTool):
    """Navigates active browser tab to a specified URL."""
    name = "browser_navigate"
    description = "Navigates current browser tab to a specified URL (e.g. 'https://classroom.google.com')."
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
    """Clicks an element on the webpage by selector or text content."""
    name = "browser_click"
    description = "Clicks a link, button, or card on the page using text matching or a CSS selector (e.g. 'ECE', 'Classroom')."
    risk_level = RiskLevel.MEDIUM
    parameters = {
        "selector": ToolParameter("selector", "string", "Target text or CSS selector (e.g. 'ECE', 'text=Google Classroom', 'button.submit').", required=True),
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
        "selector": ToolParameter("selector", "string", "CSS selector or placeholder for input field.", required=True),
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
        return ToolVerification(verified=result.success, details=f"Typed text into '{arguments['selector']}'.")


class BrowserSelectTool(BaseTool):
    """Selects an option from a dropdown element."""
    name = "browser_select"
    description = "Selects an option in a dropdown select element by value or visible label."
    risk_level = RiskLevel.LOW
    parameters = {
        "selector": ToolParameter("selector", "string", "CSS selector for select element.", required=True),
        "value": ToolParameter("value", "string", "Option value or label to select.", required=True),
    }

    def execute(self, selector: str, value: str, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        try:
            ctrl = get_browser_controller()
            out = ctrl.select_option(selector=selector, value_or_label=value)
            return ToolResult(success=True, output=out, duration_ms=(time.perf_counter() - start_t) * 1000)
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e), duration_ms=(time.perf_counter() - start_t) * 1000)

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        return ToolVerification(verified=result.success, details=f"Selected option '{arguments['value']}'.")


class BrowserUploadTool(BaseTool):
    """Uploads a local file to a file input on the webpage."""
    name = "browser_upload"
    description = "Uploads a local file to a file input field on the page."
    risk_level = RiskLevel.MEDIUM
    parameters = {
        "selector": ToolParameter("selector", "string", "CSS selector for file input.", required=True),
        "file_path": ToolParameter("file_path", "string", "Path to local file to upload.", required=True),
    }

    def execute(self, selector: str, file_path: str, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        try:
            ctrl = get_browser_controller()
            out = ctrl.upload_file(selector=selector, file_path=file_path)
            return ToolResult(success=True, output=out, duration_ms=(time.perf_counter() - start_t) * 1000)
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e), duration_ms=(time.perf_counter() - start_t) * 1000)

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        return ToolVerification(verified=result.success, details=f"File uploaded to '{arguments['selector']}'.")


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


class BrowserDetectPDFsTool(BaseTool):
    """Detects course lecture PDFs, documents, and Classroom attachments."""
    name = "browser_detect_pdfs"
    description = "Scans page for downloadable PDF files, lecture notes, or Google Classroom attachment links."
    risk_level = RiskLevel.LOW
    parameters = {
        "query": ToolParameter("query", "string", "Optional search term for lectures (e.g. 'Lecture 3', 'ECE').", required=False),
    }

    def execute(self, query: Optional[str] = None, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        try:
            ctrl = get_browser_controller()
            out = ctrl.detect_pdfs(query=query)
            return ToolResult(success=True, output=out, duration_ms=(time.perf_counter() - start_t) * 1000)
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e), duration_ms=(time.perf_counter() - start_t) * 1000)

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        count = result.output.get("count", 0) if result.success else 0
        return ToolVerification(verified=result.success, details=f"Detected {count} document/PDF material(s).")


class BrowserDetectSessionTool(BaseTool):
    """Detects active login and authentication state for Google, Classroom, or institutional accounts."""
    name = "browser_detect_session"
    description = "Detects whether active authentication session exists for Google Classroom or institutional profile."
    risk_level = RiskLevel.LOW
    parameters = {
        "service": ToolParameter("service", "string", "Target service name hint (e.g. 'google', 'classroom').", required=False),
    }

    def execute(self, service: Optional[str] = None, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        try:
            ctrl = get_browser_controller()
            out = ctrl.detect_session(service_hint=service)
            return ToolResult(success=True, output=out, duration_ms=(time.perf_counter() - start_t) * 1000)
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e), duration_ms=(time.perf_counter() - start_t) * 1000)

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        logged_in = result.output.get("logged_in", False) if result.success else False
        status = "Active login session verified" if logged_in else "Session requires login"
        return ToolVerification(verified=result.success, details=status)


class BrowserDownloadTool(BaseTool):
    """Downloads a file (e.g. PDF lecture notes) from a URL to a local destination."""
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


class BrowserVerifyPDFTool(BaseTool):
    """Verifies that a downloaded document exists on disk and has valid %PDF magic bytes."""
    name = "browser_verify_pdf"
    description = "Verifies file exists on disk, is non-empty, and possesses valid %PDF header magic bytes."
    risk_level = RiskLevel.LOW
    parameters = {
        "file_path": ToolParameter("file_path", "string", "Path of downloaded PDF file to verify.", required=True),
    }

    def execute(self, file_path: str, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        try:
            ctrl = get_browser_controller()
            out = ctrl.verify_pdf(file_path=file_path)
            return ToolResult(success=out.get("verified", False), output=out, error=out.get("reason") if not out.get("verified") else None, duration_ms=(time.perf_counter() - start_t) * 1000)
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e), duration_ms=(time.perf_counter() - start_t) * 1000)

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        return ToolVerification(verified=result.success, details=result.output.get("reason", "") if result.success else str(result.error))


class BrowserVerifyNavigationTool(BaseTool):
    """Verifies current tab URL and title match expected patterns."""
    name = "browser_verify_navigation"
    description = "Verifies active webpage URL and/or title match specified regular expressions or substrings."
    risk_level = RiskLevel.LOW
    parameters = {
        "url_pattern": ToolParameter("url_pattern", "string", "Expected URL pattern (regex or substring).", required=False),
        "title_pattern": ToolParameter("title_pattern", "string", "Expected Title pattern (regex or substring).", required=False),
    }

    def execute(self, url_pattern: Optional[str] = None, title_pattern: Optional[str] = None, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        try:
            ctrl = get_browser_controller()
            out = ctrl.verify_navigation(url_pattern=url_pattern, title_pattern=title_pattern)
            return ToolResult(success=out.get("verified", False), output=out, duration_ms=(time.perf_counter() - start_t) * 1000)
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e), duration_ms=(time.perf_counter() - start_t) * 1000)

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        return ToolVerification(verified=result.success, details=result.output.get("reason", "") if result.success else str(result.error))


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
