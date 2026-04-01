"""
Code Obfuscation Generator.

Generates obfuscated versions of source code at various levels:
- Level 0: Original (no obfuscation)
- Level 1: Whitespace/formatting changes
- Level 2: Variable/function name renaming
- Level 3: Statement reordering (where semantically safe)
- Level 4: Mixed (all of the above)

Used to benchmark detection system robustness against obfuscation.
"""
from typing import Dict, List, Any, Optional, Tuple
import re
import ast
import random
import string
from dataclasses import dataclass, field


@dataclass
class ObfuscationResult:
    """Result of obfuscation."""
    original: str
    obfuscated: str
    level: int
    level_name: str
    transformations: List[str] = field(default_factory=list)
    preserved_names: Dict[str, str] = field(default_factory=dict)  # old -> new


LEVEL_NAMES = {
    0: "Original",
    1: "Whitespace/Formatting",
    2: "Variable Renaming",
    3: "Statement Reordering",
    4: "Mixed (All Transformations)",
}


class ObfuscationGenerator:
    """
    Generates obfuscated versions of source code.

    Usage:
        gen = ObfuscationGenerator(seed=42)
        for level in range(5):
            result = gen.obfuscate(source_code, level)
            print(f"Level {level} ({result.level_name}):")
            print(result.obfuscated)
    """

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        self._name_counter = 0

    def _generate_name(self, prefix: str = "v") -> str:
        """Generate a unique obfuscated variable name."""
        self._name_counter += 1
        suffix = ''.join(self.rng.choices(string.ascii_lowercase, k=3))
        return f"{prefix}_{suffix}_{self._name_counter}"

    def obfuscate(self, source_code: str, level: int = 0,
                  language: str = "python") -> ObfuscationResult:
        """
        Obfuscate source code at the given level.

        Args:
            source_code: Original source code
            level: Obfuscation level (0-4)
            language: Target language (python, java)

        Returns:
            ObfuscationResult with obfuscated code
        """
        if level == 0:
            return ObfuscationResult(
                original=source_code,
                obfuscated=source_code,
                level=0,
                level_name=LEVEL_NAMES[0],
            )

        if language == "python":
            return self._obfuscate_python(source_code, level)
        elif language == "java":
            return self._obfuscate_java(source_code, level)
        else:
            return self._obfuscate_generic(source_code, level)

    def _obfuscate_python(self, source_code: str, level: int) -> ObfuscationResult:
        """Obfuscate Python code."""
        transformations = []
        preserved_names = {}
        result = source_code

        if level >= 1:
            result, t = self._obfuscate_whitespace_python(result)
            transformations.extend(t)

        if level == 2 or level == 4:
            result, t, p = self._rename_python_variables(result)
            transformations.extend(t)
            preserved_names.update(p)

        if level == 3:
            result, t = self._reorder_python_statements(result)
            transformations.extend(t)

        if level == 4:
            # Already has rename from above, add reordering
            result, t = self._reorder_python_statements(result)
            transformations.extend(t)

        return ObfuscationResult(
            original=source_code,
            obfuscated=result,
            level=level,
            level_name=LEVEL_NAMES[level],
            transformations=transformations,
            preserved_names=preserved_names,
        )

    def _obfuscate_whitespace_python(self, code: str) -> Tuple[str, List[str]]:
        """Apply whitespace and formatting changes to Python code."""
        transformations = []
        lines = code.split('\n')
        result_lines = []

        for line in lines:
            # Add/remove spaces (but preserve indentation)
            stripped = line.lstrip()
            indent = line[:len(line) - len(stripped)]

            # Randomly add spaces around operators
            if self.rng.random() < 0.3:
                stripped = re.sub(r'(\w)\s*=\s*(\w)', r'\1 = \2', stripped)
                stripped = re.sub(r'(\w)\s*\+\s*(\w)', r'\1 + \2', stripped)

            # Add blank comments
            if self.rng.random() < 0.2:
                result_lines.append("# ")
                transformations.append("Added blank comment")

            result_lines.append(indent + stripped)

        # Add extra newlines at random positions
        if self.rng.random() < 0.5:
            pos = self.rng.randint(0, len(result_lines))
            result_lines.insert(pos, "")
            transformations.append("Added extra newline")

        return '\n'.join(result_lines), transformations

    def _rename_python_variables(self, code: str) -> Tuple[str, List[str], Dict[str, str]]:
        """Rename variables in Python code using AST."""
        transformations = []
        name_map = {}

        try:
            tree = ast.parse(code)
        except SyntaxError:
            return code, ["AST parse failed - skipping rename"], {}

        # First pass: collect local variable names (skip builtins, keywords, class/func defs)
        builtin_names = {'self', 'cls', 'True', 'False', 'None', '__name__', '__main__',
                         'print', 'len', 'range', 'int', 'str', 'list', 'dict', 'set'}

        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                if node.id not in builtin_names and node.id not in name_map:
                    new_name = self._generate_name("var")
                    name_map[node.id] = new_name
            elif isinstance(node, ast.FunctionDef):
                # Rename function-local variables
                pass  # Handle args separately

        if not name_map:
            return code, ["No variables to rename"], {}

        # Second pass: rename in code (simple regex-based for safety)
        result = code
        for old_name, new_name in sorted(name_map.items(), key=lambda x: -len(x[0])):
            # Use word boundaries to avoid partial matches
            pattern = r'\b' + re.escape(old_name) + r'\b'
            result = re.sub(pattern, new_name, result)
            transformations.append(f"Renamed '{old_name}' -> '{new_name}'")

        return result, transformations, name_map

    def _reorder_python_statements(self, code: str) -> Tuple[str, List[str]]:
        """
        Reorder independent statements where possible.
        This is a simplified version - full version would use data flow analysis.
        """
        transformations = []
        lines = code.split('\n')

        # Find blocks of simple assignments and shuffle them
        result_lines = []
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            # Check if this is a simple assignment
            if re.match(r'^\w+\s*=.*$', stripped) and not stripped.startswith('def '):
                block_start = i
                block = [line]
                i += 1
                while i < len(lines):
                    next_line = lines[i]
                    if re.match(r'^\w+\s*=.*$', next_line.strip()) and not next_line.strip().startswith('def '):
                        block.append(next_line)
                        i += 1
                    else:
                        break

                # Shuffle the block if it has multiple lines
                if len(block) > 1 and self.rng.random() < 0.7:
                    shuffled = block.copy()
                    self.rng.shuffle(shuffled)
                    if shuffled != block:
                        transformations.append(f"Reordered {len(block)} assignments")
                    result_lines.extend(shuffled)
                else:
                    result_lines.extend(block)
            else:
                result_lines.append(line)
                i += 1

        return '\n'.join(result_lines), transformations

    def _obfuscate_java(self, source_code: str, level: int) -> ObfuscationResult:
        """Obfuscate Java code."""
        transformations = []
        preserved_names = {}
        result = source_code

        if level >= 1:
            result, t = self._obfuscate_whitespace_java(result)
            transformations.extend(t)

        if level == 2 or level == 4:
            result, t, p = self._rename_java_identifiers(result)
            transformations.extend(t)
            preserved_names.update(p)

        if level == 3:
            result, t = self._reorder_java_methods(result)
            transformations.extend(t)

        if level == 4:
            result, t = self._reorder_java_methods(result)
            transformations.extend(t)

        return ObfuscationResult(
            original=source_code,
            obfuscated=result,
            level=level,
            level_name=LEVEL_NAMES[level],
            transformations=transformations,
            preserved_names=preserved_names,
        )

    def _obfuscate_whitespace_java(self, code: str) -> Tuple[str, List[str]]:
        """Apply whitespace changes to Java code."""
        transformations = []
        # Normalize line endings
        code = code.replace('\r\n', '\n')
        # Add/remove braces style
        transformations.append("Normalized whitespace")
        return code, transformations

    def _rename_java_identifiers(self, code: str) -> Tuple[str, List[str], Dict[str, str]]:
        """Rename local variables in Java code."""
        transformations = []
        name_map = {}

        # Java pattern: type variableName = ...
        pattern = r'\b(?:int|long|float|double|String|boolean|char|byte|short)\s+(\w+)\b'
        
        java_keywords = {'int', 'long', 'float', 'double', 'String', 'boolean', 
                        'public', 'private', 'protected', 'static', 'final', 'void',
                        'class', 'interface', 'extends', 'implements', 'return', 'new'}

        for match in re.finditer(pattern, code):
            var_name = match.group(1)
            if var_name not in java_keywords and var_name not in name_map:
                new_name = self._generate_name("v")
                name_map[var_name] = new_name

        # Rename (reverse sorted to handle longer names first)
        result = code
        for old_name, new_name in sorted(name_map.items(), key=lambda x: -len(x[0])):
            pattern = r'\b' + re.escape(old_name) + r'\b'
            result = re.sub(pattern, new_name, result)
            transformations.append(f"Renamed '{old_name}' -> '{new_name}'")

        return result, transformations, name_map

    def _reorder_java_methods(self, code: str) -> Tuple[str, List[str]]:
        """Reorder method declarations in Java class."""
        transformations = []
        
        # Find method boundaries
        method_pattern = r'(public|private|protected)\s+.*?\}\s*\n'
        methods = re.findall(method_pattern, code, re.DOTALL)
        
        if len(methods) > 1 and self.rng.random() < 0.5:
            shuffled = methods.copy()
            self.rng.shuffle(shuffled)
            if shuffled != methods:
                # Replace methods in order
                result = code
                for i, m in enumerate(methods):
                    result = result.replace(m, f"__PLACEHOLDER_{i}__")
                for i, m in enumerate(shuffled):
                    result = result.replace(f"__PLACEHOLDER_{i}__", m)
                transformations.append(f"Reordered {len(methods)} methods")
                return result, transformations

        return code, transformations

    def _obfuscate_generic(self, source_code: str, level: int) -> ObfuscationResult:
        """Generic obfuscation for unknown languages."""
        result = source_code
        transformations = []

        if level >= 1:
            # Basic whitespace normalization
            result = '\n'.join(line.rstrip() for line in result.split('\n'))
            transformations.append("Normalized whitespace")

        if level >= 2:
            # Comment out random lines
            lines = result.split('\n')
            for i in range(len(lines)):
                if self.rng.random() < 0.1:
                    lines[i] = "// " + lines[i]
                    transformations.append(f"Commented line {i+1}")
            result = '\n'.join(lines)

        return ObfuscationResult(
            original=source_code,
            obfuscated=result,
            level=level,
            level_name=LEVEL_NAMES[level],
            transformations=transformations,
        )

    def generate_dataset(self, original_code: str, language: str = "python",
                         samples_per_level: int = 5) -> List[ObfuscationResult]:
        """
        Generate obfuscated samples at all levels.

        Args:
            original_code: Original source code
            language: Programming language
            samples_per_level: Number of samples per level

        Returns:
            List of ObfuscationResult for each sample
        """
        results = []
        for level in range(5):
            for _ in range(samples_per_level):
                result = self.obfuscate(original_code, level, language)
                results.append(result)
                self._name_counter = 0  # Reset for next sample
        return results