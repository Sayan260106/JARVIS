"""Command Line Interface for JARVIS Phase 0."""

import sys

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from jarvis.core.loop import JarvisAgentLoop
from jarvis.core.state import LoopPhase


def run_cli():
    print("=" * 60)
    print(" JARVIS - Autonomous AI Assistant (Phase 0: Agent Loop)")
    print(" Loop: Understand -> Plan -> Act -> Observe -> Verify -> Recover")
    print("=" * 60)

    loop = JarvisAgentLoop()

    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        _execute_query(loop, query)
    else:
        print("\nEnter an objective (or 'exit' to quit):")
        while True:
            try:
                user_input = input("\nJARVIS > ").strip()
                if not user_input:
                    continue
                if user_input.lower() in ("exit", "quit"):
                    print("Shutting down JARVIS.")
                    break
                _execute_query(loop, user_input)
            except (KeyboardInterrupt, EOFError):
                print("\nExiting.")
                break


def _execute_query(loop: JarvisAgentLoop, query: str):
    print(f"\n[1. UNDERSTAND] Parsing intent for: '{query}'")
    state = loop.run(query)

    if state.phase == LoopPhase.AWAITING_USER:
        print(f"  [?] Clarification Required: {state.error_message}")
        return

    print(f"  Intent: {state.objective.intent.value}")
    print(f"\n[2. PLAN] Generated {len(state.plan.steps)} steps:")
    for idx, step in enumerate(state.plan.steps, 1):
        print(f"  Step {idx}: [{step.subsystem.value}] {step.description} (Tool: {step.tool_name})")

    print("\n[3. ACT -> 4. OBSERVE -> 4b. VERIFY]")
    for record in state.history:
        status_sym = "[PASS]" if record.verification.passed else "[FAIL]"
        print(f"  {status_sym} Step: {record.step.description}")
        print(f"         Duration: {record.observation.duration_ms:.2f}ms")
        print(f"         Observation: {record.observation.output[:80]}...")
        if record.recovery:
            print(f"         [5. RECOVER] Strategy: {record.recovery.strategy.value} - {record.recovery.explanation}")

    if state.phase == LoopPhase.COMPLETED:
        print(f"\n[FINAL RESULT]: {state.final_result}")
    else:
        print(f"\n[STOPPED]: Phase={state.phase.value}, Error={state.error_message}")


if __name__ == "__main__":
    run_cli()
