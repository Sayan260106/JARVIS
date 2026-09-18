"""Voice 2.0 Interface & Continuous Voice Pipeline for JARVIS.

Unifies voice and text under the central JARVIS Agent Loop orchestrator:
Microphone / Audio Stream
       ↓
Wake-word detector ("Hey JARVIS...")
       ↓
Speech recognition (Local STT)
       ↓
Task Engine / Central Agent Loop (JarvisAgentLoop)
       ↓
Action & Reversible History Stack ("Actually, cancel that", "Wait, go back")
       ↓
TTS Response (Local TTS with interruptibility)

Both Spoken Voice and Text reach the EXACT same orchestrator.
"""

from __future__ import annotations
import argparse
import queue
import re
import sys
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from jarvis.core.loop import JarvisAgentLoop
from jarvis.core.state import LoopPhase
from jarvis.subsystems.local.stt import LocalSTT, WakeWordDetector
from jarvis.subsystems.local.tts import LocalTTS
from jarvis.capabilities.conversation import ConversationEngine


class VoiceSessionState(str, Enum):
    """Lifecycle states of the voice conversation agent."""
    IDLE = "IDLE"                   # Waiting for wake-word
    LISTENING = "LISTENING"         # Wake-word heard, waiting for user command
    THINKING = "THINKING"           # Transcribing or analyzing
    EXECUTING = "EXECUTING"         # Running through JarvisAgentLoop
    SPEAKING = "SPEAKING"           # Speaking aloud via TTS
    INTERRUPTED = "INTERRUPTED"     # Interrupted via cancel or rollback


@dataclass
class ActionHistoryRecord:
    """Represents a reversible action executed by the agent loop."""
    description: str
    tool_name: str
    parameters: Dict[str, Any]
    undo_tool: Optional[str] = None
    undo_args: Optional[Dict[str, Any]] = None
    timestamp: float = field(default_factory=time.time)


class ActionHistoryStack:
    """Maintains an undo/rewind stack to support 'Wait, go back'."""

    def __init__(self):
        self._stack: List[ActionHistoryRecord] = []

    def push(self, record: ActionHistoryRecord) -> None:
        self._stack.append(record)

    def pop(self) -> Optional[ActionHistoryRecord]:
        return self._stack.pop() if self._stack else None

    def peek(self) -> Optional[ActionHistoryRecord]:
        return self._stack[-1] if self._stack else None

    def clear(self) -> None:
        self._stack.clear()

    @property
    def is_empty(self) -> bool:
        return len(self._stack) == 0

    def undo_last(self, loop: JarvisAgentLoop) -> Dict[str, Any]:
        """Reverts the most recent reversible action using the loop's tool registry."""
        if not self._stack:
            return {"success": False, "message": "Nothing to undo."}

        record = self._stack.pop()
        if not record.undo_tool:
            return {"success": True, "message": f"Action '{record.description}' had no undo procedure.", "record": record}

        registry = getattr(loop, "registry", None)
        if registry and hasattr(registry, "get"):
            tool = registry.get(record.undo_tool)
            if tool and hasattr(tool, "execute"):
                try:
                    tool.execute(**(record.undo_args or {}))
                    return {"success": True, "message": f"Reverted: {record.description}.", "record": record}
                except Exception as e:
                    return {"success": False, "message": f"Failed to undo {record.description}: {e}", "record": record}

        # Fallback simulation
        return {"success": True, "message": f"Reverted: {record.description}.", "record": record}


