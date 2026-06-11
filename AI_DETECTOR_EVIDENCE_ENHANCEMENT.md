# AI Detector - Enhanced Evidence Display ✅

## Overview
Enhanced the AI Detector results page to display comprehensive evidence that professors can trust and understand. The system now shows detailed code characteristics, AI-specific patterns, and signal breakdowns to support academic integrity decisions.

## What's New

### 1. **Code Characteristics Section**
Displays quantitative metrics about the submitted code:
- **Total Lines**: Number of lines in the code
- **Functions**: Count of function definitions
- **Type Hints**: Number of type annotations (high count suggests AI)
- **Docstring Ratio**: Percentage of functions with docstrings (high ratio suggests AI)
- **Comment Ratio**: Percentage of lines that are comments
- **Average Line Length**: Average characters per line

**Why This Matters**: AI-generated code typically has:
- Very high docstring ratios (AI adds docstrings to almost every function)
- Many type hints (AI uses type hints extensively)
- Formal, consistent structure

### 2. **AI-Specific Patterns Detected**
Shows concrete evidence of AI patterns found in the code:

#### Pattern Types:
- **Docstring Patterns**: Formal docstrings with triple quotes
  - Example: `"""Process input data and return statistics."""`
  - AI Indicator: Docstrings on every function, even trivial ones

- **Comment Patterns**: Formal, generic comments
  - Examples: "Let's process", "Here we initialize", "This function"
  - AI Indicator: Formal, instructional tone

- **Type Hint Patterns**: Type annotations
  - Examples: `Optional[List[str]]`, `Dict[str, int]`, `-> Dict`
  - AI Indicator: Extensive use of complex type hints

- **Exception Handling**: Explicit error handling
  - Examples: `raise ValueError()`, `raise TypeError()`
  - AI Indicator: Defensive programming patterns

- **Logging Statements**: Logging calls
  - Examples: `logging.info()`, `logging.error()`
  - AI Indicator: Production-grade logging

- **Import Patterns**: Standard library imports
  - Examples: `import logging`, `from typing import`
  - AI Indicator: Comprehensive imports

**Why This Matters**: Each pattern is clickable and shows:
- Line number where pattern appears
- Exact code snippet
- Count of occurrences
- First 3 examples with "show more" option

### 3. **Signal Breakdown**
Detailed analysis of 8 independent signals:

1. **Perplexity (Token Entropy)** - 18% weight
   - Measures code predictability
   - Low entropy = AI-like (high score)

2. **Burstiness** - 14% weight
   - Code complexity variation
   - Uniform patterns = AI-like (high score)

3. **Stylometry** - 16% weight
   - Code style profile (comments, naming, type hints)
   - Formal style = AI-like (high score)

4. **Pattern Library** - 20% weight
   - 40+ regex patterns from GPT-4, Claude, Copilot
   - Highest weight signal

5. **Structural Entropy** - 12% weight
   - AST uniformity
   - Uniform syntax trees = AI-like (high score)

6. **Vocabulary Richness** - 8% weight
   - Token diversity
   - Limited vocabulary = AI-like (high score)

7. **Whitespace Rhythm** - 6% weight
   - Blank-line spacing regularity
   - Regular spacing = AI-like (high score)

8. **Docstring Density** - 6% weight
   - Documentation prevalence
   - High density = AI-like (high score)

### 4. **Annotated Code Display**
Shows first 60 lines of submitted code with:
- Line numbers
- Flagged lines highlighted in amber
- Exact code text
- Visual indication of AI pattern matches

## How Professors Should Use This

### Step 1: Check Overall Score
- **70%+**: High confidence AI generation - warrants investigation
- **40-70%**: Moderate confidence - review evidence carefully
- **<40%**: Low confidence - likely human-written

### Step 2: Review Code Characteristics
Look for suspicious patterns:
- ✅ High docstring ratio (>50%) = suspicious
- ✅ Many type hints (>20% of lines) = suspicious
- ✅ Very consistent line lengths = suspicious
- ✅ High comment ratio (>30%) = suspicious

### Step 3: Examine AI-Specific Patterns
- Count of detected patterns
- Concentration of patterns (all in one section vs. spread out)
- Whether patterns match student's prior work

### Step 4: Review Signal Breakdown
- Which signals are high (>0.7)?
- Do multiple signals agree?
- Are there contradictions?

### Step 5: Check Annotated Code
- Look at flagged lines
- Do they match the detected patterns?
- Does the code style seem consistent with student's prior submissions?

## Evidence-Based Decision Making

### Strong Indicators of AI Generation:
✅ Multiple signals >0.7 (especially Pattern Library, Perplexity, Stylometry)
✅ High docstring ratio (>60%)
✅ Many type hints (>30% of lines)
✅ Formal, generic comments
✅ Consistent code structure
✅ 40+ detected AI patterns

