"""Official PAN plagiarism detection evaluation metrics.

Implements the standard evaluation metrics from the PAN workshop series:
- Precision (character level)
- Recall (character level)
- Granularity
- PlagDet (combined primary score)

Based on the official reference implementation from PAN@CLEF 2014.
"""
from __future__ import annotations

import math
from typing import List, Tuple, Set, Dict, Any
from dataclasses import dataclass


@dataclass(frozen=True)
class TextSpan:
    """Represents a span of text with start offset and length."""
    offset: int
    length: int

    @property
    def end(self) -> int:
        return self.offset + self.length

    def overlap(self, other: TextSpan) -> int:
        """Calculate character overlap between two spans."""
        overlap_start = max(self.offset, other.offset)
        overlap_end = min(self.end, other.end)
        return max(0, overlap_end - overlap_start)


@dataclass(frozen=True)
class Detection:
    """A detected plagiarism alignment between suspicious and source document."""
    suspicious_span: TextSpan
    source_span: TextSpan


@dataclass
class PANMetrics:
    """PAN standard evaluation metrics result."""
    precision: float
    recall: float
    f1_score: float
    granularity: float
    plagdet: float

    def as_dict(self) -> Dict[str, float]:
        """Return metrics as dictionary for serialization."""
        return {
            "precision": round(self.precision, 6),
            "recall": round(self.recall, 6),
            "f1_score": round(self.f1_score, 6),
            "granularity": round(self.granularity, 6),
            "plagdet": round(self.plagdet, 6)
        }


def calculate_pan_metrics(
    ground_truth: List[Detection],
    predictions: List[Detection]
) -> PANMetrics:
    """Calculate official PAN plagiarism detection metrics.

    Implements the exact metrics defined in:
    Potthast et al. "Overview of the 2nd International Competition on Plagiarism Detection"

    Args:
        ground_truth: List of true plagiarism detections
        predictions: List of predicted plagiarism detections

    Returns:
        PANMetrics object with all calculated metrics
    """
    if not ground_truth:
        return PANMetrics(
            precision=1.0 if not predictions else 0.0,
            recall=1.0,
            f1_score=1.0 if not predictions else 0.0,
            granularity=1.0,
            plagdet=1.0 if not predictions else 0.0
        )

    if not predictions:
        return PANMetrics(
            precision=1.0,
            recall=0.0,
            f1_score=0.0,
            granularity=1.0,
            plagdet=0.0
        )

    # Calculate Precision
    precision_sum = 0.0
    for pred in predictions:
        max_overlap = 0
        for gt in ground_truth:
            overlap_susp = pred.suspicious_span.overlap(gt.suspicious_span)
            overlap_src = pred.source_span.overlap(gt.source_span)
            if overlap_susp > 0 and overlap_src > 0:
                max_overlap = max(max_overlap, overlap_susp)
        precision_sum += max_overlap / pred.suspicious_span.length

    precision = precision_sum / len(predictions)

    # Calculate Recall
    recall_sum = 0.0
    detected_ground_truth: Set[int] = set()
    detection_count_per_gt: Dict[int, int] = {i: 0 for i in range(len(ground_truth))}

    for gt_idx, gt in enumerate(ground_truth):
        max_overlap = 0
        for pred_idx, pred in enumerate(predictions):
            overlap_susp = pred.suspicious_span.overlap(gt.suspicious_span)
            overlap_src = pred.source_span.overlap(gt.source_span)
            if overlap_susp > 0 and overlap_src > 0:
                max_overlap = max(max_overlap, overlap_susp)
                detected_ground_truth.add(gt_idx)
                detection_count_per_gt[gt_idx] += 1
        recall_sum += max_overlap / gt.suspicious_span.length

    recall = recall_sum / len(ground_truth)

    # Calculate F1 Score
    if precision + recall > 0:
        f1_score = 2 * precision * recall / (precision + recall)
    else:
        f1_score = 0.0

    # Calculate Granularity
    if detected_ground_truth:
        total_detections = sum(detection_count_per_gt[gt_idx] for gt_idx in detected_ground_truth)
        granularity = total_detections / len(detected_ground_truth)
    else:
        granularity = 1.0

    # Calculate PlagDet
    # Formula: PlagDet = F1 / log2(1 + Granularity)
    if granularity > 0:
        plagdet = f1_score / math.log2(1 + granularity)
    else:
        plagdet = 0.0

    return PANMetrics(
        precision=precision,
        recall=recall,
        f1_score=f1_score,
        granularity=granularity,
        plagdet=plagdet
    )


def pan_macro_average(metrics_list: List[PANMetrics]) -> PANMetrics:
    """Calculate macro average across multiple document pairs.

    Args:
        metrics_list: List of PANMetrics objects for individual pairs

    Returns:
        Macro averaged PAN metrics
    """
    if not metrics_list:
        return PANMetrics(0.0, 0.0, 0.0, 1.0, 0.0)

    count = len(metrics_list)

    return PANMetrics(
        precision=sum(m.precision for m in metrics_list) / count,
        recall=sum(m.recall for m in metrics_list) / count,
        f1_score=sum(m.f1_score for m in metrics_list) / count,
        granularity=sum(m.granularity for m in metrics_list) / count,
        plagdet=sum(m.plagdet for m in metrics_list) / count
    )


def pan_micro_average(
    all_ground_truth: List[List[Detection]],
    all_predictions: List[List[Detection]]
) -> PANMetrics:
    """Calculate micro average across all detections.

    Micro averaging treats all characters equally across the entire dataset.

    Args:
        all_ground_truth: List of ground truth detections for each document pair
        all_predictions: List of predicted detections for each document pair

    Returns:
        Micro averaged PAN metrics
    """
    flat_ground_truth = []
    flat_predictions = []

    for gt_list, pred_list in zip(all_ground_truth, all_predictions):
        flat_ground_truth.extend(gt_list)
        flat_predictions.extend(pred_list)

    return calculate_pan_metrics(flat_ground_truth, flat_predictions)
