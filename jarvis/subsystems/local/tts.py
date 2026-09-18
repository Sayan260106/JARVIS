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

        self._is_speaking = False

        if self.enabled:
            self._init_engine()

    @property
    def is_speaking(self) -> bool:
        """Returns True if speech playback is currently in progress."""
        return self._is_speaking

    def _init_engine(self):
        if pyttsx3 is None:
            self._engine = None
            return

        try:
            self._engine = pyttsx3.init()
            self._engine.setProperty("rate", self.rate)
            self._engine.setProperty("volume", self.volume)
        except Exception as e:
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
                self._is_speaking = True
                self._engine.say(clean_text)
                if wait:
                    self._engine.runAndWait()
            except Exception:
                try:
                    self._init_engine()
                    if self._engine:
                        self._engine.say(clean_text)
                        if wait:
                            self._engine.runAndWait()
                except Exception:
                    pass
            finally:
                if wait:
                    self._is_speaking = False

    def speak_async(self, text: str):
        """Speaks text in background thread so user can interrupt JARVIS mid-speech."""
        t = threading.Thread(target=self.speak, args=(text, True), daemon=True)
        t.start()

    def stop(self):
        """Immediately halts active speech playback and resets state."""
        self._is_speaking = False
        if self._engine:
            try:
                self._engine.stop()
            except Exception:
                pass
