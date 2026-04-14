"""
Architecture Layer Metadata Registry

This module defines the canonical layer ordering and import rules.
All architectural enforcement is based on this registry.

Usage:
    from src.backend.architecture import ARCH_LAYERS, RULES, validate_import
"""

from typing import Dict, List, Set, Optional
from enum import IntEnum
from dataclasses import dataclass


class LayerOrder(IntEnum):
    """Layer hierarchy order (lower number = higher level)."""
    API = 1
    APPLICATION = 2
    DOMAIN = 3
    CORE = 4
    ENGINES = 5
    EVALUATION = 5
    INFRASTRUCTURE = 6


# Layer hierarchy mapping
ARCH_LAYERS: Dict[str, int] = {
    "api": LayerOrder.API,
    "application": LayerOrder.APPLICATION,
    "domain": LayerOrder.DOMAIN,
    "core": LayerOrder.CORE,
    "engines": LayerOrder.ENGINES,
    "evaluation": LayerOrder.EVALUATION,
    "infrastructure": LayerOrder.INFRASTRUCTURE,
}

# Import rules: what each layer MAY import
# Everything else is DENIED
RULES: Dict[str, Dict[str, List[str]]] = {
    "api": {
        "allow": ["application"],
        "deny": ["domain", "core", "engines", "evaluation", "infrastructure"],
    },
    "application": {
        "allow": ["domain", "core"],
        "deny": ["engines", "evaluation", "infrastructure"],
    },
    "domain": {
        "allow": [],  # Domain is PURE - imports NOTHING
        "deny": ["api", "application", "core", "engines", "evaluation", "infrastructure"],
    },
    "core": {
        "allow": ["domain"],
        "deny": ["api", "application", "engines", "evaluation", "infrastructure"],
    },
    "engines": {
        "allow": ["core", "domain"],
        "deny": ["api", "application", "evaluation"],
    },
    "evaluation": {
        "allow": ["core", "domain", "engines"],  # READ-ONLY access to engines
        "deny": ["api", "application"],
    },
    "infrastructure": {
        "allow": ["core", "domain"],  # May use core/domain if necessary
        "deny": ["api", "application", "evaluation"],
    },
}


@dataclass
class ImportViolation:
    """Import architecture violation."""
    source_layer: str
    target_layer: str
    import_name: str
    file_path: str
    line_number: int
    message: str


def get_layer_order(layer_name: str) -> int:
    """Get the order number for a layer."""
    return ARCH_LAYERS.get(layer_name, 999)


def is_valid_import(source_layer: str, target_layer: str) -> bool:
    """Check if import from source to target is valid."""
    if source_layer not in ARCH_LAYERS:
        return True  # Unknown layer, allow
    
    if target_layer not in ARCH_LAYERS:
        return True  # Unknown target, allow
    
    source_order = get_layer_order(source_layer)
    target_order = get_layer_order(target_layer)
    
    # Lower order = higher level (can import lower level)
    return source_order <= target_order


def validate_import(
    source_layer: str,
    import_name: str,
    file_path: str = "",
    line_number: int = 0
) -> Optional[ImportViolation]:
    """Validate an import against architecture rules.
    
    Returns:
        ImportViolation if invalid, None if valid
    """
    if source_layer not in RULES:
        return None
    
    rules = RULES[source_layer]
    denied = rules.get("deny", [])
    allowed = rules.get("allow", [])
    
    # Check if import is denied
    for denied_layer in denied:
        if import_name.startswith(denied_layer):
            # Check if it's explicitly allowed
            for allowed_layer in allowed:
                if import_name.startswith(allowed_layer):
                    return None  # Explicitly allowed
            
            # Not allowed, create violation
            return ImportViolation(
                source_layer=source_layer,
                target_layer=denied_layer,
                import_name=import_name,
                file_path=file_path,
                line_number=line_number,
                message=f"{source_layer} cannot import {denied_layer}",
            )
    
    # Check layer ordering
    target_layer = None
    for layer in ARCH_LAYERS.keys():
        if import_name.startswith(layer):
            target_layer = layer
            break
    
    if target_layer and not is_valid_import(source_layer, target_layer):
        return ImportViolation(
            source_layer=source_layer,
            target_layer=target_layer,
            import_name=import_name,
            file_path=file_path,
            line_number=line_number,
            message=f"Layer ordering violation: {source_layer} (order {get_layer_order(source_layer)}) cannot import {target_layer} (order {get_layer_order(target_layer)})",
        )
    
    return None


def get_allowed_imports(layer_name: str) -> List[str]:
    """Get list of allowed imports for a layer."""
    if layer_name not in RULES:
        return []
    
    return RULES[layer_name].get("allow", [])


def get_denied_imports(layer_name: str) -> List[str]:
    """Get list of denied imports for a layer."""
    if layer_name not in RULES:
        return []
    
    return RULES[layer_name].get("deny", [])


def get_layer_description(layer_name: str) -> str:
    """Get description of a layer's responsibilities."""
    descriptions = {
        "api": "REST API endpoints (presentation layer)",
        "application": "Use cases and orchestration",
        "domain": "Business logic (pure, no external imports)",
        "core": "IR, primitives, and invariants",
        "engines": "Runtime execution logic",
        "evaluation": "Metrics computation (no execution)",
        "infrastructure": "External systems (DB, IO, etc.)",
    }
    
    return descriptions.get(layer_name, "Unknown layer")


def print_architecture_summary():
    """Print summary of architecture rules."""
    print("Architecture Layer Summary:")
    print("=" * 60)
    print()
    
    for layer_name in sorted(ARCH_LAYERS.keys(), key=lambda x: ARCH_LAYERS[x]):
        order = ARCH_LAYERS[layer_name]
        description = get_layer_description(layer_name)
        allowed = get_allowed_imports(layer_name)
        denied = get_denied_imports(layer_name)
        
        print(f"Layer {order}: {layer_name}")
        print(f"  Description: {description}")
        print(f"  May import: {', '.join(allowed) if allowed else 'nothing'}")
        print(f"  Must NOT import: {', '.join(denied)}")
        print()
    
    print("Dependency Direction:")
    print("  api → application → domain → core")
    print("                      ↓")
    print("               engines / evaluation (read-only)")
    print("                      ↓")
    print("                infrastructure")


if __name__ == "__main__":
    print_architecture_summary()