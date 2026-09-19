"""Local Conversation Engine for JARVIS.

Coordinates:
Microphone / STT -> Wake-Word Gate -> Ollama -> SQLite Memory -> Response -> TTS
"""

from __future__ import annotations
from typing import Any
import re
from typing import Optional, List, Dict
from jarvis.subsystems.local.ollama_client import OllamaClient
from jarvis.subsystems.local.memory import ConversationMemory
from jarvis.subsystems.local.tts import LocalTTS
from jarvis.subsystems.local.stt import LocalSTT
from jarvis.capabilities.agent_planner import AgentToolExecutor
from jarvis.tools.registry import ToolRegistry
from jarvis.core.personality import PersonalityEngine
from jarvis.core.ui_state import UIStateManager, default_ui_state


WAKE_WORDS = ["jarvis", "hey jarvis", "hi jarvis", "ok jarvis"]


class ConversationEngine:
    """Manages multi-turn voice and text conversations with secure tool capabilities and personality."""

    def __init__(
        self,
        ollama_client: Optional[OllamaClient] = None,
        memory: Optional[ConversationMemory] = None,
        tts: Optional[LocalTTS] = None,
        stt: Optional[LocalSTT] = None,
        tool_executor: Optional[AgentToolExecutor] = None,
        session_id: Optional[str] = None,
        speak_output: bool = True,
        enable_tools: bool = True,
        unified_memory: Optional[Any] = None,
        personality: Optional[PersonalityEngine] = None,
        ui_state: Optional[UIStateManager] = None,
    ):
        self.ollama = ollama_client or OllamaClient()
        self.memory = memory or ConversationMemory()
        self.tts = tts or LocalTTS(enabled=speak_output)
        self.stt = stt or LocalSTT()
        self.enable_tools = enable_tools
        self.tool_executor = tool_executor or (
            AgentToolExecutor(ollama_client=self.ollama) if enable_tools else None
        )
        self.unified_memory = unified_memory
        self.personality = personality or PersonalityEngine()
        self.ui_state = ui_state or default_ui_state
        self.session_id = session_id or self.memory.get_latest_session_id()
        self.is_active = False


    def is_wake_word(self, text: str) -> bool:
        """Check if input text is purely a wake word trigger."""
        cleaned = re.sub(r"[^\w\s]", "", text.strip().lower())
        return cleaned in WAKE_WORDS

    def extract_query(self, text: str) -> str:
        """Strip leading wake-word salutations if combined in one utterance."""
        cleaned = text.strip()
        lower = cleaned.lower()
        for w in WAKE_WORDS:
            pattern = rf"^{re.escape(w)}[\s,:\.\?!]+"
            if re.match(pattern, lower):
                return re.sub(pattern, "", cleaned, flags=re.IGNORECASE).strip()
        return cleaned

    def process_turn(self, user_input: str) -> str:
        """Process a single conversational turn through the local brain pipeline.

        Returns:
            The generated response string.
        """
        raw_text = user_input.strip()
        if not raw_text:
            return ""

        # Check for standalone wake word: "Jarvis." -> "Yes?"
        if self.is_wake_word(raw_text):
            self.is_active = True
            response = "Yes?"
            self.tts.speak(response)
            return response

        # If it was a combined query like "Jarvis, what is a binary search tree?"
        query = self.extract_query(raw_text)
        self.ui_state.add_message("You", query)
        self.ui_state.set_agent_state("THINKING...", quote="Analyzing request...")

        # 1. Personality: User appreciation check
        if self.personality.is_user_appreciation(query):
            response = self.personality.on_user_appreciation(query)
        else:
            # Retrieve prior conversational history from SQLite
            history = self.memory.get_history(self.session_id, limit=8)

            # Retrieve relevant long-term memory context (preferences, knowledge, episodes)
            mem_context = self.unified_memory.get_relevant_context(query) if self.unified_memory else ""
            augmented_history = list(history)
            if mem_context:
                augmented_history.insert(0, {"role": "system", "content": f"Context from Long-Term Memory:\n{mem_context}"})

            # Retrieve active desktop context snapshot (Phase 10 Context Awareness)
            try:
                from jarvis.subsystems.context.collector import ContextCollector
                snap = ContextCollector.get_instance().collect(refresh=False, capture_selection=False)
                augmented_history.insert(0, {"role": "system", "content": snap.to_prompt_context()})
            except Exception:
                pass

            if self.enable_tools and self.tool_executor:
                turn_result = self.tool_executor.run_turn(query, augmented_history)
                response = turn_result.final_response
            else:
                # Direct chat fallback
                messages: List[Dict[str, str]] = list(augmented_history)
                messages.append({"role": "user", "content": query})
                response = self.ollama.chat(messages)

            # Stylize final response according to personality interaction layer
            response = self.personality.stylize_response(response)

        # Update UI state
        self.ui_state.add_message("JARVIS", response)
        self.ui_state.set_agent_state("LISTENING...", quote="How may I assist you?")

        # Persist both user query and assistant answer into SQLite
        self.memory.add_message(self.session_id, "user", query)
        self.memory.add_message(self.session_id, "assistant", response)

        # Output via local TTS
        self.tts.speak(response)

        return response

