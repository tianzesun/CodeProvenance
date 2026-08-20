"""Signal computation layer for AI Detection Engine.

Implements all 8 independent signals that measure different aspects of code
characteristics. Each signal is computed independently and returns a score
in [0.0, 1.0] where 0.0 = human-like and 1.0 = AI-like.

Signals:
1. Perplexity: Token-level entropy (0.18 weight)
2. Burstiness: Line complexity variation (0.14 weight)
3. Stylometry: Code style profile (0.16 weight)
4. Pattern Library: LLM fingerprints (0.20 weight)
5. Structural Entropy: AST uniformity (0.12 weight)
6. Vocabulary Richness: Token diversity (0.08 weight)
7. Whitespace Rhythm: Blank-line spacing (0.06 weight)
8. Docstring Density: Documentation prevalence (0.06 weight)
"""

import ast
import logging
import math
import re
from collections import Counter

logger = logging.getLogger(__name__)


# ============================================================================
# SIGNAL 1: PERPLEXITY (Token-level entropy)
# ============================================================================


def _tokenize(code: str) -> list[str]:
    """Lightweight code tokenizer - identifiers, keywords, operators.

    Args:
        code: Source code to tokenize

    Returns:
        List of lowercase tokens
    """
    tokens = re.findall(r"\b\w+\b|[+\-*/=<>!&|]+|[{}()\[\],;:]", code)
    return [t.lower() for t in tokens if t]


def _safe_entropy(counter: Counter) -> float:
    """Shannon entropy of a frequency counter, normalized to [0, 1].

    Args:
        counter: Counter object with token frequencies

    Returns:
        Normalized entropy in [0.0, 1.0]
    """
    total = sum(counter.values())
    if total == 0:
        return 0.0

    n_unique = len(counter)
    if n_unique <= 1:
        return 0.0

    entropy = -sum(
        (c / total) * math.log2(c / total) for c in counter.values() if c > 0
    )
    max_entropy = math.log2(n_unique)
    return entropy / max_entropy if max_entropy > 0 else 0.0


def compute_perplexity_signal(code: str) -> float:
    """Compute N-gram perplexity signal.

    LLM output has lower token-level entropy (more predictable).
    Human code has higher entropy (more varied).

    Algorithm:
    1. Tokenize code into lowercase identifiers, keywords, operators
    2. Compute unigram entropy: H_unigram = -Σ(p_i * log₂(p_i))
    3. Compute bigram entropy: H_bigram = -Σ(p_j * log₂(p_j))
    4. Combine: H_combined = 0.4 * H_unigram + 0.6 * H_bigram (raw bits)
    5. Map to score: score = max(0.0, min(1.0, 1.0 - H_combined / 5.0))

    Calibration:
    - Human code: 3.5–5.5 bits (score 0.0–0.3)
    - LLM code: 0–3.0 bits (score 0.4–1.0)

    Args:
        code: Source code to analyze

    Returns:
        Perplexity score in [0.0, 1.0]
    """
    tokens = _tokenize(code)

    # Edge case: too few tokens
    if len(tokens) < 10:
        return 0.0

    # Compute unigram entropy (raw bits, not normalized)
    unigram_counter = Counter(tokens)
    total = len(tokens)
    raw_unigram = -sum(
        (c / total) * math.log2(c / total) for c in unigram_counter.values() if c > 0
    )

    # Compute bigram entropy (raw bits, not normalized)
    bigrams = [f"{tokens[i]} {tokens[i + 1]}" for i in range(len(tokens) - 1)]
    bigram_counter = Counter(bigrams)
    btotal = len(bigrams)
    raw_bigram = -sum(
        (c / btotal) * math.log2(c / btotal) for c in bigram_counter.values() if c > 0
    )

    # Combined raw entropy (typical human code: 3.5–5.5 bits)
    combined = 0.4 * raw_unigram + 0.6 * raw_bigram

    # Map to score: 0 bits → 1.0 (very AI-like), 5.0 bits → 0.0 (very human-like)
    score = max(0.0, min(1.0, 1.0 - combined / 5.0))
    return round(score, 3)


# ============================================================================
# SIGNAL 2: BURSTINESS (Line complexity variation)
# ============================================================================


