"""
Job Executor - Isolated job runner.

Executes individual benchmark jobs in isolated process context.
Handles dataset loading, transformation application, and tool execution.
"""

from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class JobExecutor:
    """
    Isolated job executor.
    
    Runs individual micro-jobs in fully isolated context.
    Implements the pipeline: Load → Transform → Execute
    """

    @staticmethod
    def execute(job: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a single benchmark job.

        Pipeline:
            1. Load dataset subset
            2. Apply transform
            3. Run detection tool
            4. Return raw score
        """
        # Import dynamically to avoid circular imports
        from src.backend.benchmark.datasets.loader import DatasetLoader
        from src.backend.benchmark.transforms.engine import TransformEngine
        from src.backend.benchmark.tool_runner import ToolRunner

        loader = DatasetLoader()
        dataset = loader.load(job["dataset"], job["task"])

        transform_engine = TransformEngine()
        transformed = transform_engine.apply(dataset, job["transform"])

        tool_runner = ToolRunner()
        score = tool_runner.run(job["tool"], transformed)

        return {
            "score": float(score),
            "transform_hash": transform_engine.get_hash(),
            "dataset_hash": loader.get_hash(),
            "tool_version": tool_runner.get_version(job["tool"])
        }