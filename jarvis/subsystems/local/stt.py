"""Local Speech-to-Text (STT) engine for JARVIS.

Captures audio via sounddevice and transcribes locally using faster-whisper or speech_recognition.
"""

from __future__ import annotations
from ast import List
import io
import wave
from typing import Optional
import numpy as np

try:
    # pyrefly: ignore [missing-import]
    import sounddevice as sd
except ImportError:
    sd = None

try:
    # pyrefly: ignore [missing-import]
    from faster_whisper import WhisperModel
except ImportError:
    WhisperModel = None

try:
    # pyrefly: ignore [missing-import]
    import speech_recognition as sr
except ImportError:
    sr = None


class LocalSTT:
    """Offline Speech-to-Text transcriber using sounddevice + faster-whisper."""

    def __init__(
        self,
        model_size: str = "tiny.en",
        samplerate: int = 16000,
        energy_threshold: float = 0.015,
        device: str = "cpu",
        compute_type: str = "int8",
    ):
        self.model_size = model_size
        self.samplerate = samplerate
        self.energy_threshold = energy_threshold
        self.device = device
        self.compute_type = compute_type
        self._whisper_model = None

    def _get_whisper_model(self):
        """Lazy load Whisper model on first invocation."""
        if self._whisper_model is None:
            if WhisperModel is None:
                print("[STT Warning] faster_whisper is not installed.")
                return None
            try:
                self._whisper_model = WhisperModel(
                    self.model_size,
                    device=self.device,
                    compute_type=self.compute_type,
                )
            except Exception as e:
                print(f"[STT Warning] Could not load faster-whisper ({e}).")
        return self._whisper_model

    def record(self, duration: float = 4.0) -> np.ndarray:
        """Record raw audio from default microphone for specified duration."""
        if sd is None:
            raise RuntimeError("sounddevice is not installed. Please run: pip install sounddevice")
        num_frames = int(duration * self.samplerate)
        audio = sd.rec(num_frames, samplerate=self.samplerate, channels=1, dtype="float32")
        sd.wait()
        return audio.flatten()

    def record_until_silence(
        self,
        max_duration: float = 8.0,
        silence_timeout: float = 1.2,
        chunk_duration: float = 0.2,
    ) -> Optional[np.ndarray]:
        """Record from microphone until speech is followed by silence."""
        # pyrefly: ignore [missing-import]
        import sounddevice as sd
        chunk_frames = int(chunk_duration * self.samplerate)
        chunks = []
        speech_started = False
        silent_chunks = 0
        max_chunks = int(max_duration / chunk_duration)
        silence_threshold_chunks = int(silence_timeout / chunk_duration)

        with sd.InputStream(samplerate=self.samplerate, channels=1, dtype="float32") as stream:
            for _ in range(max_chunks):
                data, _ = stream.read(chunk_frames)
                flat_data = data.flatten()
                rms = np.sqrt(np.mean(flat_data**2))

                if rms > self.energy_threshold:
                    speech_started = True
                    silent_chunks = 0
                    chunks.append(flat_data)
                elif speech_started:
                    silent_chunks += 1
                    chunks.append(flat_data)
                    if silent_chunks >= silence_threshold_chunks:
                        break

        if not chunks or not speech_started:
            return None

        return np.concatenate(chunks)

    def transcribe(self, audio_data: np.ndarray) -> str:
        """Transcribe float32 numpy audio buffer to text."""
        model = self._get_whisper_model()
        if model is not None:
            try:
                # faster-whisper accepts numpy float32 array sampled at 16kHz directly
                segments, _ = model.transcribe(audio_data, language="en", beam_size=1)
                text = " ".join(seg.text.strip() for seg in segments)
                return text.strip()
            except Exception as e:
                print(f"[STT Warning] Whisper transcription failed: {e}")

        # Fallback to speech_recognition if whisper is unavailable
        if sr is not None:
            try:
                # Convert float32 [-1, 1] to int16
                int16_data = (audio_data * 32767).astype(np.int16)
                recognizer = sr.Recognizer()
                audio = sr.AudioData(int16_data.tobytes(), self.samplerate, 2)
                return recognizer.recognize_google(audio).strip()
            except Exception:
                return ""
        return ""

    def process_stream_chunk(self, audio_chunk: np.ndarray) -> Optional[str]:
        """Processes an incoming audio chunk in real time; returns transcribed text if voice detected."""
        if audio_chunk is None or len(audio_chunk) == 0:
            return None
        rms = float(np.sqrt(np.mean(audio_chunk**2)))
        if rms >= self.energy_threshold:
            text = self.transcribe(audio_chunk)
            return text if text else None
        return None


class WakeWordDetector:
    """Detects activation phrases (e.g. 'Hey JARVIS', 'JARVIS') with sensitivity and command extraction."""

    DEFAULT_WAKE_WORDS = ["hey jarvis", "jarvis", "hi jarvis", "ok jarvis"]

    def __init__(self, wake_words: Optional[List[str]] = None, sensitivity: float = 0.5):
        self.wake_words = [w.lower().strip() for w in (wake_words or self.DEFAULT_WAKE_WORDS)]
        self.sensitivity = sensitivity

    def is_wake_word(self, text: str) -> bool:
        """Determines if the utterance is purely a wake word trigger (e.g. 'Hey JARVIS...')."""
        import re
        cleaned = re.sub(r"[^\w\s]", "", text.strip().lower())
        return cleaned in self.wake_words

    def extract_command(self, text: str) -> Optional[str]:
        """If utterance starts with a wake word, extracts trailing command.
        
        Returns:
            - "" (empty string) if utterance was ONLY the wake word (e.g. 'Hey JARVIS...')
            - "Open Chrome" if compound utterance (e.g. 'Hey JARVIS, open Chrome')
            - None if wake word was NOT present at the start of the utterance.
        """
        import re
        cleaned = text.strip()
        lower = cleaned.lower()
        for w in self.wake_words:
            pattern = rf"^{re.escape(w)}[\s,:\.\?!]*(.*)$"
            m = re.match(pattern, lower)
            if m:
                rest = m.group(1).strip()
                if rest:
                    return cleaned[m.start(1):].strip()
                return ""
        return None

    def contains_wake_word(self, text: str) -> bool:
        """Checks whether the text contains any wake word phrase."""
        lower = text.lower()
        return any(w in lower for w in self.wake_words)
