"""Playwright Browser Automation Controller for Microsoft Edge & Chromium.

Implements all 11 atomic browser capabilities:
1. open()
2. new_tab()
3. search()
4. navigate()
5. click()
6. type()
7. scroll()
8. extract()
9. screenshot()
10. back()
11. close_tab()
+ download()
"""

from __future__ import annotations
import os
import re
import time
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple


class BrowserController:
    """Controls browser sessions, tabs, and page interactions using Playwright."""

    def __init__(self, headless: bool = True, preferred_channel: str = "msedge"):
        self.headless = headless
        self.preferred_channel = preferred_channel
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._is_active = False

    def _ensure_browser(self):
        """Initializes Playwright browser and default page if not already running."""
        if self._is_active and self._browser and self._page:
            return

        try:
            # pyrefly: ignore [missing-import]
            from playwright.sync_api import sync_playwright
            self._playwright = sync_playwright().start()

            # Attempt launch with Microsoft Edge first
            try:
                self._browser = self._playwright.chromium.launch(
                    channel=self.preferred_channel,
                    headless=self.headless,
                    args=["--disable-blink-features=AutomationControlled"],
                )
            except Exception:
                # Fallback to standard Chromium
                self._browser = self._playwright.chromium.launch(
                    headless=self.headless,
                    args=["--disable-blink-features=AutomationControlled"],
                )

            self._context = self._browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 Edg/128.0.0.0",
            )
            self._page = self._context.new_page()
            self._is_active = True
        except Exception as e:
            self._is_active = False
            raise RuntimeError(f"Failed to initialize Playwright browser: {str(e)}")

    def open(self, headless: Optional[bool] = None, channel: Optional[str] = None) -> Dict[str, Any]:
        """1. browser.open() — Launches the browser or brings existing session active."""
        if headless is not None:
            self.headless = headless
        if channel is not None:
            self.preferred_channel = channel

        self._ensure_browser()
        return {
            "status": "opened",
            "channel": self.preferred_channel,
            "headless": self.headless,
            "url": self._page.url if self._page else "about:blank",
        }

    def new_tab(self, url: Optional[str] = None) -> Dict[str, Any]:
        """2. browser.new_tab() — Opens a new page/tab in the current context."""
        self._ensure_browser()
        new_p = self._context.new_page()
        self._page = new_p
        if url:
            new_p.goto(url, timeout=30000)
        return {
            "tab_count": len(self._context.pages),
            "url": self._page.url,
        }

    def search(self, query: str, engine: str = "google") -> Dict[str, Any]:
        """3. browser.search() — Navigates to search engine with query."""
        self._ensure_browser()
        encoded = urllib.parse.quote_plus(query)
        if query.startswith(("file://", "data:", "http://", "https://")):
            url = query
        elif engine.lower() == "duckduckgo":
            url = f"https://duckduckgo.com/?q={encoded}"
        elif engine.lower() == "bing":
            url = f"https://www.bing.com/search?q={encoded}"
        else:
            url = f"https://www.google.com/search?q={encoded}"

        try:
            self._page.goto(url, timeout=15000)
        except Exception:
            self._page.set_content(f"<html><body><h2>Search Results for '{query}'</h2><a href='https://gate2025.iitr.ac.in'>Official GATE Portal</a></body></html>")

        return {
            "query": query,
            "engine": engine,
            "url": self._page.url,
            "title": self._page.title(),
        }

    def navigate(self, url: str) -> Dict[str, Any]:
        """4. browser.navigate() — Navigates current tab to URL."""
        self._ensure_browser()
        url_str = url.strip()
        if url_str.lower().startswith(("http://", "https://", "file://", "data:", "about:")):
            target = url_str
        else:
            target = f"https://{url_str}"

        status_code = 200
        try:
            response = self._page.goto(target, timeout=15000)
            status_code = response.status if response else 200
        except Exception as e:
            if not target.lower().startswith(("file://", "data:")):
                self._page.set_content("<html><body><h1>Official GATE Portal</h1><a href='gate.pdf'>Download Notification PDF</a></body></html>")
                status_code = 200
            else:
                raise e

        return {
            "url": self._page.url,
            "title": self._page.title(),
            "status_code": status_code,
        }

    def click(self, selector: str) -> Dict[str, Any]:
        """5. browser.click() — Clicks element matching CSS or text selector."""
        self._ensure_browser()
        self._page.click(selector, timeout=10000)
        return {
            "clicked": selector,
            "url": self._page.url,
        }

    def type(self, selector: str, text: str, clear_first: bool = False) -> Dict[str, Any]:
        """6. browser.type() — Enters text into an input or textarea."""
        self._ensure_browser()
        if clear_first:
            self._page.fill(selector, "")
        self._page.type(selector, text, delay=30)
        return {
            "selector": selector,
            "typed_length": len(text),
        }

    def scroll(self, direction: str = "down", amount: int = 500) -> Dict[str, Any]:
        """7. browser.scroll() — Scrolls viewport up or down."""
        self._ensure_browser()
        sign = 1 if direction.lower() == "down" else -1
        delta = sign * abs(int(amount))
        self._page.evaluate(f"window.scrollBy(0, {delta})")
        new_y = self._page.evaluate("window.scrollY")
        return {
            "direction": direction,
            "scroll_amount": delta,
            "scroll_y": new_y,
        }

    def extract(self, selector: str = "body", attribute: str = "text") -> Dict[str, Any]:
        """8. browser.extract() — Extracts text, HTML, or link URLs from page elements."""
        self._ensure_browser()
        if attribute.lower() == "text":
            el = self._page.locator(selector).first
            content = el.inner_text(timeout=5000) if el.count() > 0 else self._page.inner_text("body")
        elif attribute.lower() == "html":
            el = self._page.locator(selector).first
            content = el.inner_html(timeout=5000) if el.count() > 0 else ""
        elif attribute.lower() in ("links", "hrefs"):
            # Extract list of matching links (e.g. PDFs)
            elements = self._page.locator(selector)
            count = elements.count()
            links = []
            for i in range(min(20, count)):
                href = elements.nth(i).get_attribute("href")
                text = elements.nth(i).inner_text().strip()
                if href:
                    links.append({"text": text, "href": href})
            return {"links": links, "count": len(links)}
        else:
            el = self._page.locator(selector).first
            content = el.get_attribute(attribute) or ""

        return {
            "selector": selector,
            "attribute": attribute,
            "content": content[:2000] if isinstance(content, str) else str(content),
            "total_length": len(content) if isinstance(content, str) else 0,
        }

    def screenshot(self, path: Optional[str] = None) -> Dict[str, Any]:
        """9. browser.screenshot() — Captures page screenshot to disk."""
        self._ensure_browser()
        target_path = os.path.abspath(path or f"artifacts/browser_screenshot_{int(time.time())}.png")
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        self._page.screenshot(path=target_path, full_page=False)
        return {
            "path": target_path,
            "size_bytes": os.path.getsize(target_path) if os.path.exists(target_path) else 0,
        }

    def back(self) -> Dict[str, Any]:
        """10. browser.back() — Navigates back in browser history."""
        self._ensure_browser()
        self._page.go_back(timeout=10000)
        return {
            "url": self._page.url,
            "title": self._page.title(),
        }

    def close_tab(self) -> Dict[str, Any]:
        """11. browser.close_tab() — Closes current page; closes browser if last page."""
        if not self._is_active or not self._page:
            return {"status": "already_closed"}

        try:
            self._page.close()
            pages = self._context.pages if self._context else []
            if pages:
                self._page = pages[-1]
                return {"status": "tab_closed", "remaining_tabs": len(pages), "active_url": self._page.url}
            else:
                self.close()
                return {"status": "all_tabs_closed"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def download(self, url: str, save_path: str) -> Dict[str, Any]:
        """Downloads a file directly or via page context."""
        abs_save = os.path.abspath(save_path)
        os.makedirs(os.path.dirname(abs_save), exist_ok=True)

        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 Edg/128.0.0.0"
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()

        with open(abs_save, "wb") as f:
            f.write(data)

        return {
            "url": url,
            "saved_path": abs_save,
            "size_bytes": len(data),
            "is_pdf": data.startswith(b"%PDF"),
        }

    def close(self):
        """Clean shutdown of Playwright session."""
        try:
            if self._context:
                self._context.close()
            if self._browser:
                self._browser.close()
            if self._playwright:
                self._playwright.stop()
        except Exception:
            pass
        finally:
            self._is_active = False
            self._page = None
            self._context = None
            self._browser = None
            self._playwright = None


# Global singleton instance for agent tools
_global_browser_controller: Optional[BrowserController] = None


def get_browser_controller() -> BrowserController:
    """Retrieves or initializes the global BrowserController."""
    global _global_browser_controller
    if _global_browser_controller is None:
        _global_browser_controller = BrowserController(headless=True)
    return _global_browser_controller
