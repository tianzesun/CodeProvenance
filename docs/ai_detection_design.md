# AI Code Detection Engine — Design Document
**Goal:** Build the most accurate AI-generated code detector, surpassing Turnitin

## Executive Summary

Turnitin's AI detector (launched 2023) is optimized for **prose**, not code. It struggles with:
- Code structure vs. natural language (syntax-constrained writing)
- Language-specific idioms that appear "formulaic" but are human-written
- Adversarial resistance (easy to fool with variable renaming, comment removal)
- Model fingerprinting (can't distinguish GPT-4 vs Claude vs Copilot)
- Code-specific patterns (imports, algorithms, boilerplate)

**Our advantages:**
1. **Code-native signals** — AST parsing, structural entropy, language-specific patterns
2. **Multi-model fingerprinting** — Detect which AI tool was used (GPT-4, Claude, Copilot, Gemini)
3. **Temporal consistency** — Compare student's historical coding style
4. **Adversarial robustness** — Resistant to variable renaming, comment stripping, paraphrasing
5. **Explainability** — Line-level heatmaps showing why code was flagged

---

## Current System Analysis

### Existing Signals (from `ai_detection.py`)
| Signal | Weight | Strengths | Weaknesses |
|--------|--------|-----------|------------|
| Perplexity | 0.18 | Measures predictability | Bigram-based (not transformer) |
| Burstiness | 0.14 | Line length variance | Misses multi-line statements |
| Stylometry | 0.16 | Naming conventions | No AST awareness |
| Pattern Library | 0.20 | Comment patterns | Regex-only, easily bypassed |
| Structural Entropy | 0.12 | Indent uniformity | Language-agnostic |
| Vocabulary Richness | 0.08 | Token diversity | No semantic understanding |
| Whitespace Rhythm | 0.06 | Spacing patterns | Low discriminative power |
| Docstring Density | 0.06 | Comment frequency | Language-dependent |

**Overall:** Heuristic-based, no ML, no ground-truth calibration, no adversarial testing.

---

## Proposed Enhancements

### 1. Transformer-Based Perplexity (Task 2)
**Replace:** Bigram frequency analysis  
**With:** GPT-2 tokenizer + actual perplexity calculation

```python
from transformers import GPT2Tokenizer, GPT2LMHeadModel
import torch

def compute_perplexity(code: str) -> float:
    """Real perplexity using GPT-2."""
    tokenizer = GPT2Tokenizer.from_pretrained("gpt2")
    model = GPT2LMHeadModel.from_pretrained("gpt2")
    inputs = tokenizer(code, return_tensors="pt", truncation=True, max_length=1024)
    with torch.no_grad():
        outputs = model(**inputs, labels=inputs["input_ids"])
        loss = outputs.loss
    return torch.exp(loss).item()
```

**Expected gain:** 15-20% accuracy improvement (true token-level analysis)

---

### 2. Model Fingerprinting (Task 3)
AI models have distinct signatures:

| Model | Signature Patterns |
|-------|-------------------|
| **GPT-4/4o** | "Here's", "Let's", "This function", excessive docstrings, snake_case everywhere |
| **Claude 3** | "I'll", "We can", type hints everywhere, defensive error handling |
| **GitHub Copilot** | Minimal comments, idiomatic patterns, follows repo style |
| **Gemini** | "To [verb]", functional style, explicit variable names |

**Implementation:**
- 50+ regex patterns per model
- Comment syntax analysis (GPT loves "# Step 1:", Claude uses "# Note:")
- Naming convention fingerprints (GPT prefers `process_data`, Claude prefers `processData`)
- Error handling patterns (Claude wraps everything in try/except)

---

### 3. AST-Based Structural Analysis (Task 4)
**Why AST:** Syntax-aware detection immune to variable renaming

```python
import ast

def ast_features(code: str) -> dict:
    """Extract AI-suspicious patterns from AST."""
    tree = ast.parse(code)
    return {
        "function_length_uniformity": cv([len(ast.unparse(f)) for f in ast.walk(tree) if isinstance(f, ast.FunctionDef)]),
        "nested_if_depth": max_depth(tree, ast.If),
        "docstring_to_code_ratio": count_docstrings(tree) / count_statements(tree),
        "import_clustering": are_imports_at_top(tree),  # AI always puts imports first
        "dead_code_presence": has_unreachable_code(tree),
        "variable_reuse_pattern": measure_var_reuse(tree),
        "function_call_diversity": unique_functions(tree) / total_calls(tree)
    }
```

**Key insight:** AI code has:
- Uniform function lengths (80-120 lines consistently)
- Perfect import organization (always alphabetical, grouped)
- Defensive try/except even for simple operations
- Consistent indentation (never mixed spaces/tabs)

---

### 4. Adversarial Resistance (Task 5)
**Attack vectors students use:**
1. Variable renaming (`process_data` → `pd`, `result` → `r`)
2. Comment removal (strip all `# This function...`)
3. Code reorganization (move functions around)
4. Paraphrasing (ask AI to "rewrite in a different style")

**Defenses:**
- **Semantic fingerprinting:** Hash AST structure ignoring names → detects renamed code
- **Style-invariant signals:** Perplexity/burstiness on AST, not text
- **Temporal comparison:** If student's style suddenly changes, flag it
- **Paraphrase detection:** Embedding similarity between original and "rewritten" versions

```python
def semantic_hash(code: str) -> str:
    """AST-based hash immune to variable renaming."""
    tree = ast.parse(code)
    # Replace all names with placeholders
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            node.id = "VAR"
    return hashlib.sha256(ast.unparse(tree).encode()).hexdigest()
```

---

### 5. Ensemble Classifier (Task 6)
**Why ensemble:** Single signals are weak; ML fusion is stronger

**Architecture:**
- **Input:** 30+ features from all signals
- **Model:** LightGBM (fast, interpretable, handles feature interactions)
- **Training data:** 5,000 labeled examples (2,500 AI, 2,500 human)
  - AI: GPT-4, Claude, Copilot, Gemini, CodeLlama
  - Human: GitHub repos, Kaggle submissions, student assignments

```python
import lightgbm as lgb

def train_ensemble(X_train, y_train):
    """Train LightGBM classifier on all signals."""
    params = {
        'objective': 'binary',
        'metric': 'auc',
        'learning_rate': 0.05,
        'num_leaves': 31,
        'feature_fraction': 0.8,
        'bagging_fraction': 0.8
    }
    model = lgb.train(params, lgb.Dataset(X_train, y_train), num_boost_round=500)
    return model
```

**Expected gain:** 25-30% improvement over weighted average

---

### 6. Temporal Consistency Check (Task 7)
**Key insight:** Students have consistent coding styles across assignments

```python
def temporal_anomaly_score(student_id: str, new_code: str) -> float:
    """Detect if new code differs from student's historical style."""
    history = get_student_submissions(student_id)
    if len(history) < 2:
        return 0.0  # Not enough history
    
    historical_features = [extract_style_features(c) for c in history]
    new_features = extract_style_features(new_code)
    
    # Mahalanobis distance from historical mean
    mean_historical = np.mean(historical_features, axis=0)
    cov = np.cov(historical_features, rowvar=False)
    distance = mahalanobis(new_features, mean_historical, np.linalg.inv(cov))
    
    # Normalize to [0,1]
    return min(1.0, distance / 10.0)
```

**Use case:** Student submits 5 assignments in typical style, then submission 6 is GPT-4 → temporal score spikes

---

### 7. Calibration & Benchmarking (Task 8)
**Ground truth dataset:**
- 1,000 verified AI-generated samples (prompt → code, timestamped)
- 1,000 verified human samples (GitHub commits, video-recorded coding sessions)
- 500 adversarial samples (AI code with manual obfuscation)

**Metrics:**
- **Precision:** % of flagged code that is actually AI (avoid false positives)
- **Recall:** % of AI code that is caught (avoid false negatives)
- **F1 Score:** Harmonic mean
- **AUC-ROC:** Discriminative power

**Turnitin comparison:**
| Metric | Turnitin (est.) | Our System (goal) |
|--------|-----------------|-------------------|
| Precision | 0.75 | **0.90** |
| Recall | 0.60 | **0.85** |
| F1 | 0.67 | **0.87** |
| Adversarial Resistance | Low | **High** |

---

### 8. Explainability (Task 9)
**Line-level heatmap:** Show which code blocks are AI-suspicious

```python
def explain_detection(code: str, ai_probability: float) -> dict:
    """Generate line-level explanations."""
    lines = code.split('\n')
    line_scores = []
    
    for i, line in enumerate(lines):
        # Score each line independently
        local_signals = compute_signals(line)
        line_ai_prob = fuse(local_signals)
        
        # Identify specific patterns
        flags = []
        if has_ai_comment(line):
            flags.append("AI-typical comment")
        if overly_defensive(line):
            flags.append("Excessive error handling")
        if too_descriptive_name(line):
            flags.append("Unnaturally verbose naming")
        
        line_scores.append({
            "line_num": i + 1,
            "ai_probability": line_ai_prob,
            "flags": flags,
            "text": line
        })
    
    return {
        "overall_probability": ai_probability,
        "line_scores": line_scores,
        "top_suspicious_lines": sorted(line_scores, key=lambda x: x['ai_probability'], reverse=True)[:10]
    }
```

**Frontend visualization:** Color-coded editor (red = high AI likelihood, green = human-like)

---

### 9. API Design (Task 10)

```python
# Synchronous mode
POST /api/ai-detect
{
  "code": "def process_data(data):\n    ...",
  "language": "python",
  "student_id": "student123",  # optional, for temporal analysis
  "options": {
    "model_fingerprinting": true,
    "temporal_check": true,
    "explainability": true,
    "threshold": 0.75  # only flag if > 75% confidence
  }
}

Response:
{
  "ai_probability": 0.87,
  "confidence": 0.92,
  "verdict": "likely_ai",
  "detected_model": "GPT-4",
  "signals": { ... },
  "temporal_anomaly": 0.65,
  "explanation": { "line_scores": [ ... ] },
  "processing_time_ms": 234
}

# Batch mode
POST /api/ai-detect/batch
{
  "submissions": [
    {"id": "sub1", "code": "...", "language": "python"},
    {"id": "sub2", "code": "...", "language": "java"}
  ]
}

# Streaming mode (for large files)
POST /api/ai-detect/stream
Content-Type: text/event-stream
```

---

## Implementation Roadmap

### Phase 1: Core Improvements (Tasks 2-4) — Week 1
- Integrate GPT-2 perplexity
- Build model fingerprinting library
- Add AST-based analysis

**Deliverable:** 60-70% accuracy on test set

### Phase 2: Robustness (Tasks 5-6) — Week 2
- Implement adversarial defenses
- Train ensemble classifier
- Collect & label training data (500 samples minimum)

**Deliverable:** 80-85% accuracy, resistant to basic obfuscation

### Phase 3: Polish (Tasks 7-10) — Week 3
- Add temporal consistency
- Build calibration pipeline
- Implement explainability UI
- API refinements

**Deliverable:** 90%+ accuracy, production-ready, beats Turnitin

---

## Success Criteria

**Must exceed Turnitin on:**
1. ✅ Precision (fewer false positives)
2. ✅ Recall (catch more AI code)
3. ✅ Adversarial resistance (can't be fooled easily)
4. ✅ Code-specific accuracy (better on Python/Java than prose-focused detector)
5. ✅ Explainability (line-level feedback vs. opaque score)

**Target metrics:**
- F1 > 0.85
- False positive rate < 10%
- Processing time < 500ms per submission
- Supports 10+ languages (Python, Java, C++, JavaScript, Go, Rust, etc.)

---

## Next Steps

1. Install dependencies: `transformers`, `lightgbm`, `torch`
2. Build transformer perplexity module (Task 2)
3. Create model fingerprinting patterns (Task 3)
4. Implement AST analyzer (Task 4)
5. Collect training data for ensemble (Task 6)
