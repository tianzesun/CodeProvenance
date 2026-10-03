"""
Architecture Layer Metadata Registry

This module defines the canonical layer ordering and import rules.
All architectural enforcement is based on this registry.

The single source of truth is ``_ALLOWED`` below: for each layer, the other layers it may import. A layer may always
import itself, and everything not listed is denied. ``RULES`` (with its ``deny`` lists) is derived from it, so the two
can no longer drift apart, and ``validate_rules()`` checks the table for mistakes when the module is imported.

Usage:
    from src.backend.architecture import ARCH_LAYERS, RULES, validate_import

    # Check the whole code base from the command line (exit status 1 on violations):
    python -m src.backend.architecture --check
"""

import argparse
import ast
import sys
from collections import Counter
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path

#: Dotted prefix of the backend package. Module names are matched after this prefix is removed.
PACKAGE_ROOT = "src.backend"


class LayerOrder(IntEnum):
    """Display order of the layers (lower number = listed first).

    This is for printing only. It is NOT the dependency direction: the rules in ``_ALLOWED`` are. (It used to be
    used as one, which flagged imports the rules allow, such as engines -> core, and missed ones they deny.)
    ``EVALUATION`` has the same value as ``ENGINES``, so Python makes it an alias of ``ENGINES``.
    """

    API = 1
    APPLICATION = 2
    DOMAIN = 3
    CORE = 4
    ENGINES = 5
    EVALUATION = 5
    INFRASTRUCTURE = 6


# Layer hierarchy mapping
ARCH_LAYERS: dict[str, int] = {
    "api": LayerOrder.API,
    "application": LayerOrder.APPLICATION,
    "domain": LayerOrder.DOMAIN,
    "core": LayerOrder.CORE,
    "engines": LayerOrder.ENGINES,
    "evaluation": LayerOrder.EVALUATION,
    "infrastructure": LayerOrder.INFRASTRUCTURE,
}

# What each layer MAY import (besides itself). Everything else is DENIED.
_ALLOWED: dict[str, tuple[str, ...]] = {
    "api": ("application",),
    "application": ("domain", "core"),
    "domain": (),  # Domain is PURE - imports no other layer
    "core": ("domain",),
    "engines": ("core", "domain"),
    "evaluation": ("core", "domain", "engines"),  # READ-ONLY access to engines
    "infrastructure": ("core", "domain"),  # May use core/domain if necessary
}


def _build_rules() -> dict[str, dict[str, list[str]]]:
    rules: dict[str, dict[str, list[str]]] = {}
    for layer in ARCH_LAYERS:
        allow = list(_ALLOWED.get(layer, ()))
        deny = [other for other in ARCH_LAYERS if other != layer and other not in allow]
        rules[layer] = {"allow": allow, "deny": deny}
    return rules


# Import rules, in the original shape: RULES[layer]["allow"] / ["deny"].
# `deny` now lists every other layer that is not allowed. The hand-written lists left some out (engines and evaluation
# could import infrastructure, application could import api), so "everything else is DENIED" was not true.
RULES: dict[str, dict[str, list[str]]] = _build_rules()


def validate_rules(allowed: dict[str, tuple[str, ...]] | None = None) -> list[str]:
    """Return the problems in a rules table (empty when it is sound): missing or unknown layers, self- or duplicate
    entries, and dependency cycles."""
    table = _ALLOWED if allowed is None else allowed
    problems: list[str] = []
    for layer in ARCH_LAYERS:
        if layer not in table:
            problems.append(f"{layer}: no rules defined")
    for layer, targets in table.items():
        if layer not in ARCH_LAYERS:
            problems.append(f"{layer}: not a known layer")
        if len(set(targets)) != len(targets):
            problems.append(f"{layer}: lists the same layer twice")
        for target in targets:
            if target not in ARCH_LAYERS:
                problems.append(f"{layer}: allows unknown layer {target!r}")
            elif target == layer:
                problems.append(f"{layer}: lists itself (always allowed, so remove it)")

    # A cycle (a -> b -> a) would make the layering meaningless.
    state: dict[str, int] = {}  # 1 = on the current path, 2 = done

    def visit(layer: str, path: list[str]) -> None:
        if state.get(layer) == 2:
            return
        if state.get(layer) == 1:
            problems.append("dependency cycle: " + " -> ".join([*path[path.index(layer):], layer]))
            return
        state[layer] = 1
        for target in table.get(layer, ()):
            if target in ARCH_LAYERS:
                visit(target, [*path, layer])
        state[layer] = 2

    for layer in table:
        visit(layer, [])
    return problems