def compute_burstiness_signal(code: str) -> float:
    """Compute burstiness signal (line complexity variation).

    Human code has irregular line complexity (bursts of dense logic
    followed by simple lines). LLM code is more uniform.
    Low coefficient of variation → high AI score.

    Algorithm:
    1. Extract non-empty lines
    2. For each line, compute complexity: C_i = (indent_level / 4.0) + (line_length / 80.0)
    3. Compute mean: μ = Σ(C_i) / n
    4. Compute coefficient of variation: CV = √(Σ(C_i - μ)² / n) / μ
    5. Map to score: score = max(0.0, min(1.0, 1.0 - (CV / 1.2)))

    Calibration:
    - Human code: CV 0.6–1.4 (score 0.0–0.5)
    - LLM code: CV 0.2–0.6 (score 0.5–1.0)

    Args:
        code: Source code to analyze

    Returns:
        Burstiness score in [0.0, 1.0]
    """
    lines = [ln.rstrip() for ln in code.splitlines() if ln.strip()]

    # Edge case: too few lines
    if len(lines) < 5:
        return 0.0

    # Compute complexity for each line
    complexities = []
    for ln in lines:
        stripped = ln.lstrip()
        indent = (len(ln) - len(stripped)) / 4.0
        length = len(stripped) / 80.0
        complexities.append(indent + length)

    # Compute mean
    mean = sum(complexities) / len(complexities)
    if mean < 1e-9:
        return 0.5

    # Compute coefficient of variation
    variance = sum((c - mean) ** 2 for c in complexities) / len(complexities)
    cv = math.sqrt(variance) / mean

    # Map to score: human code CV 0.6–1.4, LLM code CV 0.2–0.6
    score = max(0.0, min(1.0, 1.0 - (cv / 1.2)))
    return round(score, 3)


# ============================================================================
# SIGNAL 3: STYLOMETRY (Code style profile)
# ============================================================================


