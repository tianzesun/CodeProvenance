"""
AST-Based Code Similarity Parser.

Uses Abstract Syntax Tree (AST) analysis for robust similarity detection
that resists common obfuscation techniques:
- Variable renaming (AST normalizes identifiers)
- Whitespace changes (AST structure is unaffected)
- Comment additions (AST ignores comments)
- Statement reordering (can detect via control flow analysis)

Supports Python and Java (via tree-sitter for Java).
"""
from typing import Dict, List, Any, Optional, Tuple, Set
from pathlib import Path
import ast
import hashlib
from dataclasses import dataclass, field
from collections import defaultdict, Counter


@dataclass
class ASTNode:
    """Normalized AST node representation."""
    node_type: str
    children: List['ASTNode'] = field(default_factory=list)
    attributes: Dict[str, Any] = field(default_factory=dict)
    position: Optional[Tuple[int, int]] = None  # (line, col)

    def structure_hash(self, normalize_ids: bool = True) -> str:
        """
        Compute hash of AST structure.
        
        Args:
            normalize_ids: If True, normalize all identifiers to same token
        """
        parts = []
        for node in self.walk():
            token = node.node_type
            if node.attributes and not normalize_ids:
                for k, v in sorted(node.attributes.items()):
                    token += f"({k}:{v})"
            parts.append(token)
        return hashlib.md5('|'.join(parts).encode()).hexdigest()

    def walk(self) -> List['ASTNode']:
        """Walk all nodes in tree."""
        result = [self]
        for child in self.children:
            result.extend(child.walk())
        return result


@dataclass
class ASTSimilarityResult:
    """Result of AST-based similarity comparison."""
    score: float
    structural_similarity: float
    token_similarity: float
    common_patterns: List[str] = field(default_factory=list)
    differences: List[str] = field(default_factory=list)


class PythonASTParser:
    """Parses Python code into normalized AST representation."""

    def parse(self, source: str) -> Optional[ASTNode]:
        """Parse Python source code into ASTNode tree."""
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return None
        
        return self._convert_node(tree)

    def _convert_node(self, node: Any) -> ASTNode:
        """Convert Python AST node to our ASTNode."""
        if node is None:
            return ASTNode(node_type="None")

        node_type = type(node).__name__
        children = []
        attributes = {}

        # Handle position information
        position = None
        if hasattr(node, 'lineno'):
            col = getattr(node, 'col_offset', 0)
            position = (node.lineno, col)

        for field_name, value in ast.iter_fields(node):
            if isinstance(value, ast.AST):
                children.append(self._convert_node(value))
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, ast.AST):
                        children.append(self._convert_node(item))
            else:
                # For simple attributes, normalize identifiers
                if field_name in ('id', 'name', 'arg'):
                    attributes[field_name] = '__ID__'
                else:
                    attributes[field_name] = str(value) if value is not None else None

        return ASTNode(
            node_type=node_type,
            children=children,
            attributes=attributes,
            position=position,
        )

    def extract_structure_tokens(self, node: ASTNode) -> List[str]:
        """Extract structural tokens (node types) for similarity."""
        return [n.node_type for n in node.walk()]

    def normalize_tree(self, node: ASTNode) -> ASTNode:
        """Normalize AST by sorting children where order doesn't matter."""
        # For certain node types, children can be reordered
        if node.node_type == 'Module':
            # Sort top-level declarations by type and name
            node.children.sort(key=lambda c: (c.node_type, c.attributes.get('name', '')))

        # Normalize all children recursively
        for child in node.children:
            self.normalize_tree(child)

        return node


