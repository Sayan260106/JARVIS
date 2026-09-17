# JARVIS Operating Rules & Safety Governance

These rules govern every autonomous action performed by JARVIS across all phases.

---

## 1. The Cardinal Principles

### Rule 1: No Action Without Verification
- An action is never assumed to have succeeded simply because the invocation returned without an exception.
- Every action must be followed by an explicit **Observation** step that inspects real environmental state (e.g. exit codes, file existence, content hash, process list, UI response).
- If verification cannot be confirmed, the step state is marked as `UNVERIFIED` and handled via the recovery protocol.

### Rule 2: Safe Defaults & Non-Destructive Guardrails
- **Destructive Operations** (permanent file deletion, process termination, disk formatting, registry edits, network configuration changes) require explicit confirmation before execution.
- Tools must prefer soft operations (e.g. move to recycle bin / backup directory instead of `rm -rf` or `Remove-Item -Recurse -Force`).
- Critical OS system paths (`C:\Windows`, system registry, system drivers) are blocked by default.

### Rule 3: Bounded Recovery Loops
- An agent must never enter an infinite loop when encountering failure.
- The maximum retry limit for any single step is **3 attempts**.
- Recovery attempts must apply varying strategies:
  1. *Attempt 1*: Self-correction of parameters or arguments.
  2. *Attempt 2*: Alternative tool or alternative subsystem route.
  3. *Attempt 3*: Structural re-plan of the entire task graph.
  4. *Attempt 4 (Escalation)*: Pause execution and prompt the user with clear diagnosis and options.

### Rule 4: Decoupling & Model Agnosticism
- The core orchestrator loop does not depend on a proprietary LLM API.
- All model interactions pass through a unified provider interface (`LLMProvider`) that can switch dynamically between Local (Ollama, vLLM) and Cloud (Gemini, Claude, OpenAI).
- Business logic, execution flow, and verification rules are enforced programmatically in Python code, not left to pure model prompt adherence.

### Rule 5: Transparent Telemetry & Explainability
- All state changes, decisions, plans, observations, and recoveries are logged in structured JSONL format.
- The user can inspect the exact reasoning chain, command history, and observation evidence at any time.

---

## 2. Step Execution Protocol

Before executing any step in a plan:
1. **Pre-flight Check**: Verify that preconditions and dependencies from previous steps are satisfied.
2. **Execution Boundary**: Pass only validated, sanitized parameters to the subsystem tool.
3. **Observation Collection**: Collect all output streams (stdout, stderr, exit code, execution duration).
4. **Verification Gate**: Evaluate the observation against the expected result criteria.
5. **Transition**: If `PASS`, proceed to next step. If `FAIL`, invoke recovery engine.
