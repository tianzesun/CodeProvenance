import ast
import math
import re
from collections import Counter
from statistics import fmean
from typing import Any

#: Line-comment prefix by language family (everything not listed uses ``//``).
_HASH_COMMENT_LANGUAGES = frozenset({"python", "py", "ruby", "rb", "bash", "sh", "perl", "r", "powershell"})

_DOCSTRING_REGEX = re.compile(r'""".*?"""|\'\'\'.*?\'\'\'', re.DOTALL)

#: Features that are fractions in [0, 1]. They are compared by absolute
#: difference: a relative difference turns 0.00 vs 0.02 into "completely
#: different", although both authors essentially never write that construct.
_BOUNDED_FEATURES = frozenset(
    {
        "snake_case_ratio",
        "camel_case_ratio",
        "comment_density",
        "tab_usage_ratio",
        "blank_line_ratio",
        "comprehension_density",
        "decorator_density",
        "lambda_density",
    }
)

_FUNC_NODES = (ast.FunctionDef, ast.AsyncFunctionDef)


def classify_identifier(name: str) -> str | None:
    """Return ``"snake"``, ``"camel"`` or ``None`` for names that show no style.

    Constants (``MAX_SIZE``), one-letter names, dunder names (``__init__`` is the
    language's choice, not the author's), single lowercase words and ClassNames
    say nothing about the author's habit, so they are neutral. The old rule
    counted any name containing ``_`` as snake_case (``_x``, ``__init__``) and
    any name with a capital as camelCase (``MAX``, ``PI``, ``Node``).
    """
    if len(name) > 4 and name.startswith("__") and name.endswith("__"):
        return None
    core = name.strip("_")
    if len(core) < 2 or core.isupper():
        return None
    if "_" in core and core.islower():
        return "snake"
    if "_" not in core and core[0].islower() and not core.islower():
        return "camel"
    return None


class StylometryExtractor:
    """
    Extracts code style features (stylometry) to distinguish between
    different authors. Features include:
    - Variable naming habits (snake_case vs camelCase)
    - Comment styles and density
    - Function length distributions
    - Use of specific language features (list comprehensions, decorators)
    - White space usage (tabs vs spaces, indentation width)

    Values are plain Python numbers (they used to be numpy scalars, which are not
    JSON-serialisable for integer types).
    """

    def extract(self, code: str, language: str = "python") -> dict[str, Any]:
        """Extract style features.

        Args:
            code: Source text.
            language: Language name; selects the comment syntax for the
                text-based features. AST features exist for Python only.
        """
        features: dict[str, Any] = {}

        try:
            tree = ast.parse(code)
            features.update(self._extract_ast_stylometry(tree))
        except (SyntaxError, ValueError, RecursionError, MemoryError):
            # Fallback for non-parseable code (other languages, syntax errors,
            # NUL bytes, pathological nesting): text features only.
            pass

        for key, value in self._extract_regex_stylometry(code, language).items():
            # An exact AST docstring count beats the regex estimate.
            features.setdefault(key, value)
        return features

    def _extract_ast_stylometry(self, tree: ast.AST) -> dict[str, Any]:
        names: list[str] = []
        func_lengths: list[int] = []
        statements = comprehensions = decorators = lambdas = docstrings = 0

        for node in ast.walk(tree):
            if isinstance(node, ast.stmt):
                statements += 1
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                names.append(node.id)
            elif isinstance(node, _FUNC_NODES):
                names.append(node.name)
                names.extend(a.arg for a in node.args.args)
                end = getattr(node, "end_lineno", None)
                # Lines spanned (the old ``end - start`` was 0 for a one-line
                # function) and None-safe for nodes without an end position.
                func_lengths.append((end - node.lineno + 1) if end is not None else 0)
                decorators += len(node.decorator_list)
            elif isinstance(node, ast.ClassDef):
                decorators += len(node.decorator_list)
            elif isinstance(node, (ast.ListComp, ast.DictComp, ast.SetComp, ast.GeneratorExp)):
                comprehensions += 1
            elif isinstance(node, ast.Lambda):
                lambdas += 1
            if isinstance(node, (ast.Module, ast.ClassDef, *_FUNC_NODES)):
                body = node.body
                if (
                    body
                    and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)
                ):
                    docstrings += 1

        total = max(1, statements)
        features: dict[str, Any] = {
            "avg_func_length": float(fmean(func_lengths)) if func_lengths else 0.0,
            "max_func_length": float(max(func_lengths)) if func_lengths else 0.0,
            # These were raw counts under a "_density" name, so the same style
            # looked different between a 20-line and a 200-line file.
            "comprehension_density": comprehensions / total,
            "decorator_density": decorators / total,
            "lambda_density": lambdas / total,
            "docstring_count": float(docstrings),
        }

        styles = Counter(s for s in map(classify_identifier, names) if s)
        styled = styles["snake"] + styles["camel"]
        if styled:
            features["snake_case_ratio"] = styles["snake"] / styled
            features["camel_case_ratio"] = styles["camel"] / styled
        # With no styled names the keys are left out. They used to be filled with
        # an invented 0.5/0.5, which then "matched" or "mismatched" real values.
        return features

    def _extract_regex_stylometry(self, code: str, language: str = "python") -> dict[str, Any]:
        lines = code.splitlines()
        if not lines:
            return {}

        prefix = "#" if language.strip().lower() in _HASH_COMMENT_LANGUAGES else "//"
        comment_lines = sum(1 for line in lines if line.lstrip().startswith(prefix))

        # Indentation: classify every indented line by its first character. The
        # old ``startswith("    ")`` count ignored 2-space indentation entirely
        # (so 2-space code looked like "no tabs, no spaces").
        tabs = spaces = 0
        increases: Counter[int] = Counter()
        previous_indent = 0
        for line in lines:
            if not line.strip():
                continue
            if line[0] == "\t":
                tabs += 1
            elif line[0] == " ":
                spaces += 1
            indent = len(line) - len(line.lstrip(" "))
            if indent > previous_indent and line[0] == " ":
                increases[indent - previous_indent] += 1
            previous_indent = indent

        blank = sum(1 for line in lines if not line.strip())
        docstrings = len(_DOCSTRING_REGEX.findall(code))
        indented = tabs + spaces
        return {
            "comment_density": comment_lines / len(lines),
            "tab_usage_ratio": tabs / indented if indented else 0.0,
            "indent_width": float(increases.most_common(1)[0][0]) if increases else 0.0,
            "docstring_count": float(docstrings),
            "avg_line_length": float(fmean(len(line) for line in lines)),
            "blank_line_ratio": blank / len(lines),
        }


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def compare_stylometry(feat_a: dict[str, Any], feat_b: dict[str, Any]) -> float:
    """Compares two stylometry feature sets and returns a similarity score in [0, 1].

    Only features present in both are compared; with none in common the answer is
    the neutral 0.5. Fractions are compared by absolute difference, unbounded
    features (lengths, counts) by relative difference.
    """
    scores: list[float] = []
    for key in sorted(feat_a.keys() & feat_b.keys()):
        val_a, val_b = feat_a[key], feat_b[key]
        if not (_is_number(val_a) and _is_number(val_b)):
            continue
        diff = abs(val_a - val_b)
        if key in _BOUNDED_FEATURES:
            scores.append(1.0 - min(1.0, diff))
        else:
            scores.append(1.0 - diff / max(abs(val_a), abs(val_b), 1e-9))

    if not scores:
        return 0.5
    return max(0.0, min(1.0, float(fmean(scores))))
