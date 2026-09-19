"""Context Resolver for Phase 10 — Deictic Reference Resolution.

Maps ambiguous or pronoun-based user utterances ('Summarize this', 'Fix this', 'Explain this')
to concrete desktop targets and actionable content payloads using the 9-dimensional system snapshot.
"""

from __future__ import annotations
import re
from typing import Optional, Tuple

from jarvis.subsystems.context.schemas import (
    DeicticTargetType,
    ResolvedContextAction,
    SystemContextSnapshot,
)


class ContextResolver:
    """Resolves deictic pronouns ('this', 'that', 'it', 'here') against live desktop context."""

    DEICTIC_PATTERN = re.compile(
        r"\b(?:this|that|it|here|the current (?:file|document|code|page|tab|window)|what(?:'s| is) (?:this|on the screen))\b",
        re.IGNORECASE,
    )

    @classmethod
    def contains_deictic_reference(cls, text: str) -> bool:
        """Determines if the utterance relies on contextual reference."""
        return bool(cls.DEICTIC_PATTERN.search(text))

    @classmethod
    def resolve(
        cls,
        prompt: str,
        snapshot: SystemContextSnapshot,
    ) -> ResolvedContextAction:
        """Resolves a contextual query into a concrete target, content payload, and unambiguous prompt."""
        cleaned = prompt.strip()
        lower = cleaned.lower()

        # 1. SUMMARIZE PATTERNS: "Summarize this", "Give me a summary of this", "TLDR this document"
        if re.search(r"\b(?:summarize|summary|tldr|overview|digest)\b", lower):
            return cls._resolve_summarize(cleaned, snapshot)

        # 2. FIX / DEBUG PATTERNS: "Fix this", "Debug this", "Fix the bug in this", "Repair this code"
        if re.search(r"\b(?:fix|debug|refactor|repair|correct|find the bug)\b", lower):
            return cls._resolve_fix(cleaned, snapshot)

        # 3. EXPLAIN PATTERNS: "Explain this", "What does this mean?", "Explain what this is", "Clarify this"
        if re.search(r"\b(?:explain|what is this|what does this mean|describe this|clarify this|help me understand this)\b", lower):
            return cls._resolve_explain(cleaned, snapshot)

        # 4. TRANSLATE PATTERNS: "Translate this", "Translate this to Spanish"
        if re.search(r"\b(?:translate)\b", lower):
            return cls._resolve_translate(cleaned, snapshot)

        # 5. GENERAL DEICTIC FALLBACK: "What am I looking at?", "Check this", "Read this"
        return cls._resolve_general(cleaned, snapshot)

    # ------------------------------------------------------------------
    # Specialized Intent Resolvers
    # ------------------------------------------------------------------

    @classmethod
    def _resolve_summarize(
        cls, prompt: str, snapshot: SystemContextSnapshot
    ) -> ResolvedContextAction:
        """Priority: Open Document -> Browser URL -> Selected Text -> Clipboard -> Active Window."""
        # A. Open Document / File in Focus
        pof = snapshot.primary_open_file
        if pof and (pof.is_document or pof.is_code or pof.content_preview):
            resolved_prompt = (
                f"Summarize the document '{pof.file_name}' ({pof.file_path}) "
                f"currently open in {pof.source_app}."
            )
            return ResolvedContextAction(
                original_prompt=prompt,
                resolved_prompt=resolved_prompt,
                target_type=DeicticTargetType.OPEN_DOCUMENT,
                target_name=pof.file_name,
                target_path=pof.file_path,
                content_payload=pof.content_preview,
                confidence=0.95,
                explanation=f"Resolved 'this' to the active document '{pof.file_name}' in {pof.source_app}.",
                metadata={"file_path": pof.file_path, "source_app": pof.source_app},
            )

        # B. Browser Web Page
        if snapshot.browser.is_browser_active and (snapshot.browser.current_url or snapshot.browser.page_title):
            browser = snapshot.browser
            target_name = browser.page_title or browser.domain or "Web Page"
            resolved_prompt = (
                f"Summarize the web page '{target_name}' at {browser.current_url} "
                f"currently active in {browser.browser_name}."
            )
            return ResolvedContextAction(
                original_prompt=prompt,
                resolved_prompt=resolved_prompt,
                target_type=DeicticTargetType.BROWSER_PAGE,
                target_name=target_name,
                content_payload=browser.current_url,
                confidence=0.90,
                explanation=f"Resolved 'this' to the current browser page in {browser.browser_name}.",
                metadata={"url": browser.current_url, "domain": browser.domain},
            )

        # C. Selected Text
        if snapshot.selection.has_selection:
            sel = snapshot.selection
            resolved_prompt = f"Summarize the following selected text: \"{sel.text}\""
            return ResolvedContextAction(
                original_prompt=prompt,
                resolved_prompt=resolved_prompt,
                target_type=DeicticTargetType.SELECTED_TEXT,
                target_name="Selected Text",
                content_payload=sel.text,
                confidence=0.88,
                explanation=f"Resolved 'this' to {sel.char_count} characters of highlighted text in {sel.source_app}.",
                metadata={"char_count": sel.char_count, "source_app": sel.source_app},
            )

        # D. Clipboard Text
        if snapshot.clipboard.has_text and len(snapshot.clipboard.text.strip()) > 20:
            clip = snapshot.clipboard
            resolved_prompt = f"Summarize the text from the clipboard: \"{clip.text.strip()}\""
            return ResolvedContextAction(
                original_prompt=prompt,
                resolved_prompt=resolved_prompt,
                target_type=DeicticTargetType.CLIPBOARD,
                target_name="Clipboard Content",
                content_payload=clip.text,
                confidence=0.80,
                explanation="Resolved 'this' to text currently in the Windows clipboard.",
                metadata={"char_count": clip.char_count},
            )

        # E. Active Window
        win = snapshot.window
        win_title = win.title or "Active Window"
        resolved_prompt = f"Summarize the content of the active window '{win_title}' ({snapshot.application.friendly_name})."
        return ResolvedContextAction(
            original_prompt=prompt,
            resolved_prompt=resolved_prompt,
            target_type=DeicticTargetType.ACTIVE_WINDOW,
            target_name=win_title,
            confidence=0.60,
            explanation=f"Resolved 'this' to active window '{win_title}'.",
            metadata={"hwnd": win.hwnd},
        )

    @classmethod
    def _resolve_fix(
        cls, prompt: str, snapshot: SystemContextSnapshot
    ) -> ResolvedContextAction:
        """Priority: Code in VS Code/Editor -> Selected Code/Error -> Clipboard Code -> Open File."""
        pof = snapshot.primary_open_file
        app = snapshot.application

        # A. Active Editor with Open File (e.g. VS Code, PyCharm, Notepad)
        if app.is_editor and pof:
            resolved_prompt = (
                f"Fix the code and resolve any errors in '{pof.file_name}' ({pof.file_path}) "
                f"currently open in {app.friendly_name}."
            )
            return ResolvedContextAction(
                original_prompt=prompt,
                resolved_prompt=resolved_prompt,
                target_type=DeicticTargetType.CODE_IN_EDITOR,
                target_name=pof.file_name,
                target_path=pof.file_path,
                content_payload=pof.content_preview,
                confidence=0.98,
                explanation=f"Resolved 'this' to the active code file '{pof.file_name}' in {app.friendly_name}.",
                metadata={"file_path": pof.file_path, "editor": app.friendly_name, "is_code": pof.is_code},
            )

        # B. Selected Text containing code or error
        if snapshot.selection.has_selection:
            sel = snapshot.selection
            resolved_prompt = f"Fix the following selected code/error snippet: \"{sel.text}\""
            return ResolvedContextAction(
                original_prompt=prompt,
                resolved_prompt=resolved_prompt,
                target_type=DeicticTargetType.SELECTED_TEXT,
                target_name="Selected Code Snippet",
                content_payload=sel.text,
                confidence=0.92,
                explanation="Resolved 'this' to highlighted code/error in active window.",
                metadata={"char_count": sel.char_count},
            )

        # C. Any open code file detected in open_files
        for f in snapshot.open_files:
            if f.is_code:
                resolved_prompt = f"Fix the code in '{f.file_name}' ({f.file_path})."
                return ResolvedContextAction(
                    original_prompt=prompt,
                    resolved_prompt=resolved_prompt,
                    target_type=DeicticTargetType.CODE_IN_EDITOR,
                    target_name=f.file_name,
                    target_path=f.file_path,
                    content_payload=f.content_preview,
                    confidence=0.85,
                    explanation=f"Resolved 'this' to detected code file '{f.file_name}'.",
                )

        # D. Clipboard contains code or error
        if snapshot.clipboard.has_text:
            clip = snapshot.clipboard
            resolved_prompt = f"Fix the code/error snippet from clipboard: \"{clip.text.strip()}\""
            return ResolvedContextAction(
                original_prompt=prompt,
                resolved_prompt=resolved_prompt,
                target_type=DeicticTargetType.CLIPBOARD,
                target_name="Clipboard Snippet",
                content_payload=clip.text,
                confidence=0.75,
                explanation="Resolved 'this' to snippet in clipboard.",
            )

        # E. Fallback to active window
        win_title = snapshot.window.title or "Active Window"
        resolved_prompt = f"Fix the issue currently displayed in '{win_title}'."
        return ResolvedContextAction(
            original_prompt=prompt,
            resolved_prompt=resolved_prompt,
            target_type=DeicticTargetType.ACTIVE_WINDOW,
            target_name=win_title,
            confidence=0.50,
            explanation=f"Resolved 'this' to active window '{win_title}'.",
        )

    @classmethod
    def _resolve_explain(
        cls, prompt: str, snapshot: SystemContextSnapshot
    ) -> ResolvedContextAction:
        """Priority: Selected Text -> Open Document / Code -> Browser Page -> Active Window."""
        # A. Selected Text (Primary semantic for 'Explain this')
        if snapshot.selection.has_selection:
            sel = snapshot.selection
            resolved_prompt = f"Explain the following selected text: \"{sel.text}\""
            return ResolvedContextAction(
                original_prompt=prompt,
                resolved_prompt=resolved_prompt,
                target_type=DeicticTargetType.SELECTED_TEXT,
                target_name="Selected Text",
                content_payload=sel.text,
                confidence=0.98,
                explanation=f"Resolved 'this' to {sel.char_count} characters of selected text in {sel.source_app}.",
                metadata={"source_app": sel.source_app, "char_count": sel.char_count},
            )

        # B. Open Document or Code
        pof = snapshot.primary_open_file
        if pof:
            target_type = DeicticTargetType.CODE_IN_EDITOR if pof.is_code else DeicticTargetType.OPEN_DOCUMENT
            resolved_prompt = (
                f"Explain the {'code' if pof.is_code else 'document'} '{pof.file_name}' ({pof.file_path}) "
                f"currently open in {pof.source_app}."
            )
            return ResolvedContextAction(
                original_prompt=prompt,
                resolved_prompt=resolved_prompt,
                target_type=target_type,
                target_name=pof.file_name,
                target_path=pof.file_path,
                content_payload=pof.content_preview,
                confidence=0.90,
                explanation=f"Resolved 'this' to the active file '{pof.file_name}'.",
                metadata={"file_path": pof.file_path},
            )

        # C. Browser Page
        if snapshot.browser.is_browser_active and (snapshot.browser.page_title or snapshot.browser.current_url):
            browser = snapshot.browser
            resolved_prompt = (
                f"Explain the content and subject of the web page '{browser.page_title}' "
                f"({browser.current_url}) currently open in {browser.browser_name}."
            )
            return ResolvedContextAction(
                original_prompt=prompt,
                resolved_prompt=resolved_prompt,
                target_type=DeicticTargetType.BROWSER_PAGE,
                target_name=browser.page_title or browser.domain,
                content_payload=browser.current_url,
                confidence=0.85,
                explanation=f"Resolved 'this' to current browser tab in {browser.browser_name}.",
            )

        # D. Active Window
        win_title = snapshot.window.title or "Active Window"
        resolved_prompt = f"Explain what is currently displayed in '{win_title}' ({snapshot.application.friendly_name})."
        return ResolvedContextAction(
            original_prompt=prompt,
            resolved_prompt=resolved_prompt,
            target_type=DeicticTargetType.ACTIVE_WINDOW,
            target_name=win_title,
            confidence=0.60,
            explanation=f"Resolved 'this' to active window '{win_title}'.",
        )

    @classmethod
    def _resolve_translate(
        cls, prompt: str, snapshot: SystemContextSnapshot
    ) -> ResolvedContextAction:
        if snapshot.selection.has_selection:
            sel = snapshot.selection
            return ResolvedContextAction(
                original_prompt=prompt,
                resolved_prompt=f"{prompt}: \"{sel.text}\"",
                target_type=DeicticTargetType.SELECTED_TEXT,
                target_name="Selected Text",
                content_payload=sel.text,
                confidence=0.95,
                explanation="Resolved 'this' to selected text for translation.",
            )
        if snapshot.clipboard.has_text:
            clip = snapshot.clipboard
            return ResolvedContextAction(
                original_prompt=prompt,
                resolved_prompt=f"{prompt}: \"{clip.text.strip()}\"",
                target_type=DeicticTargetType.CLIPBOARD,
                target_name="Clipboard Text",
                content_payload=clip.text,
                confidence=0.85,
                explanation="Resolved 'this' to clipboard text for translation.",
            )
        return cls._resolve_general(prompt, snapshot)

    @classmethod
    def _resolve_general(
        cls, prompt: str, snapshot: SystemContextSnapshot
    ) -> ResolvedContextAction:
        """General resolution picking the most salient active context element."""
        if snapshot.selection.has_selection:
            return ResolvedContextAction(
                original_prompt=prompt,
                resolved_prompt=f"{prompt} (Target: Selected Text \"{snapshot.selection.text[:60]}...\")",
                target_type=DeicticTargetType.SELECTED_TEXT,
                target_name="Selected Text",
                content_payload=snapshot.selection.text,
                confidence=0.85,
                explanation="Resolved to selected text.",
            )

        pof = snapshot.primary_open_file
        if pof:
            return ResolvedContextAction(
                original_prompt=prompt,
                resolved_prompt=f"{prompt} (Target: Open File '{pof.file_name}')",
                target_type=DeicticTargetType.OPEN_DOCUMENT if pof.is_document else DeicticTargetType.CODE_IN_EDITOR,
                target_name=pof.file_name,
                target_path=pof.file_path,
                content_payload=pof.content_preview,
                confidence=0.85,
                explanation=f"Resolved to open file '{pof.file_name}'.",
            )

        if snapshot.browser.is_browser_active and snapshot.browser.current_url:
            return ResolvedContextAction(
                original_prompt=prompt,
                resolved_prompt=f"{prompt} (Target: Web Page '{snapshot.browser.page_title}' at {snapshot.browser.current_url})",
                target_type=DeicticTargetType.BROWSER_PAGE,
                target_name=snapshot.browser.page_title or snapshot.browser.domain,
                content_payload=snapshot.browser.current_url,
                confidence=0.80,
                explanation="Resolved to active browser tab.",
            )

        win_title = snapshot.window.title or "Active Window"
        return ResolvedContextAction(
            original_prompt=prompt,
            resolved_prompt=f"{prompt} (Target: '{win_title}')",
            target_type=DeicticTargetType.ACTIVE_WINDOW,
            target_name=win_title,
            confidence=0.50,
            explanation=f"Resolved to active window '{win_title}'.",
        )
