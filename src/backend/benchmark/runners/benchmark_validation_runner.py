"""
Benchmark validation runner.

Orchestrates end-to-end benchmark validation runs following formal protocol.
Handles dataset splitting, baseline execution, candidate tool execution,
metric calculation, validation rule application, and report generation.
"""
from __future__ import annotations

import datetime
import logging
from typing import Any, Dict, List, Tuple, Optional
import uuid

from ..adapters.base_adapter import BaseAdapter
from ..adapters import get_adapter
from ..cross_dataset.dataset_registry import get_dataset
from ..evaluation.metrics import calculate_all_metrics
from ..validation.protocol import ValidationProtocol, ValidationResult, ValidationStatus
from ..validation.pass_fail import BenchmarkPassFailValidator, STANDARD_VALIDATION_RULES


logger = logging.getLogger(__name__)


class BenchmarkValidationRunner:
    """
    Main execution runner for benchmark validation protocols.
    Orchestrates the complete benchmark validation workflow.
    """

    def __init__(self, protocol: ValidationProtocol):
        self.protocol = protocol
        self.result = ValidationResult(
            protocol=protocol,
            status=ValidationStatus.PENDING
        )

    def run(self) -> ValidationResult:
        """
        Execute the complete validation protocol.

        Returns:
            Final validation result with all metrics and pass/fail outcomes
        """
        self.result.started_at = datetime.datetime.utcnow()
        self.result.status = ValidationStatus.RUNNING

        try:
            logger.info(f"Starting validation run {self.protocol.protocol_id}")
            logger.info(f"Dataset: {self.protocol.dataset_id}")

            # Load dataset
            dataset = get_dataset(self.protocol.dataset_id)
            logger.info(f"Loaded dataset with {len(dataset)} samples")

            # Execute baseline tools
            baseline_results = {}
            for tool_id in self.protocol.baseline_tools:
                logger.info(f"Running baseline tool: {tool_id}")
                adapter = get_adapter(tool_id)
                baseline_results[tool_id] = self._run_tool(adapter, dataset)

            # Execute candidate tools
            for tool_id in self.protocol.candidate_tools:
                logger.info(f"Running candidate tool: {tool_id}")
                adapter = get_adapter(tool_id)
                self.result.tool_results[tool_id] = self._run_tool(adapter, dataset)

            # Calculate metrics and run validation rules
            validator = BenchmarkPassFailValidator(STANDARD_VALIDATION_RULES)

            for tool_id, tool_result in self.result.tool_results.items():
                passed, rule_results = validator.validate(tool_result, baseline_results)
                self.result.pass_fail_outcomes[tool_id] = passed

                self.result.comparison_summary[tool_id] = {
                    "metrics": tool_result,
                    "validation_rules": rule_results,
                    "passed": passed
                }

            self.result.status = ValidationStatus.COMPLETED
            if all(self.result.pass_fail_outcomes.values()):
                self.result.status = ValidationStatus.PASSED
            else:
                self.result.status = ValidationStatus.FAILED

            logger.info(f"Validation run completed with status: {self.result.status.value}")

        except Exception as e:
            logger.error(f"Validation run failed: {e}", exc_info=True)
            self.result.status = ValidationStatus.FAILED
            self.result.error_message = str(e)

        finally:
            self.result.completed_at = datetime.datetime.utcnow()

        return self.result

    def _run_tool(self, adapter: BaseAdapter, dataset: Any) -> Dict[str, Any]:
        """Run a single tool adapter against the dataset and calculate metrics."""
        predictions = adapter.run(dataset)
        metrics = calculate_all_metrics(dataset.ground_truth, predictions)
        return metrics