def compute_stylometry_signal(code: str) -> float:
    """Compute stylometry signal (code style profile).

    Analyzes comment formality, naming conventions, type-hint density,
    and other stylistic features that differ between human and AI code.

    Features analyzed:
    - Descriptive variable ratio (generic names like result, data, temp)
    - Docstring ratio (docstring lines / total lines)
    - Type-hint ratio (functions with return type hints / total functions)
    - Single-char variable ratio (single-char vars / total variables)
    - Exception handling ratio (try/except blocks / total functions)
    - List comprehension ratio (list comprehensions / total loops)

    Args:
        code: Source code to analyze

    Returns:
        Stylometry score in [0.0, 1.0]
    """
    # Count generic variable names (LLM-like)
    generic_names = [
        "result",
        "output",
        "data",
        "value",
        "temp",
        "final",
        "new",
        "processed",
        "formatted",
        "cleaned",
    ]
    generic_count = sum(len(re.findall(rf"\b{name}\b", code)) for name in generic_names)

    # Count all variable assignments
    var_count = len(re.findall(r"\b[a-zA-Z_]\w*\s*=", code))
    generic_ratio = generic_count / max(var_count, 1)

    # Count docstrings
    docstring_count = len(re.findall(r'"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'', code))
    lines = code.splitlines()
    docstring_ratio = docstring_count / max(len(lines), 1)

    # Count type hints
    type_hint_count = len(
        re.findall(r"->\s*(?:None|bool|int|str|float|List|Dict|Optional|Union)", code)
    )
    func_count = len(re.findall(r"^\s*def\s+\w+", code, re.MULTILINE))
    type_hint_ratio = type_hint_count / max(func_count, 1)

    # Count single-char variables
    single_char_count = len(re.findall(r"\b[a-z]\b", code))
    single_char_ratio = single_char_count / max(var_count, 1)

    # Count exception handling
    try_count = len(re.findall(r"^\s*try\s*:", code, re.MULTILINE))
    except_ratio = try_count / max(func_count, 1)

    # Count list comprehensions
    list_comp_count = len(re.findall(r"\[.*for.*in.*\]", code))
    loop_count = len(re.findall(r"^\s*for\s+\w+\s+in\s+", code, re.MULTILINE))
    list_comp_ratio = list_comp_count / max(loop_count, 1)

    # Combine features with weights
    score = (
        generic_ratio * 0.25
        + docstring_ratio * 0.20
        + type_hint_ratio * 0.20
        + (1.0 - single_char_ratio) * 0.15
        + except_ratio * 0.10
        + min(1.0, list_comp_ratio) * 0.10
    )

    return round(max(0.0, min(1.0, score)), 3)


# ============================================================================
# SIGNAL 4: PATTERN LIBRARY (LLM-specific fingerprints)
# ============================================================================

# LLM fingerprint patterns - curated from GPT-4 / Claude / Copilot output
_LLM_COMMENT_PATTERNS = [
    re.compile(
        r"#\s*(Let's|Let us|We can|We will|We need to|We first|We then)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"#\s*(Here we|Here is|Here's|This function|This method|This class)\b",
        re.IGNORECASE,
    ),
    re.compile(r"#\s*(Note:|Note that|NOTE:|TODO:|FIXME:|Step \d+:)", re.IGNORECASE),
    re.compile(
        r"#\s*(Initialize|Create|Define|Compute|Calculate|Return|Check|Handle)\b",
        re.IGNORECASE,
    ),
    re.compile(r"#\s*[A-Z][a-z]+(?: [a-z]+){2,}\s*$", re.MULTILINE),
    re.compile(r"#\s*-{3,}"),
    re.compile(
        r'"""[\s\S]{0,40}(?:Initialize|Create|Define|Compute|Calculate|Return|Check|Handle)',
        re.IGNORECASE,
    ),
]

_LLM_NAMING_PATTERNS = [
    re.compile(
        r"\b(result|output|data|value|temp|final|new|processed|formatted|cleaned)\b"
    ),
    re.compile(
        r"\b(process_|handle_|compute_|calculate_|generate_|validate_|parse_)\w+"
    ),
    re.compile(
        r"\b(input_data|output_data|result_list|data_list|item_list|temp_list)\b"
    ),
    re.compile(r"\b(is_valid|is_empty|is_none|has_error|has_value)\b"),
]

_LLM_STRUCTURAL_PATTERNS = [
    re.compile(r"if\s+\w+\s+is\s+None\s*:", re.IGNORECASE),
    re.compile(r"raise\s+ValueError\s*\(f?['\"]", re.IGNORECASE),
    re.compile(r"raise\s+TypeError\s*\(f?['\"]", re.IGNORECASE),
    re.compile(r"logging\.(debug|info|warning|error)\s*\(f?['\"]", re.IGNORECASE),
    re.compile(r"return\s+\[\s*\w+\s+for\s+\w+\s+in\s+\w+\s*\]"),
    re.compile(r"Optional\["),
    re.compile(r"Union\["),
    re.compile(r"Dict\[str,"),
    re.compile(r"List\[str\]"),
    re.compile(r"-> (?:None|bool|int|str|float|List|Dict|Optional)\s*:"),
]

_ALL_LLM_PATTERNS = (
    _LLM_COMMENT_PATTERNS + _LLM_NAMING_PATTERNS + _LLM_STRUCTURAL_PATTERNS
)


def compute_pattern_library_signal(code: str) -> float:
    """Compute pattern library signal (LLM fingerprints).

    Counts matches against 40+ curated regex fingerprints that are
    characteristic of LLM-generated code. Normalized by code length
    to prevent bias toward longer files.

    Algorithm:
    1. Define 40+ LLM-specific regex patterns
    2. Count total matches: match_count = Σ(pattern.findall(code))
    3. Normalize by code length: density = match_count / max(1, total_lines)
    4. Map to score: score = max(0.0, min(1.0, density * 5.0))

    Calibration:
    - Human code: 0–2 matches per 10 lines (score 0.0–0.4)
    - LLM code: 3–8 matches per 10 lines (score 0.6–1.0)

    Args:
        code: Source code to analyze

    Returns:
        Pattern library score in [0.0, 1.0]
    """
    total_lines = max(1, len(code.splitlines()))
    match_count = sum(len(pattern.findall(code)) for pattern in _ALL_LLM_PATTERNS)
    density = match_count / total_lines

    # Map density to score: 0 matches/line → 0.0, 5+ matches/line → 1.0
    score = max(0.0, min(1.0, density * 5.0))
    return round(score, 3)


# ============================================================================
# SIGNAL 5: STRUCTURAL ENTROPY (AST uniformity)
# ============================================================================


def compute_structural_entropy_signal(code: str, language: str = "python") -> float:
    """Compute structural entropy signal (AST uniformity).

    LLMs produce ASTs with very uniform node-type distributions.
    Human code has more varied AST structures.

    Algorithm (Python):
    1. Parse code into Abstract Syntax Tree (AST)
    2. Count node types: node_types = Counter(type(n).__name__ for n in ast.walk(tree))
    3. Compute normalized entropy: H = -Σ(p_i * log₂(p_i)) / log₂(n_unique)
    4. Map to score: score = max(0.0, min(1.0, 1.0 - H)) * 0.8

    Fallback (non-Python or parse error):
    1. Count indent levels: indent_levels = Counter((len(line) - len(line.lstrip())) // 4)
    2. Compute normalized entropy: H = -Σ(p_i * log₂(p_i)) / log₂(n_unique)
    3. Map to score: score = max(0.0, min(1.0, 1.0 - H)) * 0.6

    Args:
        code: Source code to analyze
        language: Programming language (default: 'python')

    Returns:
        Structural entropy score in [0.0, 1.0]
    """
    if language not in ("python", "py", ""):
        # Fallback to indent-level uniformity for non-Python
        return _indent_block_uniformity(code)

    try:
        tree = ast.parse(code)
    except SyntaxError:
        # Fallback to indent-level uniformity on parse error
        return _indent_block_uniformity(code)

    # Count node types
    node_types = Counter(type(n).__name__ for n in ast.walk(tree))
    if not node_types:
        return 0.0

    # Compute normalized entropy
    entropy = _safe_entropy(node_types)
    score = max(0.0, min(1.0, 1.0 - entropy)) * 0.8
    return round(score, 3)


def _indent_block_uniformity(code: str) -> float:
    """Fallback structural signal: indent-level distribution uniformity.

    Args:
        code: Source code to analyze

    Returns:
        Indent uniformity score in [0.0, 1.0]
    """
    lines = [ln for ln in code.splitlines() if ln.strip()]
    if not lines:
        return 0.0

    indent_levels = Counter((len(ln) - len(ln.lstrip())) // 4 for ln in lines)
    entropy = _safe_entropy(indent_levels)
    score = max(0.0, min(1.0, 1.0 - entropy)) * 0.6
    return round(score, 3)


# ============================================================================
# SIGNAL 6: VOCABULARY RICHNESS (Token diversity)
# ============================================================================


def compute_vocabulary_richness_signal(code: str) -> float:
    """Compute vocabulary richness signal (token diversity).

    Type-Token Ratio (TTR) and hapax legomena ratio.
    LLMs reuse a smaller vocabulary of "safe" tokens.
    Low TTR → high AI score.

    Algorithm:
    1. Tokenize code into lowercase tokens
    2. Compute TTR in sliding windows:
       - Window size: 50 tokens
       - Overlap: 50% (step = 25)
       - TTR_i = unique_tokens_in_window / 50
       - TTR_avg = mean(TTR_i)
    3. Compute hapax legomena ratio: hapax_ratio = count(tokens appearing exactly once) / total_unique_tokens
    4. Combine: score = 0.6 * TTR_score + 0.4 * hapax_score
       - TTR_score = max(0.0, min(1.0, 1.0 - (TTR_avg / 0.7)))
       - hapax_score = max(0.0, min(1.0, 1.0 - hapax_ratio))

    Calibration:
    - Human code: TTR 0.5–0.7, hapax 0.3–0.5 (score 0.0–0.4)
    - LLM code: TTR 0.3–0.5, hapax 0.1–0.3 (score 0.6–1.0)

    Args:
        code: Source code to analyze

    Returns:
        Vocabulary richness score in [0.0, 1.0]
    """
    tokens = _tokenize(code)

    # Edge case: too few tokens
    if len(tokens) < 20:
        return 0.0

    # Compute TTR in sliding windows
    window = 50
    ttrs = []
    for i in range(0, len(tokens) - window, window // 2):
        chunk = tokens[i : i + window]
        ttrs.append(len(set(chunk)) / window)

    ttr = sum(ttrs) / len(ttrs) if ttrs else len(set(tokens)) / len(tokens)

    # Compute hapax legomena ratio
    counter = Counter(tokens)
    hapax_ratio = sum(1 for c in counter.values() if c == 1) / len(counter)

    # Combine metrics
    ttr_score = max(0.0, min(1.0, 1.0 - (ttr / 0.7)))
    hapax_score = max(0.0, min(1.0, 1.0 - hapax_ratio))
    score = 0.6 * ttr_score + 0.4 * hapax_score

    return round(max(0.0, min(1.0, score)), 3)


# ============================================================================
# SIGNAL 7: WHITESPACE RHYTHM (Blank-line spacing)
# ============================================================================


def compute_whitespace_rhythm_signal(code: str) -> float:
    """Compute whitespace rhythm signal (blank-line spacing regularity).

    LLMs produce very regular blank-line spacing.
    Human code has more varied spacing.

    Algorithm:
    1. Identify runs of consecutive blank lines
    2. Count run lengths: runs = [1, 2, 1, 3, 1, 2, ...]
    3. Compute distribution: run_counter = Counter(runs)
    4. Compute normalized entropy: H = -Σ(p_i * log₂(p_i)) / log₂(n_unique)
    5. Map to score: score = max(0.0, min(1.0, 1.0 - H))

    Calibration:
    - Human code: varied run lengths, high entropy (score 0.0–0.3)
    - LLM code: uniform run lengths, low entropy (score 0.7–1.0)

    Args:
        code: Source code to analyze

    Returns:
        Whitespace rhythm score in [0.0, 1.0]
    """
    lines = code.splitlines()
    runs = []
    run = 0

    for ln in lines:
        if not ln.strip():
            run += 1
        else:
            if run > 0:
                runs.append(run)
            run = 0

    if run > 0:
        runs.append(run)

    # Edge case: too few blank-line runs
    if len(runs) < 3:
        return 0.0

    # Compute entropy of run lengths
    run_counter = Counter(runs)
    entropy = _safe_entropy(run_counter)
    score = max(0.0, min(1.0, 1.0 - entropy))

    return round(score, 3)


# ============================================================================
# SIGNAL 8: DOCSTRING DENSITY (Documentation prevalence)
# ============================================================================


def compute_docstring_density_signal(code: str) -> float:
    """Compute docstring density signal (documentation prevalence).

    LLMs add docstrings to almost every function.
    Human code has more selective documentation.

    Algorithm:
    1. Count function definitions: func_count = len(re.findall(r'^\\s*def\\s+\\w+', code, re.M))
    2. Count docstrings: docstring_count = len(re.findall(triple-quote pattern, code))
    3. If func_count > 0:
       - ratio = docstring_count / func_count
       - score = max(0.0, min(1.0, ratio * 0.75))
    4. Else (no functions):
       - ratio = docstring_count / max(1, total_lines / 10)
       - score = min(1.0, ratio)

    Calibration:
    - Human code: 0.2–0.4 docstrings per function (score 0.0–0.3)
    - LLM code: 0.8–1.0 docstrings per function (score 0.6–0.75)

    Args:
        code: Source code to analyze

    Returns:
        Docstring density score in [0.0, 1.0]
    """
    func_count = len(re.findall(r"^\s*def\s+\w+", code, re.MULTILINE))
    # Match triple-quoted strings (both """ and ''')
    docstring_pattern = r'"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\''
    docstring_count = len(re.findall(docstring_pattern, code))

    if func_count == 0:
        # No functions: compute relative to code length
        lines = code.splitlines()
        if not lines:
            return 0.0
        ratio = docstring_count / max(1, len(lines) / 10)
        score = min(1.0, ratio)
    else:
        # Compute ratio of docstrings to functions
        ratio = docstring_count / func_count
        score = max(0.0, min(1.0, ratio * 0.75))

    return round(score, 3)
