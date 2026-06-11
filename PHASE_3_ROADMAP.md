# Phase 3 Roadmap: Fusion & Calibration Layer

## Overview
Phase 3 focuses on aggregating the 8 independent signals into a reliable, calibrated AI detection score with confidence metrics and false positive reduction.

## Architecture

### Signal Aggregation
```
Signal Scores (8 signals)
    ↓
Signal Reliability Assessment
    ↓
Signal Agreement Analysis
    ↓
Weighted Aggregation
    ↓
Confidence Calibration
    ↓
False Positive Reduction
    ↓
Final AI Probability + Confidence
```

## Implementation Tasks

### Task 3.1: Signal Reliability Framework
**Objective**: Assign reliability scores to each signal based on code characteristics

**Implementation**:
- Create `src/backend/engines/ai/reliability.py`
- Implement `assess_signal_reliability(signal_name: str, code: str) -> float`
- For each signal, determine reliability based on:
  - Code length (some signals need minimum code)
  - Language (Python vs other)
  - Code structure (some signals need functions/classes)
  - Entropy levels (extreme values indicate unreliability)

**Reliability Factors**:
- Perplexity: Reliable for code > 100 tokens
- Burstiness: Reliable for code > 5 lines
- Stylometry: Reliable for code > 50 lines
- Pattern Library: Reliable for all code
- Structural Entropy: Reliable for Python with functions
- Vocabulary Richness: Reliable for code > 20 tokens
- Whitespace Rhythm: Reliable for code > 10 lines
- Docstring Density: Reliable for code with functions

**Tests**: 8 tests (one per signal)

### Task 3.2: Signal Agreement Analysis
**Objective**: Detect when signals agree or contradict each other

**Implementation**:
- Create `src/backend/engines/ai/agreement.py`
- Implement `analyze_signal_agreement(signals: SignalScores) -> Dict`
- Return:
  - `agreement_level`: "high" / "medium" / "low"
  - `supporting_signals`: List of signals > 0.6
  - `contradicting_signals`: List of signals < 0.4
  - `neutral_signals`: List of signals 0.4-0.6
  - `agreement_score`: 0.0-1.0

**Agreement Logic**:
- High agreement: 6+ signals in same direction (all high or all low)
- Medium agreement: 4-5 signals in same direction
- Low agreement: 3 or fewer signals in same direction

**Tests**: 6 tests (high/medium/low agreement scenarios)

### Task 3.3: Weighted Signal Aggregation
**Objective**: Combine signals with weights and reliability adjustments

**Implementation**:
- Create `src/backend/engines/ai/aggregation.py`
- Implement `aggregate_signals(signals: SignalScores, reliabilities: Dict) -> float`
- Algorithm:
  1. Adjust each signal by reliability: `adjusted_score = signal * reliability`
  2. Apply weights: `weighted_score = adjusted_score * weight`
  3. Sum: `final_score = Σ(weighted_score)`
  4. Normalize: `final_score = final_score / Σ(reliability * weight)`

**Tests**: 8 tests (various signal combinations)

### Task 3.4: Confidence Calibration
**Objective**: Assign confidence scores based on signal agreement and reliability

**Implementation**:
- Create `src/backend/engines/ai/confidence.py`
- Implement `calibrate_confidence(signals: SignalScores, reliabilities: Dict, agreement: Dict) -> float`
- Confidence factors:
  - Signal agreement (high agreement → high confidence)
  - Signal reliability (high reliability → high confidence)
  - Signal variance (low variance → high confidence)
  - Extreme scores (very high/low → high confidence)

**Confidence Calculation**:
```
base_confidence = (agreement_score + avg_reliability) / 2
variance_penalty = signal_variance / 0.25  # Penalize high variance
extreme_bonus = 0.1 if any signal > 0.8 or < 0.2 else 0.0
final_confidence = max(0.0, min(1.0, base_confidence - variance_penalty + extreme_bonus))
```

**Tests**: 10 tests (various confidence scenarios)

### Task 3.5: False Positive Reduction
**Objective**: Implement safeguards to reduce false positives

