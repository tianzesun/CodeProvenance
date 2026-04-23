# IntegrityDesk Multi-Agent Workflow

This folder defines a minimal prompt-chaining workflow for using Augment as a
simulated multi-agent development system. The goal is to keep everyday coding
fast while forcing enough structure that product ideas become researched,
planned, implemented, tested, and reviewed in order.

## Agent Order

```text
Project Manager -> Researcher -> Architect -> Developer -> Tester -> Reviewer
                                             ^                    |
                                             |--------------------|
```

If the Reviewer finds blocking problems, the next prompt goes back to the
Developer with a narrow fix list. The loop repeats until the Reviewer signs off
or records known follow-up work in `docs/tasks.md`.

## Project Structure

```text
docs/
  agents/
    README.md
    system-prompt.md
    prompt-chain.md
    prompts/
      project-manager.md
      researcher.md
      architect.md
      developer.md
      tester.md
      reviewer.md
  agent-runs/              # Generated per-feature coordination notes
  research.md              # Researcher output
  architecture.md          # Architect output
  tasks.md                 # Project Manager task board

src/
  backend/
    api/                   # FastAPI routes and schemas
    application/           # Use cases and orchestration
    domain/                # Domain models and decision rules
    engines/               # Internal engines and external tool execution
    infrastructure/        # DB, reporting, parsing, logging
  frontend/                # Next.js user interface

tests/
  unit/                    # Tester-owned focused tests
  integration/             # Tester-owned cross-module tests

tools/                     # External detection tools and tool configs
scripts/
  agent_workflow.py        # Optional prompt-chain helper
```

## Daily Usage

1. Start with the system prompt in `docs/agents/system-prompt.md`.
2. Run the Project Manager prompt with the feature request.
3. Run each next agent prompt in order, pasting the previous agent output as
   context.
4. Allow the Developer to edit code only after Researcher and Architect outputs
   are written or updated.
5. Let the Tester add or update tests.
6. Let the Reviewer inspect the diff. If blocking problems exist, run the
   Developer prompt again with only those review findings.

## IntegrityDesk Platform Direction

Use this workflow to build IntegrityDesk as a unified detection platform, not
only as a single similarity engine. Professors should be able to:

- Run IntegrityDesk internal presets, MOSS, JPlag, Dolos, NiCad, and future
  tools from one interface.
- Select multiple tools in one job and receive one normalized report.
- See tool availability, supported languages, execution limits, and confidence
  notes before running a job.
- Receive recommended engine/tool presets based on assignment features.
- Compare evidence from different tools without treating any one detector as
  universally best.

## Prompt Templates

| Agent | Template | Required Output |
| --- | --- | --- |
| Project Manager | `prompts/project-manager.md` | Updates `docs/tasks.md` |
| Researcher | `prompts/researcher.md` | Updates `docs/research.md` |
| Architect | `prompts/architect.md` | Updates `docs/architecture.md` |
| Developer | `prompts/developer.md` | Code changes following architecture |
| Tester | `prompts/tester.md` | Tests under `tests/` |
| Reviewer | `prompts/reviewer.md` | Findings and developer fix-back tasks |

## Example Feature Request

```text
Feature: Unified detection tool launcher

Professors can choose IntegrityDesk, MOSS, JPlag, Dolos, and NiCad from one
analysis form, run multiple tools in parallel, and receive one normalized report
with per-tool evidence and a fused recommendation.
```

## Optional Helper

```bash
source /home/tsun/Documents/CodeProvenance/venv/bin/activate
python scripts/agent_workflow.py list
python scripts/agent_workflow.py show researcher
python scripts/agent_workflow.py init "unified detection tool launcher"
```

The helper does not call Augment for you. It creates or prints coordination text
so you can paste the right prompt into Augment at each stage.
