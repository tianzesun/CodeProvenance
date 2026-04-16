from typing import Any, Dict, List
from benchmark.harness import Normalizer
from benchmark.harness.schemas import Sample


class HumanEvalNormalizer(Normalizer):
    """
    Normalize HumanEval dataset rows into unified Sample format.
    Handles HumanEval JSONL format with prompt, test, and entry_point fields.
    """

    def normalize(self, raw_rows: List[Dict[str, Any]]) -> List[Sample]:
        samples: List[Sample] = []

        for idx, row in enumerate(raw_rows):
            sample = Sample(
                id=row["task_id"],
                dataset="human_eval",
                task="generation_exec",
                split="test",
                language="python",
                prompt=row["prompt"],
                tests=[row["test"]],
                entry_point=row["entry_point"],
                metadata={
                    "raw_id": row["task_id"],
                    "canonical_solution": row.get("canonical_solution"),
                }
            )
            samples.append(sample)

        return samples
