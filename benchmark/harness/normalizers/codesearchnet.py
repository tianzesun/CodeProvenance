from typing import Any, Dict, List
from benchmark.harness import Normalizer
from benchmark.harness.schemas import Sample


class CodeSearchNetNormalizer(Normalizer):
    """
    Normalize CodeSearchNet dataset rows into unified Sample format.
    Maps docstring -> prompt, function code -> code field.
    """

    def normalize(self, raw_rows: List[Dict[str, Any]]) -> List[Sample]:
        samples: List[Sample] = []

        for idx, row in enumerate(raw_rows):
            sample = Sample(
                id=f"csn-{row.get('language', 'python')}-{idx:06d}",
                dataset="codesearchnet",
                task="retrieval",
                split=row.get("partition", "test"),
                language=row.get("language", "python"),
                prompt=row["docstring"],
                code=row["code"],
                metadata={
                    "repo": row.get("repo"),
                    "path": row.get("path"),
                    "func_name": row.get("func_name"),
                    "original_docstring_tokens": row.get("docstring_tokens"),
                    "original_code_tokens": row.get("code_tokens"),
                    "raw_id": row.get("url"),
                }
            )
            samples.append(sample)

        return samples
