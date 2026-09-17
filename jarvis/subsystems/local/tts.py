"""Local Text-to-Speech (TTS) engine for JARVIS.

Utilizes native Windows SAPI5 via pyttsx3 for zero-latency, 100% offline speech synthesis.
"""

from __future__ import annotations
import threading
from typing import Optional


try:
    # pyrefly: ignore [missing-import]
    import pyttsx3
except ImportError:
    pyttsx3 = None


class LocalTTS:
    """Offline Text-to-Speech synthesizer."""

    def __init__(self, rate: int = 190, volume: float = 1.0, enabled: bool = True):
        self.rate = rate
        self.volume = volume
        self.enabled = enabled
        self._lock = threading.Lock()
        self._engine = None

        if self.enabled:
            self._init_engine()

    def _init_engine(self):
        if pyttsx3 is None:
            print("[TTS Warning] pyttsx3 package is not installed. Falling back to console-only speech.")
            self._engine = None
            return

        try:
            self._engine = pyttsx3.init()
            self._engine.setProperty("rate", self.rate)
            self._engine.setProperty("volume", self.volume)
        except Exception as e:
            print(f"[TTS Warning] Could not initialize SAPI5 engine: {e}. Falling back to console-only speech.")
            self._engine = None

    def speak(self, text: str, wait: bool = True):
        """Synthesizes and speaks text aloud through default audio output."""
        if not text or not text.strip():
            return

        clean_text = text.strip()

        if not self.enabled or self._engine is None:
            return

        with self._lock:
            try:
                self._engine.say(clean_text)
                if wait:
                    self._engine.runAndWait()
            except Exception as e:
                # If pyttsx3 loop gets desynced, attempt recovery
                try:
                    self._init_engine()
                    self._engine.say(clean_text)
                    if wait:
                        self._engine.runAndWait()
                except Exception:
                    pass

    def stop(self):
        """Immediately halts active speech playback."""
        if self._engine:
            try:
                self._engine.stop()
            except Exception:
                pass