_problems = validate_rules()
if _problems:  # pragma: no cover - guards against future edits
    raise RuntimeError("Invalid architecture rules: " + "; ".join(_problems))


@dataclass(frozen=True)
class ImportViolation:
    """Import architecture violation."""

    source_layer: str
    target_layer: str
    import_name: str
    file_path: str
    line_number: int
    message: str


def get_layer_order(layer_name: str) -> int:
    """Get the display-order number for a layer (999 for an unknown layer)."""
    return ARCH_LAYERS.get(layer_name, 999)


def layer_of(module_name: str) -> str | None:
    """The layer a dotted module name belongs to, or None.

    ``src.backend.core.ir`` and ``core.ir`` are both in ``core``. Names are compared by whole dotted segment, so
    ``corelib`` and ``domainlib`` are not mistaken for ``core`` and ``domain`` (matching used ``str.startswith``).
    A module outside every layer (``config``, ``models``, third-party packages) returns None.
    """
    parts = [p for p in module_name.split(".") if p]
    root = PACKAGE_ROOT.split(".")
    if parts[: len(root)] == root:
        parts = parts[len(root):]
    return parts[0] if parts and parts[0] in ARCH_LAYERS else None


def is_valid_import(source_layer: str, target_layer: str) -> bool:
    """Check if import from source to target is valid (a layer may import itself and what its rules allow)."""
    if source_layer not in ARCH_LAYERS or target_layer not in ARCH_LAYERS:
        return True  # Unknown layer: not covered by the rules
    return source_layer == target_layer or target_layer in RULES[source_layer]["allow"]


def validate_import(
    source_layer: str, import_name: str, file_path: str = "", line_number: int = 0
) -> ImportViolation | None:
    """Validate an import against architecture rules.

    ``import_name`` is the dotted module being imported, with or without the ``src.backend`` prefix.

    Returns:
        ImportViolation if invalid, None if valid
    """
    if source_layer not in RULES:
        return None  # Not a layer: nothing to enforce

    target_layer = layer_of(import_name)
    if target_layer is None or target_layer == source_layer:
        return None  # Not one of our layers, or the layer's own code
    allowed = RULES[source_layer]["allow"]
    if target_layer in allowed:
        return None

    return ImportViolation(
        source_layer=source_layer,
        target_layer=target_layer,
        import_name=import_name,
        file_path=file_path,
        line_number=line_number,
        message=(
            f"{source_layer} cannot import {target_layer} "
            f"(it may import: {', '.join(allowed) if allowed else 'no other layer'})"
        ),
    )


def get_allowed_imports(layer_name: str) -> list[str]:
    """Get list of allowed imports for a layer (a copy)."""
    if layer_name not in RULES:
        return []

    return list(RULES[layer_name]["allow"])


def get_denied_imports(layer_name: str) -> list[str]:
    """Get list of denied imports for a layer (a copy)."""
    if layer_name not in RULES:
        return []

    return list(RULES[layer_name]["deny"])


_DESCRIPTIONS = {
    "api": "REST API endpoints (presentation layer)",
    "application": "Use cases and orchestration",
    "domain": "Business logic (pure, no external imports)",
    "core": "IR, primitives, and invariants",
    "engines": "Runtime execution logic",
    "evaluation": "Metrics computation (no execution)",
    "infrastructure": "External systems (DB, IO, etc.)",
}


def get_layer_description(layer_name: str) -> str:
    """Get description of a layer's responsibilities."""
    return _DESCRIPTIONS.get(layer_name, "Unknown layer")


# ── Checking real code ───────────────────────────────────────────────────────


