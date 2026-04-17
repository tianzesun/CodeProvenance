#!/usr/bin/env python3
"""
Single command validation entry point.

Usage:
    python -m src.backend.benchmark.validate <dataset_id> <candidate_tool>
"""
from __future__ import annotations

import sys
import logging
from pathlib import Path

# Add repo root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)7s | %(message)s"
)
logger = logging.getLogger(__name__)


def main() -> int:
    if len(sys.argv) < 3:
        print("Usage: python -m src.backend.benchmark.validate <dataset_id> <candidate_tool>")
        print("\nExample:")
        print("  python -m src.backend.benchmark.validate poj104 lexical_baseline")
        return 1

    try:
        from src.backend.benchmark.validation.protocol import ValidationProtocol
        from src.backend.benchmark.runners.benchmark_validation_runner import BenchmarkValidationRunner
    except ModuleNotFoundError as exc:
        logger.error("Missing runtime dependency for validation command: %s", exc)
        return 1

    dataset_id = sys.argv[1]
    candidate_tool = sys.argv[2]

    # Create standard validation protocol
    protocol = ValidationProtocol(
        dataset_id=dataset_id,
        baseline_tools=["moss"],
        candidate_tools=[candidate_tool],
        metrics=["precision", "recall", "f1"],
    )

    if not protocol.validate():
        logger.error("Invalid validation protocol configuration")
        return 1

    logger.info(f"Starting validation: dataset={dataset_id}, candidate={candidate_tool}")
    logger.info(f"Protocol ID: {protocol.protocol_id}")

    runner = BenchmarkValidationRunner(protocol)
    result = runner.run()

    logger.info("=" * 80)
    logger.info(f"Validation completed: {result.status.value}")
    logger.info(f"Duration: {result.duration_seconds:.1f} seconds")

    for tool_id, verdict in result.pass_fail_outcomes.items():
        logger.info(f"  {tool_id}: {verdict}")

    logger.info("=" * 80)

    return 0 if result.status.value != "failed" else 1


if __name__ == "__main__":
    sys.exit(main())