**Implementation**:
- Create `src/backend/engines/ai/false_positive_reduction.py`
- Implement `apply_false_positive_reduction(ai_score: float, confidence: float, signals: SignalScores) -> Tuple[float, float]`

**Safeguards**:
1. **Single Signal Dominance**: If only 1 signal is elevated (> 0.6) and others are low (< 0.4), reduce confidence by 30%
2. **Contradiction Detection**: If signals contradict (some > 0.7, others < 0.3), reduce confidence by 20%
3. **Low Reliability**: If average reliability < 0.5, reduce confidence by 25%
4. **Extreme Variance**: If signal variance > 0.3, reduce confidence by 15%
5. **Confidence Floor**: Never allow confidence below 0.3 for scores 0.4-0.6 (medium risk)

**Tests**: 8 tests (each safeguard + combinations)

### Task 3.6: Risk Categorization
**Objective**: Map AI probability to risk categories with confidence

**Implementation**:
- Update `src/backend/engines/ai/models.py` with enhanced risk categorization
- Implement `categorize_risk(ai_probability: float, confidence: float) -> Dict`
- Return:
  - `risk_level`: "Very Low" / "Low" / "Moderate" / "Elevated" / "High"
  - `risk_score`: 0.0-1.0
  - `confidence`: 0.0-1.0
  - `supporting_signals`: List of signals
  - `contradicting_signals`: List of signals

**Risk Thresholds**:
- Very Low: ai_probability < 0.25, confidence > 0.6
- Low: 0.25 ≤ ai_probability < 0.45, confidence > 0.5
- Moderate: 0.45 ≤ ai_probability < 0.65, confidence > 0.4
- Elevated: 0.65 ≤ ai_probability < 0.80, confidence > 0.3
- High: ai_probability ≥ 0.80, confidence > 0.2

**Tests**: 10 tests (all risk categories + boundary conditions)

### Task 3.7: Integration Tests
**Objective**: Test the complete fusion pipeline

**Implementation**:
- Create `tests/unit/test_ai_detector_fusion.py`
- Test complete pipeline: signals → reliability → agreement → aggregation → confidence → risk

**Test Scenarios**:
1. All signals high (AI-like code)
2. All signals low (human-like code)
3. Mixed signals (contradictory)
4. Single signal high (false positive risk)
5. Low reliability code
6. Edge cases (empty, very short, syntax errors)

**Tests**: 12 tests

### Task 3.8: Checkpoint - Fusion Layer Complete
**Objective**: Verify all fusion components work correctly

**Verification**:
- All 12 integration tests passing
- All 8 signal tests still passing
- All 28 model tests still passing
- Code formatted and linted
- Documentation complete

## File Structure

```
src/backend/engines/ai/
├── models.py (existing, update risk categorization)
├── signals.py (existing, complete)
├── reliability.py (NEW)
├── agreement.py (NEW)
├── aggregation.py (NEW)
├── confidence.py (NEW)
├── false_positive_reduction.py (NEW)
└── fusion.py (NEW - orchestrator)

tests/unit/
├── test_ai_detector_models.py (existing)
├── test_ai_detector_signals.py (existing)
└── test_ai_detector_fusion.py (NEW)
```

## Success Criteria

- ✅ All 8 signals properly weighted and aggregated
- ✅ Confidence calibration accurate and reliable
- ✅ False positive reduction effective
- ✅ Risk categorization clear and actionable
- ✅ 60+ new tests, all passing
- ✅ Code quality standards met
- ✅ Documentation complete

## Estimated Effort

- Task 3.1: 2-3 hours
- Task 3.2: 2-3 hours
- Task 3.3: 2-3 hours
- Task 3.4: 3-4 hours
- Task 3.5: 3-4 hours
- Task 3.6: 2-3 hours
- Task 3.7: 3-4 hours
- Task 3.8: 1-2 hours

**Total**: 18-26 hours

## Next Phase (Phase 4)

After Phase 3 is complete, Phase 4 will focus on:
- Integration with detection pipeline
- Report generation
- Evidence annotation
- Instructor-facing insights
- API endpoints