def module_name_for(path: Path, root: Path) -> str:
    """Dotted module name of ``path`` relative to ``root`` (the directory that contains ``src``)."""
    parts = list(path.resolve().relative_to(root.resolve()).with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _resolve_relative(current_module: str, is_package: bool, level: int, module: str | None) -> str:
    package = current_module.split(".") if is_package else current_module.split(".")[:-1]
    keep = len(package) - (level - 1)
    if keep < 0:
        return ""
    return ".".join(p for p in (*package[:keep], module or "") if p)


def iter_imports(tree: ast.AST, current_module: str = "", is_package: bool = False) -> Iterator[tuple[str, int]]:
    """Yield ``(dotted_module, line_number)`` for every import in a parsed file, relative imports resolved."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name, node.lineno
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                base = _resolve_relative(current_module, is_package, node.level, node.module)
            if base:
                yield base, node.lineno
                # `from src.backend import core` imports the submodule `core`.
                for alias in node.names:
                    if alias.name != "*":
                        yield f"{base}.{alias.name}", node.lineno


def check_source(source: str, module: str, file_path: str = "", is_package: bool = False) -> list[ImportViolation]:
    """Violations in one file's source. Raises ``SyntaxError`` if it does not parse."""
    layer = layer_of(module)
    if layer is None:
        return []
    found: dict[tuple[int, str], ImportViolation] = {}
    for name, line in iter_imports(ast.parse(source), module, is_package):
        violation = validate_import(layer, name, file_path, line)
        if violation is not None:
            # One line can name the module and its submodule; report it once.
            found.setdefault((line, violation.target_layer), violation)
    return sorted(found.values(), key=lambda v: v.line_number)


@dataclass
class ScanResult:
    violations: list[ImportViolation] = field(default_factory=list)
    #: Top-level packages (and file counts) that belong to no layer, so no rule applies to them.
    unmapped: Counter = field(default_factory=Counter)
    unparsable: list[str] = field(default_factory=list)


def scan_tree(root: Path, backend: str = "src/backend") -> ScanResult:
    result = ScanResult()
    backend_dir = root / backend
    for path in sorted(backend_dir.rglob("*.py")):
        module = module_name_for(path, root)
        if layer_of(module) is None:
            tail = module.split(".")[len(PACKAGE_ROOT.split(".")):]
            if tail:  # (the backend package's own __init__.py has no tail and is not worth listing)
                result.unmapped[tail[0]] += 1
            continue
        try:
            result.violations += check_source(
                path.read_text(encoding="utf-8"), module, str(path.relative_to(root)), path.name == "__init__.py"
            )
        except (SyntaxError, UnicodeDecodeError):
            result.unparsable.append(str(path.relative_to(root)))
    return result


def print_architecture_summary():
    """Print summary of architecture rules."""
    print("Architecture Layer Summary:")
    print("=" * 60)
    print()

    for layer_name in sorted(ARCH_LAYERS.keys(), key=lambda x: (ARCH_LAYERS[x], x)):
        order = ARCH_LAYERS[layer_name]
        description = get_layer_description(layer_name)
        allowed = get_allowed_imports(layer_name)
        denied = get_denied_imports(layer_name)

        print(f"Layer {order}: {layer_name}")
        print(f"  Description: {description}")
        print(f"  May import: {', '.join(allowed) if allowed else 'nothing'}")
        print(f"  Must NOT import: {', '.join(denied)}")
        print()

    # Drawn from the rules, so it cannot disagree with them. (The hand-drawn version showed
    # api -> application -> domain -> core, but the rules have core importing domain, and nothing may import
    # infrastructure: it is wired in from outside the layers.)
    print("Dependency direction (A -> B means A may import B):")
    for layer_name in ARCH_LAYERS:
        allowed = get_allowed_imports(layer_name)
        print(f"  {layer_name} -> {', '.join(allowed) if allowed else '(nothing)'}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Show or check the architecture layer rules.")
    parser.add_argument("--check", action="store_true", help="scan the backend sources and report violations")
    parser.add_argument("--root", type=Path, help="repository root (the directory containing src/)")
    parser.add_argument("--backend", default="src/backend", help="backend directory, relative to --root")
    args = parser.parse_args(argv)

    if not args.check:
        print_architecture_summary()
        return 0

    root = args.root or Path(__file__).resolve().parents[2]
    result = scan_tree(root, args.backend)
    for v in result.violations:
        print(f"{v.file_path}:{v.line_number}: {v.message}  [import {v.import_name}]")
    for path in result.unparsable:
        print(f"{path}: could not be parsed")
    if result.unmapped:
        listing = ", ".join(f"{name} ({count} file{'s' if count != 1 else ''})" for name, count in sorted(result.unmapped.items()))
        print(f"\nIn no layer, so no rule applies to them: {listing}")
    print(f"\n{len(result.violations)} violation(s)")
    return 1 if result.violations or result.unparsable else 0


if __name__ == "__main__":
    sys.exit(main())