class JavaASTParser:
    """
    Parses Java code into normalized AST representation.
    
    Uses regex-based parsing (no tree-sitter dependency).
    For production, consider integrating tree-sitter-java.
    """

    def parse(self, source: str) -> Optional[ASTNode]:
        """Parse Java source code into ASTNode tree."""
        try:
            lines = source.split('\n')
            root = ASTNode(node_type="CompilationUnit")
            self._parse_class(lines, root)
            return root
        except Exception:
            return None

    def _parse_class(self, lines: List[str], parent: ASTNode) -> None:
        """Extract class and method structure."""
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # Class declaration
            class_match = self._match_class_decl(line)
            if class_match:
                class_node = ASTNode(
                    node_type="ClassDeclaration",
                    attributes={"name": class_match[0]}
                )
                parent.children.append(class_node)
                i = self._parse_block(lines, i + 1, class_node)
                continue

            # Method declaration
            method_match = self._match_method_decl(line)
            if method_match:
                method_node = ASTNode(
                    node_type="MethodDeclaration",
                    attributes={"name": method_match[0]}
                )
                parent.children.append(method_node)
                i = self._parse_block(lines, i + 1, method_node)
                continue

            # Simple statement - extract structure
            if line and not line.startswith('//') and not line.startswith('/*'):
                tokens = self._extract_java_tokens(line)
                stmt_node = ASTNode(
                    node_type="Statement",
                    attributes={"tokens": ' '.join(tokens)}
                )
                parent.children.append(stmt_node)
            
            i += 1

    def _match_class_decl(self, line: str) -> Optional[Tuple[str]]:
        """Match Java class declaration."""
        import re
        match = re.search(r'(?:public\s+)?(?:abstract\s+)?class\s+(\w+)', line)
        if match:
            return (match.group(1),)
        return None

    def _match_method_decl(self, line: str) -> Optional[Tuple[str]]:
        """Match Java method declaration."""
        import re
        match = re.search(r'(?:public|private|protected)?\s*\w*\s+(\w+)\s*\(', line)
        if match:
            return (match.group(1),)
        return None

    def _parse_block(self, lines: List[str], start: int, parent: ASTNode) -> int:
        """Parse a code block (between braces)."""
        brace_count = 0
        i = start
        started = False
        
        while i < len(lines):
            line = lines[i]
            for ch in line:
                if ch == '{':
                    brace_count += 1
                    started = True
                elif ch == '}':
                    brace_count -= 1
                    if started and brace_count == 0:
                        return i + 1
            
            # Parse content inside block
            if started and brace_count > 0:
                stripped = line.strip()
                if stripped and not stripped.startswith('//'):
                    # Method or statement
                    method_match = self._match_method_decl(stripped)
                    if method_match:
                        method_node = ASTNode(
                            node_type="MethodDeclaration",
                            attributes={"name": method_match[0]}
                        )
                        parent.children.append(method_node)
                    elif not stripped.startswith('/*') and '{' not in stripped and '}' not in stripped:
                        tokens = self._extract_java_tokens(stripped)
                        stmt_node = ASTNode(
                            node_type="Statement",
                            attributes={"tokens": ' '.join(tokens)}
                        )
                        parent.children.append(stmt_node)
            
            i += 1
        
        return i

    def _extract_java_tokens(self, line: str) -> List[str]:
        """Extract significant tokens from Java code line."""
        import re
        # Remove comments
        line = re.sub(r'//.*$', '', line)
        # Extract words/symbols
        tokens = re.findall(r'\b\w+\b|[{}();=<>+\-*/]', line)
        # Normalize identifiers
        java_keywords = {
            'public', 'private', 'protected', 'static', 'final', 'class',
            'interface', 'extends', 'implements', 'if', 'else', 'for',
            'while', 'do', 'switch', 'case', 'return', 'void', 'int',
            'long', 'float', 'double', 'String', 'boolean', 'try', 'catch',
        }
        return [t if t in java_keywords else '__ID__' for t in tokens]


