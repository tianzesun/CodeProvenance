# VS Code And Augment Prompt Chain

This workflow uses plain markdown files as coordination state. It does not
require a separate agent framework.

## Setup

1. Open this repository in VS Code.
2. Open `docs/agents/system-prompt.md`.
3. Paste that prompt into a fresh Augment thread.
4. Keep these files open while working:
   - `docs/tasks.md`
   - `docs/research.md`
   - `docs/architecture.md`
   - `docs/agents/prompts/`

## Triggering Agents

Use the command palette task `Tasks: Run Task` for quick prompt access:

- `Agent: List Prompts`
- `Agent: Show Project Manager Prompt`
- `Agent: Show Researcher Prompt`
- `Agent: Show Architect Prompt`
- `Agent: Show Developer Prompt`
- `Agent: Show Tester Prompt`
- `Agent: Show Reviewer Prompt`
- `Agent: Init Run`

The tasks print prompt text in the terminal. Paste the relevant prompt into
Augment with the current feature request and previous agent handoff.

## Manual Chain

### 1. Project Manager

Paste:

```text
Use docs/agents/prompts/project-manager.md.
Feature request: <your feature>
```

Expected result:

- `docs/tasks.md` updated with scope, steps, acceptance criteria, and handoff.

### 2. Researcher

Paste:

```text
Use docs/agents/prompts/researcher.md.
Read the Project Manager handoff from docs/tasks.md.
```

Expected result:

- `docs/research.md` updated with findings, tool notes, risks, and options.

### 3. Architect

Paste:

```text
Use docs/agents/prompts/architect.md.
Read docs/tasks.md and docs/research.md.
```

Expected result:

- `docs/architecture.md` updated with module boundaries, diagrams, and a slice
  plan.

### 4. Developer

Paste:

```text
Use docs/agents/prompts/developer.md.
Implement only the approved slice from docs/architecture.md.
```

Expected result:

- Minimal implementation changes.
- No dependency additions without confirmation.

### 5. Tester

Paste:

```text
Use docs/agents/prompts/tester.md.
Add focused tests for the Developer changes.
```

Expected result:

- Unit and integration tests under `tests/` where appropriate.
- Validation commands recorded.

### 6. Reviewer

Paste:

```text
Use docs/agents/prompts/reviewer.md.
Review the current diff and test results.
```

Expected result:

- Blocking findings first.
- Developer fix-back task list if needed.
- Sign-off only when the slice is acceptable.

## Example Prompt Chain

```text
Feature request:
Make IntegrityDesk a unified platform where professors can run MOSS, JPlag,
Dolos, NiCad, and IntegrityDesk presets from one analysis workflow. The platform
should recommend tools based on assignment features and produce one combined
report when multiple tools run.
```

Start with the Project Manager prompt. Do not ask the Developer to code until
Researcher and Architect outputs have been written.

## Coordination Tools

- `docs/tasks.md`: task board and agent handoffs.
- `docs/research.md`: researched facts, tool tradeoffs, and risks.
- `docs/architecture.md`: module plan and diagrams.
- `docs/agent-runs/`: optional per-feature prompt-chain transcript.
- `tools/README.md`: external tool installation and reproducibility notes.
- `src/backend/engines/execution/`: existing external tool execution layer.
- `src/backend/benchmark/tools/tool_registry.py`: existing tool metadata model.