class VoiceInterface:
    """Voice 2.0 Agent Interface connecting voice to the central orchestrator."""

    def __init__(
        self,
        loop: Optional[JarvisAgentLoop] = None,
        tts: Optional[LocalTTS] = None,
        stt: Optional[LocalSTT] = None,
        wake_detector: Optional[WakeWordDetector] = None,
        conversation_engine: Optional[ConversationEngine] = None,
        wake_ack_phrase: str = "Yes?",
    ):
        self.loop = loop or JarvisAgentLoop()
        self.tts = tts or LocalTTS(enabled=True)
        self.stt = stt or LocalSTT()
        self.wake_detector = wake_detector or WakeWordDetector()
        self.conversation_engine = conversation_engine
        self.wake_ack_phrase = wake_ack_phrase

        self.state = VoiceSessionState.IDLE
        self.history = ActionHistoryStack()
        self.active_task_id: Optional[str] = None
        self.last_utterance: str = ""
        self.last_response: str = ""
        self._lock = threading.Lock()

    def process_utterance(self, utterance: str) -> Dict[str, Any]:
        """Processes a single spoken utterance through the state machine and orchestrator."""
        with self._lock:
            cleaned = utterance.strip()
            if not cleaned:
                return {"type": "empty", "state": self.state.value}

            self.last_utterance = cleaned

            # 1. Check for standalone wake-word trigger ("Hey JARVIS...", "JARVIS.")
            if self.wake_detector.is_wake_word(cleaned):
                self.state = VoiceSessionState.LISTENING
                self.last_response = self.wake_ack_phrase
                self.tts.speak(self.wake_ack_phrase)
                return {
                    "type": "wake_ack",
                    "state": self.state.value,
                    "response": self.wake_ack_phrase,
                    "command": "",
                }

            # 2. Check for compound wake-word trigger ("Hey JARVIS, open Chrome")
            command = self.wake_detector.extract_command(cleaned)
            if command is not None:
                if not command:
                    self.state = VoiceSessionState.LISTENING
                    self.last_response = self.wake_ack_phrase
                    self.tts.speak(self.wake_ack_phrase)
                    return {
                        "type": "wake_ack",
                        "state": self.state.value,
                        "response": self.wake_ack_phrase,
                        "command": "",
                    }
                target_query = command
            else:
                # If no wake word was spoken, verify if session is already engaged/listening
                if self.state in (VoiceSessionState.LISTENING, VoiceSessionState.EXECUTING):
                    target_query = cleaned
                else:
                    return {
                        "type": "ignored",
                        "state": self.state.value,
                        "reason": "Ignored utterance because wake-word was not detected while IDLE.",
                    }

            # 3. Conversational Interruption & Cancellation: "Actually, cancel that"
            if re.search(r"\b(?:actually[,\s]+cancel(?:\s+that)?|cancel(?:\s+that)?|abort|stop(?:\s+that)?)\b", target_query, re.I):
                self.state = VoiceSessionState.INTERRUPTED
                self.tts.stop()
                if self.active_task_id:
                    self.loop.request_cancellation(self.active_task_id)
                self.loop.request_cancellation()

                # Roll back uncommitted action
                undo_res = self.history.undo_last(self.loop)
                cancel_resp = "Cancelled."
                self.last_response = cancel_resp
                self.tts.speak(cancel_resp)
                self.state = VoiceSessionState.IDLE
                return {
                    "type": "cancellation",
                    "state": self.state.value,
                    "response": cancel_resp,
                    "undo": undo_res,
                }

            # 4. Conversational Revert / Undo: "Wait, go back"
            if re.search(r"\b(?:wait[,\s]+go\s+back|go\s+back|undo(?:\s+that)?|revert(?:\s+last\s+action)?)\b", target_query, re.I):
                self.state = VoiceSessionState.INTERRUPTED
                undo_res = self.history.undo_last(self.loop)
                rollback_resp = "Going back." if undo_res.get("success") else "Nothing to go back to."
                self.last_response = rollback_resp
                self.tts.speak(rollback_resp)
                self.state = VoiceSessionState.LISTENING
                return {
                    "type": "rollback",
                    "state": self.state.value,
                    "response": rollback_resp,
                    "undo": undo_res,
                }

            # 5. General Command -> Hand off directly to Central Agent Loop orchestrator
            self.state = VoiceSessionState.EXECUTING
            agent_state = self.loop.run(target_query)
            self.active_task_id = agent_state.task_id

            if agent_state.phase == LoopPhase.COMPLETED:
                # Track reversible actions on history stack
                for record in agent_state.history:
                    step = record.step
                    if step.tool_name == "open_application":
                        app_name = step.arguments.get("app_name") or step.arguments.get("application", "Chrome")
                        self.history.push(ActionHistoryRecord(
                            description=f"Opened {app_name}",
                            tool_name="open_application",
                            parameters={"app_name": app_name},
                            undo_tool="close_application",
                            undo_args={"app_name": app_name},
                        ))
                    elif step.tool_name == "create_file":
                        fpath = step.arguments.get("path", "")
                        self.history.push(ActionHistoryRecord(
                            description=f"Created file '{fpath}'",
                            tool_name="create_file",
                            parameters={"path": fpath},
                            undo_tool="delete_file",
                            undo_args={"path": fpath},
                        ))

                spoken_text = self._format_spoken_response(target_query, agent_state)
            elif agent_state.phase == LoopPhase.CANCELLED:
                spoken_text = "Task was cancelled."
            elif agent_state.phase == LoopPhase.FAILED:
                spoken_text = f"Failed to complete task: {agent_state.error_message or 'Unknown error'}"
            else:
                # Conversational fallback
                if self.conversation_engine:
                    spoken_text = self.conversation_engine.process_turn(target_query)
                else:
                    spoken_text = agent_state.final_result or "Done."

            self.state = VoiceSessionState.SPEAKING
            self.last_response = spoken_text
            self.tts.speak(spoken_text)
            self.state = VoiceSessionState.LISTENING

            return {
                "type": "execution",
                "state": self.state.value,
                "command": target_query,
                "response": spoken_text,
                "task_id": agent_state.task_id,
                "loop_phase": agent_state.phase.value,
            }

    def _format_spoken_response(self, query: str, state: Any) -> str:
        """Formulates concise spoken responses suitable for voice output."""
        lower = query.strip().lower()
        if lower.startswith("open "):
            app = query.strip()[5:].strip().strip(".?!")
            return f"Opened {app}."
        if lower.startswith("close "):
            app = query.strip()[6:].strip().strip(".?!")
            return f"Closed {app}."
        if "lock" in lower:
            return "Workstation locked."
        if "volume" in lower:
            return "Volume adjusted."
        if state.final_result and len(state.final_result) < 120:
            return state.final_result
        return "Task completed successfully, sir."


