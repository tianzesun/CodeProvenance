"""
Experiment Planner - Job Matrix Generator.

Expands an Experiment definition into the complete Cartesian product of
all experimental parameters. This generates the full set of micro-jobs
for distributed execution.
"""

from typing import List, Dict, Any
from uuid import uuid4
from .experiment import Experiment


class ExperimentPlanner:
    """
    Builds the complete job matrix from an experiment definition.
    
    Generates the full Cartesian product:
    Dataset × Transform × Tool × Task × Repetition
    """

    @staticmethod
    def build_job_matrix(experiment: Experiment) -> List[Dict[str, Any]]:
        """
        Build complete job matrix for distributed execution.

        Args:
            experiment: Complete experiment definition

        Returns:
            List of individual micro-jobs
        """
        jobs = []

        for tool in experiment.tools:
            for transform in experiment.transforms:
                for task in experiment.tasks:
                    for run_id in range(experiment.n_runs):

                        job = {
                            "job_id": str(uuid4())[:8],
                            "experiment_id": experiment.experiment_id,
                            "dataset": experiment.dataset,
                            "tool": tool,
                            "transform": transform,
                            "task": task,
                            "run_id": run_id,
                            "status": "pending",
                            "attempt": 0,
                            "created_at": None,
                            "completed_at": None
                        }

                        jobs.append(job)

        return jobs

    @staticmethod
    def estimate_runtime(jobs: List[Dict[str, Any]], seconds_per_job: float = 15.0) -> Dict[str, float]:
        """Estimate total runtime for given job count."""
        total_jobs = len(jobs)
        return {
            "total_jobs": total_jobs,
            "sequential_runtime_hours": (total_jobs * seconds_per_job) / 3600,
            "parallel_10_runtime_hours": (total_jobs * seconds_per_job) / 3600 / 10,
            "parallel_100_runtime_hours": (total_jobs * seconds_per_job) / 3600 / 100
        }