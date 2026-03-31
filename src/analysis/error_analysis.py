"""Error analysis for detection weaknesses."""
from typing import Dict, List, Any, Tuple
from dataclasses import dataclass
from collections import defaultdict
from datetime import datetime


@dataclass
class ErrorCase:
    file_a: str
    file_b: str
    predicted_score: float
    actual_label: bool
    error_type: str
    characteristics: Dict[str, Any] = None


@dataclass
class ErrorAnalysisResult:
    total: int
    false_positives: int
    false_negatives: int
    error_rate: float
    error_cases: List[ErrorCase]
    patterns: Dict[str, int]
    recommendations: List[str]
    analyzed_at: str = ""


class ErrorAnalyzer:
    def __init__(self, threshold: float = 0.5):
        self.threshold = threshold

    def analyze(self, predictions: List[Tuple[str, str, float, bool]]) -> ErrorAnalysisResult:
        errors = []
        fp = fn = 0
        patterns = defaultdict(int)
        for fa, fb, score, is_clone in predictions:
            pred = score >= self.threshold
            if not is_clone and pred:
                fp += 1
                errors.append(ErrorCase(fa, fb, score, is_clone, 'false_positive'))
                patterns['structural'] += 1
            elif is_clone and not pred:
                fn += 1
                errors.append(ErrorCase(fa, fb, score, is_clone, 'false_negative'))
                patterns['semantic'] += 1
        total = len(predictions)
        rate = (fp + fn) / max(total, 1)
        recs = []
        if fp > fn:
            recs.append("High FP: consider increasing threshold or improving filtering.")
        elif fn > fp:
            recs.append("High FN: consider decreasing threshold or enabling semantic analysis.")
        if fp + fn > 10:
            recs.append(f"Found {fp+fn} error cases suitable for training data.")
        return ErrorAnalysisResult(total, fp, fn, rate, errors, dict(patterns), recs, datetime.now().isoformat())

    def export_training_data(self, errors: List[ErrorCase], path: str) -> None:
        import json
        with open(path, 'w') as f:
            json.dump([{'file_a': e.file_a, 'file_b': e.file_b, 'label': 1 if e.actual_label else 0,
                        'error_type': e.error_type} for e in errors], f, indent=2)