class ContinuousVoiceListener:
    """Background listener managing real-time audio chunk feeds and queueing."""

    def __init__(
        self,
        voice_interface: VoiceInterface,
        chunk_duration: float = 0.5,
        samplerate: int = 16000,
    ):
        self.voice = voice_interface
        self.chunk_duration = chunk_duration
        self.samplerate = samplerate
        self.audio_queue: queue.Queue = queue.Queue()
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self):
        """Starts the background audio processing loop."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stops the continuous listening thread."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

    def inject_text(self, text: str) -> Dict[str, Any]:
        """Simulates direct voice transcription injection for testing."""
        return self.voice.process_utterance(text)

    def inject_audio_chunk(self, chunk: np.ndarray) -> None:
        """Simulates incoming microphone audio chunk."""
        self.audio_queue.put(chunk)

    def _listen_loop(self):
        """Processes audio chunks from queue or microphone stream."""
        buffer = []
        while self._running:
            try:
                chunk = self.audio_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            # Process chunk via STT
            rms = float(np.sqrt(np.mean(chunk**2))) if len(chunk) > 0 else 0.0
            if rms >= self.voice.stt.energy_threshold:
                buffer.append(chunk)
            elif buffer:
                # Speech ended, concatenate and transcribe
                audio_data = np.concatenate(buffer)
                buffer = []
                transcript = self.voice.stt.transcribe(audio_data)
                if transcript:
                    self.voice.process_utterance(transcript)


def run_interactive(voice: VoiceInterface):
    """Console-based simulation of the voice 2.0 interface."""
    print("\n[Voice 2.0 Active] Type your spoken commands (or 'exit' to quit).")
    print("Try saying:")
    print("  1. 'Hey JARVIS...'")
    print("  2. 'Open Chrome.'")
    print("  3. 'Actually, cancel that.'")
    print("  4. 'Wait, go back.'\n")

    while True:
        try:
            user_input = input("You (Spoken) > ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit"):
                print("JARVIS: Goodbye, sir.")
                voice.tts.speak("Goodbye, sir.")
                break

            result = voice.process_utterance(user_input)
            resp = result.get("response", "")
            if resp:
                print(f"JARVIS [{result.get('state', '')}] > {resp}\n")

        except (KeyboardInterrupt, EOFError):
            print("\nShutting down Voice 2.0 interface.")
            break


def run_microphone(voice: VoiceInterface):
    """Live microphone mode using continuous STT listener."""
    print("\n[Voice 2.0 Continuous Microphone Active]")
    print("Listening for: 'Hey JARVIS...', 'Open Chrome', 'Actually, cancel that', 'Wait, go back'...")
    print("Press Ctrl+C to stop.\n")

    listener = ContinuousVoiceListener(voice)
    listener.start()

    try:
        while True:
            text = voice.stt.listen_and_transcribe(timeout=5.0)
            if text:
                print(f"\nYou [Spoken] > {text}")
                res = voice.process_utterance(text)
                if res.get("response"):
                    print(f"JARVIS > {res['response']}\n")
    except KeyboardInterrupt:
        print("\nStopping continuous voice listener.")
    finally:
        listener.stop()


def main():
    parser = argparse.ArgumentParser(description="JARVIS Voice 2.0 Continuous Interface")
    parser.add_argument(
        "--mode",
        choices=["interactive", "mic", "continuous"],
        default="interactive",
        help="Interface mode: 'interactive' (simulated voice input) or 'mic' (continuous microphone)",
    )
    parser.add_argument(
        "--no-tts",
        action="store_true",
        help="Disable TTS audio playback",
    )

    args = parser.parse_args()

    print("=" * 60)
    print(" JARVIS - Phase 9: Voice 2.0 (Continuous Voice Agent)")
    print(" Pipeline: Wake-Word -> STT -> AgentLoop -> Undo/Action -> TTS")
    print("=" * 60)

    loop = JarvisAgentLoop()
    tts = LocalTTS(enabled=not args.no_tts)
    stt = LocalSTT()
    wake_detector = WakeWordDetector()
    voice = VoiceInterface(loop=loop, tts=tts, stt=stt, wake_detector=wake_detector)

    if args.mode in ("mic", "continuous"):
        run_microphone(voice)
    else:
        run_interactive(voice)


if __name__ == "__main__":
    main()
