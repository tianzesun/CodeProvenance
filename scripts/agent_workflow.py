"""Prompt-chain helper for the IntegrityDesk multi-agent workflow."""

from __future__ import annotations

import argparse
import re
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROMPT_DIR = ROOT / "docs" / "agents" / "prompts"
RUN_DIR = ROOT / "docs" / "agent-runs"
AGENTS = (
    "project-manager",
    "researcher",
    "architect",
    "developer",
    "tester",
    "reviewer",
)


def slugify(value: str) -> str:
    """Convert a feature title into a filesystem-safe slug."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "agent-run"


def read_prompt(agent: str) -> str:
    """Read a prompt template by agent name."""
    if agent not in AGENTS:
        names = ", ".join(AGENTS)
        raise SystemExit(f"Unknown agent '{agent}'. Choose one of: {names}")
    return (PROMPT_DIR / f"{agent}.md").read_text(encoding="utf-8")


def list_prompts() -> str:
    """Return all available prompt names."""
    return "\n".join(AGENTS)


def init_run(title: str) -> Path:
    """Create a markdown coordination file for one prompt-chain run."""
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    path = RUN_DIR / f"{stamp}-{slugify(title)}.md"
    chain = " -> ".join(agent.replace("-", " ").title() for agent in AGENTS)
    path.write_text(
        "\n".join(
            (
                f"# {title}",
                "",
                f"Created: {datetime.now().isoformat(timespec='seconds')}",
                f"Workflow: {chain}",
                "",
                "## Feature Request",
                "",
                title,
                "",
                "## Agent Handoffs",
                "",
                "### Project Manager",
                "",
                "### Researcher",
                "",
                "### Architect",
                "",
                "### Developer",
                "",
                "### Tester",
                "",
                "### Reviewer",
                "",
            )
        ),
        encoding="utf-8",
    )
    return path


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Print IntegrityDesk agent prompts or initialize a run file.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="List available agent prompts.")

    show_parser = subparsers.add_parser("show", help="Print an agent prompt.")
    show_parser.add_argument("agent", choices=AGENTS)

    init_parser = subparsers.add_parser("init", help="Create an agent run file.")
    init_parser.add_argument("title")

    return parser


def main() -> None:
    """Run the prompt-chain helper."""
    args = build_parser().parse_args()
    if args.command == "list":
        print(list_prompts())
    elif args.command == "show":
        print(read_prompt(args.agent))
    elif args.command == "init":
        path = init_run(args.title)
        print(path.relative_to(ROOT))


if __name__ == "__main__":
    main()
