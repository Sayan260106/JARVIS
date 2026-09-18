"""Browser Lifecycle Manager and Chrome Profile Resolver for JARVIS.

Manages Chrome and Chromium browser instances, profile detection (e.g. institutional profiles),
persistent sessions, and Playwright lifecycle control.
"""

from __future__ import annotations
import json
import os
import pathlib
import platform
import shutil
from typing import Any, Dict, List, Optional, Tuple


class ChromeProfileResolver:
    """Discovers and resolves Google Chrome and Chromium user profiles on Windows."""

    @classmethod
    def get_chrome_user_data_dir(cls) -> str:
        """Returns the default Chrome User Data directory on Windows."""
        return os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data")

    @classmethod
    def list_profiles(cls, user_data_dir: Optional[str] = None) -> List[Dict[str, Any]]:
        """Enumerates all configured Chrome profiles by inspecting Local State."""
        data_dir = user_data_dir or cls.get_chrome_user_data_dir()
        local_state_path = os.path.join(data_dir, "Local State")

        if not os.path.exists(local_state_path):
            return []

        try:
            with open(local_state_path, "r", encoding="utf-8", errors="ignore") as f:
                state_data = json.load(f)

            info_cache = state_data.get("profile", {}).get("info_cache", {})
            profiles = []

            for dir_name, p_info in info_cache.items():
                name = p_info.get("name", "")
                user_name = p_info.get("user_name", "")  # Often the Google account email
                is_ephemeral = p_info.get("is_ephemeral", False)

                # Heuristic for institutional or academic accounts
                email_lower = user_name.lower()
                is_institutional = any(
                    domain in email_lower or domain in name.lower()
                    for domain in [".edu", ".ac.in", ".edu.in", "heritageit", "university", "college", "school", "inst"]
                )

                profiles.append({
                    "directory_name": dir_name,
                    "name": name,
                    "email": user_name,
                    "is_institutional": is_institutional,
                    "is_ephemeral": is_ephemeral,
                    "full_path": os.path.join(data_dir, dir_name),
                })

            return profiles
        except Exception:
            return []

    @classmethod
    def resolve_profile(cls, query: str, user_data_dir: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Resolves natural language queries like 'institutional', 'college', 'heritageit', or an email.

        Returns matching profile metadata dictionary or None if not found.
        """
        profiles = cls.list_profiles(user_data_dir=user_data_dir)
        if not profiles:
            return None

        clean = query.strip().lower()

        # 1. Check for institutional / college query
        if clean in ("institutional", "college", "university", "academic", "institution"):
            for p in profiles:
                if p["is_institutional"]:
                    return p

        # 2. Check exact directory match (e.g. 'Default', 'Profile 1')
        for p in profiles:
            if p["directory_name"].lower() == clean:
                return p

        # 3. Check name or email match
        for p in profiles:
            if clean in p["name"].lower() or clean in p["email"].lower():
                return p

        return None


class BrowserLifecycleManager:
    """Manages browser process lifecycle, persistent contexts, and Playwright session cleanup."""

    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.active_page = None
        self.active_profile: Optional[Dict[str, Any]] = None
        self.is_persistent: bool = False
        self.user_data_dir: Optional[str] = None

    def launch(
        self,
        headless: bool = True,
        channel: str = "chrome",
        profile_name: Optional[str] = None,
        user_data_dir: Optional[str] = None,
        use_persistent: bool = False,
    ) -> Dict[str, Any]:
        """Launches a browser session with optional Chrome profile and persistence."""
        from playwright.sync_api import sync_playwright

        if self.active_page and self.context:
            return {
                "status": "already_active",
                "channel": channel,
                "profile": self.active_profile.get("directory_name") if self.active_profile else None,
                "url": self.active_page.url,
            }

        self.playwright = sync_playwright().start()

        # Resolve profile if requested
        profile_meta = None
        if profile_name:
            profile_meta = ChromeProfileResolver.resolve_profile(profile_name, user_data_dir=user_data_dir)
            self.active_profile = profile_meta

        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--no-first-run",
            "--no-default-browser-check",
        ]

        if profile_meta and profile_meta.get("directory_name"):
            launch_args.append(f"--profile-directory={profile_meta['directory_name']}")

        # Persistent context launch (preserves cookies, session, local storage)
        if use_persistent and user_data_dir:
            self.is_persistent = True
            self.user_data_dir = user_data_dir
            try:
                self.context = self.playwright.chromium.launch_persistent_context(
                    user_data_dir=user_data_dir,
                    channel=channel if channel in ("chrome", "msedge") else None,
                    headless=headless,
                    args=launch_args,
                    viewport={"width": 1280, "height": 800},
                )
                self.active_page = self.context.pages[0] if self.context.pages else self.context.new_page()
            except Exception as e:
                # If profile directory is locked by another running Chrome instance, fall back to standard launch
                self.is_persistent = False
                self._launch_standard(headless, channel, launch_args)
        else:
            self.is_persistent = False
            self._launch_standard(headless, channel, launch_args)

        return {
            "status": "launched",
            "channel": channel,
            "profile": profile_meta.get("directory_name") if profile_meta else None,
            "profile_email": profile_meta.get("email") if profile_meta else None,
            "headless": headless,
            "persistent": self.is_persistent,
            "url": self.active_page.url if self.active_page else "about:blank",
        }

    def _launch_standard(self, headless: bool, channel: str, launch_args: List[str]):
        """Launches standard browser and creates context."""
        try:
            self.browser = self.playwright.chromium.launch(
                channel=channel if channel in ("chrome", "msedge") else None,
                headless=headless,
                args=launch_args,
            )
        except Exception:
            # Fallback to default chromium
            self.browser = self.playwright.chromium.launch(
                headless=headless,
                args=launch_args,
            )

        self.context = self.browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        )
        self.active_page = self.context.new_page()

    def shutdown(self):
        """Clean shutdown of browser context and Playwright runtime."""
        try:
            if self.context:
                self.context.close()
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
        except Exception:
            pass
        finally:
            self.active_page = None
            self.context = None
            self.browser = None
            self.playwright = None
            self.active_profile = None
            self.is_persistent = False