### Weak Indicators (Could Be False Positives):
⚠️ Single signal >0.7 (others low)
⚠️ Code following best practices (type hints, docstrings)
⚠️ Well-documented code
⚠️ Code from tutorials or examples
⚠️ Code written with instructor guidance

## Important Limitations

1. **Not Definitive Proof**: This tool detects patterns, not proof of AI generation
2. **False Positives Possible**: Well-written human code can match AI patterns
3. **False Negatives Possible**: Modified AI code might not be detected
4. **Context Matters**: 
   - Code written during office hours
   - Code with instructor guidance
   - Code using AI as a learning tool
   - Code from tutorials/examples

5. **Language Specific**: Calibrated for Python; other languages may be less reliable

## Recommended Workflow

### For Suspected AI Generation:
1. ✅ Review the evidence on this page
2. ✅ Compare with student's prior submissions
3. ✅ Check submission timestamps and edit history
4. ✅ Conduct code walkthrough or interview
5. ✅ Ask student to explain specific code sections
6. ✅ Review institutional AI usage policy

### For Borderline Cases (40-70%):
1. ✅ Request student explanation
2. ✅ Ask about development process
3. ✅ Check if code matches student's skill level
4. ✅ Review prior submissions for style consistency
5. ✅ Consider giving benefit of doubt if evidence is weak

## Technical Details

### Backend Enhancement
Added three helper functions to extract evidence:

1. **`_extract_ai_evidence_patterns()`**
   - Scans code for 6 pattern types
   - Returns line numbers and code snippets
   - Limits to first 30 occurrences per type

2. **`_generate_signal_interpretations()`**
   - Creates human-readable signal descriptions
   - Color-codes by strength (🔴 strong, 🟡 moderate, 🟢 weak)
   - Includes interpretation guidance

3. **`_compute_code_metrics()`**
   - Calculates 10 code statistics
   - Computes ratios (docstring, comment)
   - Analyzes code structure

### Frontend Enhancement
Enhanced `SubmissionCard` component to display:
- Code characteristics grid (6 metrics)
- Evidence patterns section (6 pattern types)
- Signal breakdown (8 signals)
- Annotated code (first 60 lines)

## Files Modified

### Backend
- `src/backend/api/server.py`
  - Added `_extract_ai_evidence_patterns()`
  - Added `_generate_signal_interpretations()`
  - Added `_compute_code_metrics()`
  - Enhanced `_build_ai_detection_summary()` to include new fields

### Frontend
- `src/frontend/app/ai-detector/results/[id]/page.tsx`
  - Enhanced `SubmissionCard` component
  - Added code characteristics display
  - Added evidence patterns display
  - Improved signal breakdown layout

## Testing

### Backend Testing
```bash
source venv/bin/activate
python -c "
from src.backend.api.server import _extract_ai_evidence_patterns, _generate_signal_interpretations, _compute_code_metrics

code = '''
import logging
from typing import Optional, List, Dict

def process_data(data: Optional[List[str]]) -> Dict[str, int]:
    \"\"\"Process input data and return statistics.\"\"\"
    logging.info('Starting')
    if data is None:
        raise ValueError('Data cannot be None')
    return {}
'''

patterns = _extract_ai_evidence_patterns(code, 'python')
print(f'Patterns: {list(patterns.keys())}')

signals = {'perplexity': 0.3, 'burstiness': 0.7}
interps = _generate_signal_interpretations(signals)
print(f'Interpretations: {len(interps)} signals')

metrics = _compute_code_metrics(code)
print(f'Metrics: {list(metrics.keys())}')
"
```

### Frontend Testing
1. Upload a Python file with type hints and docstrings
2. Click "Run AI Detector"
3. Expand the results card
4. Verify all sections display:
   - ✅ Code Characteristics
   - ✅ AI-Specific Patterns
   - ✅ Signal Breakdown
   - ✅ Annotated Code

## Future Enhancements

1. **Comparative Analysis**: Compare with student's prior submissions
2. **Confidence Intervals**: Show uncertainty ranges
3. **Export Reports**: PDF/CSV export with evidence
4. **Batch Analysis**: Analyze entire class at once
5. **Feedback Loop**: Collect professor feedback to improve calibration
6. **Multi-Language Support**: Extend to Java, JavaScript, C++, etc.
7. **Humanizer Detection**: Detect code modified by humanizer tools
8. **Plagiarism Integration**: Cross-reference with plagiarism detection

## Conclusion

The enhanced AI Detector now provides professors with:
- **Explainable Evidence**: Every score is traceable to specific patterns
- **Multiple Signals**: 8 independent signals reduce false positives
- **Code Characteristics**: Quantitative metrics for comparison
- **Pattern Detection**: Concrete examples of AI-specific code patterns
- **Confidence Calibration**: Realistic confidence scores with limitations

This evidence-based approach enables informed decision-making while acknowledging the limitations of automated detection.