class ASTSimilarityComparator:
    """
    Compares code similarity using AST analysis.

    Uses multiple techniques:
    1. Structural similarity (tree edit distance approximation)
    2. Token sequence similarity (normalized identifiers)
    3. Control flow similarity
    """

    def __init__(self, language: str = "python"):
        self.language = language.lower()
        self.python_parser = PythonASTParser()
        self.java_parser = JavaASTParser()

    def get_parser(self):
        """Get appropriate parser for language."""
        if self.language == "python":
            return self.python_parser
        elif self.language == "java":
            return self.java_parser
        return self.python_parser  # Default

    def compute_similarity(self, code1: str, code2: str) -> ASTSimilarityResult:
        """
        Compute AST-based similarity between two code snippets.

        Args:
            code1: First code
            code2: Second code

        Returns:
            ASTSimilarityResult with detailed scores
        """
        parser = self.get_parser()

        ast1 = parser.parse(code1)
        ast2 = parser.parse(code2)

        if ast1 is None or ast2 is None:
            return ASTSimilarityResult(
                score=0.0,
                structural_similarity=0.0,
                token_similarity=0.0,
                differences=["Failed to parse one or both code snippets"],
            )

        # Normalize ASTs
        parser.normalize_tree(ast1)
        parser.normalize_tree(ast2)

        # Compute structural similarity
        struct_sim = self._structural_similarity(ast1, ast2)

        # Compute token similarity
        tokens1 = parser.extract_structure_tokens(ast1)
        tokens2 = parser.extract_structure_tokens(ast2)
        token_sim = self._jaccard_similarity(tokens1, tokens2)

        # Combined score (weighted)
        score = 0.6 * struct_sim + 0.4 * token_sim

        # Find common patterns and differences
        common_patterns = self._find_common_patterns(ast1, ast2)
        differences = self._find_differences(ast1, ast2)

        return ASTSimilarityResult(
            score=round(score, 4),
            structural_similarity=round(struct_sim, 4),
            token_similarity=round(token_sim, 4),
            common_patterns=common_patterns,
            differences=differences,
        )

    def _structural_similarity(self, tree1: ASTNode, tree2: ASTNode) -> float:
        """
        Compute structural similarity using tree structure comparison.
        
        Uses a simplified tree edit distance approximation:
        - Compare node type sequences
        - Weight by depth and position
        """
        nodes1 = tree1.walk()
        nodes2 = tree2.walk()

        if not nodes1 or not nodes2:
            return 0.0

        # Build node type counts at each depth
        depth_types1 = defaultdict(Counter)
        depth_types2 = defaultdict(Counter)

        for node in nodes1:
            depth = self._get_depth(node, tree1)
            depth_types1[depth][node.node_type] += 1

        for node in nodes2:
            depth = self._get_depth(node, tree2)
            depth_types2[depth][node.node_type] += 1

        # Compare at each depth level
        all_depths = set(list(depth_types1.keys()) + list(depth_types2.keys()))
        if not all_depths:
            return 0.0

        similarities = []
        for depth in all_depths:
            types1 = set(depth_types1[depth].keys())
            types2 = set(depth_types2[depth].keys())
            sim = len(types1 & types2) / max(1, len(types1 | types2))
            similarities.append(sim)

        return sum(similarities) / len(similarities) if similarities else 0.0

    def _get_depth(self, node: ASTNode, root: ASTNode) -> int:
        """Get depth of node in tree."""
        if node is root:
            return 0
        for child in root.children:
            depth = self._get_depth(node, child)
            if depth >= 0:
                return depth + 1
        return -1

    def _jaccard_similarity(self, seq1: List[str], seq2: List[str]) -> float:
        """Compute Jaccard similarity between two sequences."""
        set1 = set(seq1)
        set2 = set(seq2)
        if not set1 and not set2:
            return 1.0
        return len(set1 & set2) / len(set1 | set2)

    def _find_common_patterns(self, tree1: ASTNode, tree2: ASTNode) -> List[str]:
        """Find common structural patterns between two ASTs."""
        patterns = []
        types1 = set(n.node_type for n in tree1.walk())
        types2 = set(n.node_type for n in tree2.walk())
        
        common = types1 & types2
        important_types = {'FunctionDef', 'MethodDeclaration', 'For', 'While', 
                          'If', 'ClassDef', 'Return', 'Statement'}
        
        for t in common:
            if t in important_types:
                patterns.append(f"Both have {t}")
        
        return patterns

    def _find_differences(self, tree1: ASTNode, tree2: ASTNode) -> List[str]:
        """Find structural differences between two ASTs."""
        diffs = []
        types1 = set(n.node_type for n in tree1.walk())
        types2 = set(n.node_type for n in tree2.walk())
        
        only_in_1 = types1 - types2
        only_in_2 = types2 - types1
        
        for t in only_in_1:
            diffs.append(f"Only in code1: {t}")
        for t in only_in_2:
            diffs.append(f"Only in code2: {t}")
        
        return diffs


# Convenience function
def ast_compare(code1: str, code2: str, language: str = "python") -> Dict[str, Any]:
    """
    Quick AST-based similarity comparison.

    Args:
        code1: First code
        code2: Second code
        language: Programming language

    Returns:
        Dict with similarity results
    """
    comparator = ASTSimilarityComparator(language=language)
    result = comparator.compute_similarity(code1, code2)
    return {
        "score": result.score,
        "structural_similarity": result.structural_similarity,
        "token_similarity": result.token_similarity,
        "common_patterns": result.common_patterns,
        "differences": result.differences,
    }