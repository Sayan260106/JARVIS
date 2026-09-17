"""Voice & Conversational Interface for JARVIS Phase 1.

Supports:
1. Interactive Mode: Type prompt, hear response via local TTS.
2. Microphone Mode: Speak via microphone, transcribed via STT, answered via TTS.
"""

import argparse
import sys

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from jarvis.capabilities.conversation import ConversationEngine
from jarvis.subsystems.local.ollama_client import OllamaClient
from jarvis.subsystems.local.tts import LocalTTS
from jarvis.subsystems.local.stt import LocalSTT


def run_interactive(engine: ConversationEngine):
    print("\n[Local Brain Active] Type your prompt (or 'exit' to quit).")
    print("Tip: Say 'Jarvis.' to test the wake-word trigger, or ask any technical question.\n")

    while True:
        try:
            user_input = input("You > ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit"):
                print("JARVIS: Goodbye.")
                engine.tts.speak("Goodbye.")
                break

            print("\nJARVIS > Thinking (Ollama)...", end="\r")
            response = engine.process_turn(user_input)
            print(f"JARVIS > {response}\n")

        except (KeyboardInterrupt, EOFError):
            print("\nShutting down voice interface.")
            break


def run_microphone(engine: ConversationEngine):
    print("\n[Microphone Mode Active] Listening on default microphone...")
    print("Press Ctrl+C to stop.\n")

    while True:
        try:
            print("Listening... (speak now)", end="\r")
            text = engine.stt.listen_and_transcribe(timeout=6.0)
            if not text:
                continue

            print(f"\nYou [Spoken] > {text}")
            print("JARVIS > Processing...", end="\r")
            response = engine.process_turn(text)
            print(f"JARVIS > {response}\n")

        except KeyboardInterrupt:
            print("\nMicrophone listener stopped.")
            break


def main():
    parser = argparse.ArgumentParser(description="JARVIS Local Brain Voice Interface")
    parser.add_argument(
        "--mode",
        choices=["interactive", "mic"],
        default="interactive",
        help="Interface mode: 'interactive' (console + TTS) or 'mic' (full STT + TTS)",
    )
    parser.add_argument(
        "--no-tts",
        action="store_true",
        help="Disable TTS audio playback",
    )
    parser.add_argument(
        "--model",
        default="qwen2.5:3b",
        help="Ollama model name (default: qwen2.5:3b)",
    )

    args = parser.parse_args()

    print("=" * 60)
    print(" JARVIS - Phase 1: Local Brain (100% Offline)")
    print(f" LLM: Ollama ({args.model}) | Memory: SQLite | Audio: Local SAPI5")
    print("=" * 60)

    ollama = OllamaClient(model=args.model)
    if not ollama.is_available():
        print(f"[!] Warning: Cannot reach Ollama at {ollama.base_url}.")
        print("    Ensure the Ollama application is running ('ollama serve').")
        sys.exit(1)

    tts = LocalTTS(enabled=not args.no_tts)
    stt = LocalSTT()
    engine = ConversationEngine(ollama_client=ollama, tts=tts, stt=stt)

    if args.mode == "mic":
        run_microphone(engine)
    else:
        run_interactive(engine)


if __name__ == "__main__":
    main()
