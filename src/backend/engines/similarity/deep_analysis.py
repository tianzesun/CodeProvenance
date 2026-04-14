"""
Deep Code Analysis Module.

Advanced code similarity detection using multiple techniques:
- Tree Edit Distance (TED) for AST comparison
- Tree Kernel Similarity for structural matching
- Control Flow Graph (CFG) analysis
- Normalized AST comparison (variable renaming insensitive)
- Subtree isomorphism detection
- Pattern-based clone detection
"""

from typing import List, Dict, Any, Tuple, Set, Optional
from collections import Counter
import hashlib
import re


class DeepCodeAnalyzer:
    """
    Advanced code analyzer that provides deep structural analysis.
    
    Combines multiple techniques for accurate plagiarism detection:
    - Normalized AST comparison (ignores variable names)
    - Tree edit distance for structural similarity
    - Tree kernel similarity for subtree matching
    - Pattern detection for common code structures
    - Control flow analysis
    """
    
    def __init__(self):
        self.reserved_keywords = {
            'python': {'def', 'class', 'if', 'else', 'elif', 'for', 'while', 'try', 
                      'except', 'finally', 'with', 'return', 'yield', 'import', 'from',
                      'as', 'pass', 'break', 'continue', 'raise', 'lambda', 'and', 'or',
                      'not', 'in', 'is', 'True', 'False', 'None', 'global', 'nonlocal'},
            'java': {'public', 'private', 'protected', 'class', 'interface', 'extends',
                    'implements', 'if', 'else', 'for', 'while', 'do', 'switch', 'case',
                    'break', 'continue', 'return', 'try', 'catch', 'finally', 'throw',
                    'throws', 'new', 'this', 'super', 'import', 'package', 'static',
                    'final', 'abstract', 'void', 'int', 'long', 'double', 'float', 'boolean',
                    'char', 'byte', 'short', 'true', 'false', 'null'},
            'javascript': {'function', 'const', 'let', 'var', 'if', 'else', 'for', 'while',
                         'do', 'switch', 'case', 'break', 'continue', 'return', 'try',
                         'catch', 'finally', 'throw', 'new', 'this', 'class', 'extends',
                         'import', 'export', 'default', 'async', 'await', 'yield', 'true',
                         'false', 'null', 'undefined'},
            'default': set()
        }
    
    def analyze(self, parsed_code: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform comprehensive analysis on parsed code.
        
        Args:
            parsed_code: Parsed code representation with tokens, ast, etc.
            
        Returns:
            Dictionary with analysis results
        """
        ast = parsed_code.get('ast')
        tokens = parsed_code.get('tokens', [])
        lines = parsed_code.get('lines', [])
        
        result = {
            'ast_normalized': None,
            'ast_statistics': {},
            'control_flow': None,
            'patterns': [],
            'subtrees': [],
            'complexity_metrics': {},
            'structure_fingerprint': None
        }
        
        if ast:
            # Normalize AST (replace identifiers with placeholders)
            result['ast_normalized'] = self._normalize_ast(ast)
            
            # Get AST statistics
            result['ast_statistics'] = self._get_ast_statistics(ast)
            
            # Extract patterns (common code structures)
            result['patterns'] = self._extract_patterns(ast)
            
            # Extract significant subtrees
            result['subtrees'] = self._extract_subtrees(ast)
            
            # Generate structure fingerprint
            result['structure_fingerprint'] = self._generate_fingerprint(ast)
        
        # Calculate complexity metrics
        result['complexity_metrics'] = self._calculate_complexity(tokens, lines)
        
        return result
    
    def _normalize_ast(self, ast: Any, language: str = 'default') -> Any:
        """
        Normalize AST by replacing identifiers with placeholders.
        
        This makes comparison insensitive to variable/function name changes.
        
        Args:
            ast: AST dictionary
            language: Programming language for keyword detection
            
        Returns:
            Normalized AST dictionary
        """
        if not isinstance(ast, dict):
            return ast
        
        # Get language-specific reserved words
        reserved = self.reserved_keywords.get(language, self.reserved_keywords['default'])
        
        result: Dict[str, Any] = {}
        for key, value in ast.items():
            if key == '_type':
                result[key] = value
            elif key in ('name', 'id', 'var', 'func', 'func_name', 'method_name',
                        'attribute', 'attr', 'arg', 'args', 'param', 'params',
                        'lhs', 'rhs', 'target', 'value', 'body'):
                # Replace identifiers with placeholders
                if isinstance(value, str) and value not in reserved:
                    result[key] = '<ID>'
                elif isinstance(value, dict):
                    result[key] = self._normalize_ast(value, language)
                elif isinstance(value, list):
                    result[key] = [self._normalize_ast(v, language) if isinstance(v, dict) else v for v in value]
                else:
                    result[key] = value
            elif isinstance(value, dict):
                result[key] = self._normalize_ast(value, language)
            elif isinstance(value, list):
                result[key] = [self._normalize_ast(v, language) if isinstance(v, dict) else v for v in value]
            else:
                result[key] = value
        
        return result
    
    def _get_ast_statistics(self, ast: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate statistics about the AST.
        
        Args:
            ast: AST dictionary
            
        Returns:
            Dictionary with AST statistics
        """
        node_types = []
        total_nodes = [0]  # Use list for mutable counter
        max_depth = [0]
        
        def traverse(node, depth=0):
            max_depth[0] = max(max_depth[0], depth)
            
            if isinstance(node, dict):
                total_nodes[0] += 1
                node_type = node.get('_type', 'Unknown')
                if node_type:
                    node_types.append(node_type)
                for key, value in node.items():
                    traverse(value, depth + 1)
            elif isinstance(node, list):
                for item in node:
                    traverse(item, depth)
        
        traverse(ast)
        
        # Count node type frequencies
        type_counts = Counter(node_types)
        
        return {
            'total_nodes': total_nodes[0],
            'max_depth': max_depth[0],
            'unique_node_types': len(type_counts),
            'node_type_distribution': dict(type_counts.most_common(10)),
            'type_ratio': len(set(node_types)) / max(total_nodes[0], 1)
        }
    
    def _extract_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract common code patterns from AST.
        
        Args:
            ast: AST dictionary
            
        Returns:
            List of detected patterns
        """
        patterns = []
        
        def traverse(node, path=None):
            if path is None:
                path = []
            
            if isinstance(node, dict):
                node_type = node.get('_type', '')
                
                # Detect common patterns
                if node_type == 'For':
                    patterns.append({
                        'type': 'for_loop',
                        'signature': self._get_node_signature(node)
                    })
                elif node_type == 'While':
                    patterns.append({
                        'type': 'while_loop',
                        'signature': self._get_node_signature(node)
                    })
                elif node_type == 'If':
                    patterns.append({
                        'type': 'conditional',
                        'signature': self._get_node_signature(node)
                    })
                elif node_type in ('FunctionDef', 'FunctionDeclaration', 'FunctionExpression'):
                    patterns.append({
                        'type': 'function',
                        'signature': self._get_node_signature(node)
                    })
                elif node_type in ('ClassDef', 'ClassDeclaration', 'Class'):
                    patterns.append({
                        'type': 'class',
                        'signature': self._get_node_signature(node)
                    })
                elif node_type == 'Try':
                    patterns.append({
                        'type': 'exception_handling',
                        'signature': self._get_node_signature(node)
                    })
                
                for key, value in node.items():
                    traverse(value, path + [node_type])
            elif isinstance(node, list):
                for item in node:
                    traverse(item, path)
        
        traverse(ast)
        return patterns
    
    def _get_node_signature(self, node: Dict[str, Any]) -> str:
        """
        Generate a signature for a node based on its structure.
        
        Args:
            node: AST node dictionary
            
        Returns:
            Signature string
        """
        node_type = node.get('_type', '')
        
        # Count children by type
        children_types = []
        for key, value in node.items():
            if key != '_type':
                if isinstance(value, dict) and '_type' in value:
                    children_types.append(value['_type'])
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict) and '_type' in item:
                            children_types.append(item['_type'])
        
        return f"{node_type}:{','.join(sorted(set(children_types)))}"
    
    def _extract_subtrees(self, ast: Dict[str, Any], min_size: int = 3) -> List[str]:
        """
        Extract significant subtrees from AST.
        
        Args:
            ast: AST dictionary
            min_size: Minimum subtree size to extract
            
        Returns:
            List of subtree hashes
        """
        subtrees = []
        
        def get_subtree_hash(node, depth=0):
            if not isinstance(node, dict):
                return None
            
            # Serialize the subtree
            serialized = self._serialize_subtree(node)
            if serialized:
                return hashlib.sha256(serialized.encode()).hexdigest()[:16]
            return None
        
        def traverse(node):
            if isinstance(node, dict):
                # Check if this is a significant subtree
                subtree_hash = get_subtree_hash(node)
                if subtree_hash:
                    subtrees.append(subtree_hash)
                
                # Traverse children
                for key, value in node.items():
                    traverse(value)
            elif isinstance(node, list):
                for item in node:
                    traverse(item)
        
        traverse(ast)
        return list(set(subtrees))  # Remove duplicates
    
    def _serialize_subtree(self, node: Dict[str, Any]) -> Optional[str]:
        """
        Serialize a subtree to a canonical string.
        
        Args:
            node: AST node dictionary
            
        Returns:
            Serialized string or None
        """
        if not isinstance(node, dict):
            return None
        
        parts = []
        node_type = node.get('_type', '')
        if node_type:
            parts.append(node_type)
        
        for key, value in sorted(node.items()):
            if key == '_type':
                continue
            if isinstance(value, dict):
                sub_type = value.get('_type', '')
                if sub_type:
                    parts.append(sub_type)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        sub_type = item.get('_type', '')
                        if sub_type:
                            parts.append(sub_type)
        
        return '|'.join(parts) if parts else None
    
    def _generate_fingerprint(self, ast: Dict[str, Any]) -> str:
        """
        Generate a structural fingerprint for the AST.
        
        Args:
            ast: AST dictionary
            
        Returns:
            Fingerprint string
        """
        # Count node type frequencies
        type_counts = Counter()
        
        def traverse(node):
            if isinstance(node, dict):
                node_type = node.get('_type', '')
                if node_type:
                    type_counts[node_type] += 1
                for key, value in node.items():
                    traverse(value)
            elif isinstance(node, list):
                for item in node:
                    traverse(item)
        
        traverse(ast)
        
        # Create fingerprint from type distribution
        sorted_types = sorted(type_counts.items(), key=lambda x: x[0])
        fingerprint_parts = [f"{t}:{c}" for t, c in sorted_types]
        
        fingerprint = '|'.join(fingerprint_parts)
        return hashlib.sha256(fingerprint.encode()).hexdigest()[:32]
    
    def _calculate_complexity(self, tokens: List[str], lines: List[str]) -> Dict[str, Any]:
        """
        Calculate code complexity metrics.
        
        Args:
            tokens: List of tokens
            lines: List of lines
            
        Returns:
            Dictionary with complexity metrics
        """
        return {
            'token_count': len(tokens),
            'line_count': len(lines),
            'blank_line_count': sum(1 for line in lines if not line.strip()),
            'comment_ratio': self._estimate_comment_ratio(lines),
            'unique_token_ratio': len(set(tokens)) / max(len(tokens), 1),
            'avg_line_length': sum(len(line) for line in lines) / max(len(lines), 1)
        }
    
    def _estimate_comment_ratio(self, lines: List[str]) -> float:
        """
        Estimate the ratio of comment lines.
        
        Args:
            lines: List of lines
            
        Returns:
            Estimated comment ratio
        """
        comment_patterns = [
            r'^\s*#',      # Python
            r'^\s*//',     # C/C++/Java/JavaScript
            r'^\s*/\*',    # C block comment start
            r'^\s*\*',     # Continuation
            r'^\s*/\*',    # Block comment
            r'^\s*<!--',   # HTML
            r'^\s*--',     # SQL
        ]
        
        comment_lines = 0
        in_block_comment = False
        
        for line in lines:
            stripped = line.strip()
            
            if in_block_comment:
                comment_lines += 1
                if '*/' in stripped:
                    in_block_comment = False
                continue
            
            for pattern in comment_patterns:
                if re.match(pattern, line):
                    comment_lines += 1
                    break
            
            if '/*' in stripped and '*/' not in stripped:
                in_block_comment = True
        
        return comment_lines / max(len(lines), 1)


class ASTTreeEditDistance:
    """
    Tree Edit Distance (TED) calculator for AST comparison.
    
    Implements Zhang-Shasha algorithm for efficient tree comparison.
    """
    
    def __init__(self):
        self._cache = {}
    
    def calculate_distance(self, ast_a: Dict[str, Any], ast_b: Dict[str, Any]) -> float:
        """
        Calculate normalized tree edit distance between two ASTs.
        
        Args:
            ast_a: First AST
            ast_b: Second AST
            
        Returns:
            Normalized distance (0 = identical, 1 = completely different)
        """
        # Serialize ASTs to tree structures
        tree_a = self._ast_to_tree(ast_a)
        tree_b = self._ast_to_tree(ast_b)
        
        # Calculate edit distance
        distance = self._zhang_shasha(tree_a, tree_b)
        
        # Normalize by maximum possible distance
        max_nodes = max(self._count_nodes(tree_a), self._count_nodes(tree_b))
        if max_nodes == 0:
            return 0.0
        
        return distance / max_nodes
    
    def _ast_to_tree(self, ast: Dict[str, Any]) -> 'TreeNode':
        """Convert AST dict to TreeNode structure."""
        if not isinstance(ast, dict):
            return None
        
        node_type = ast.get('_type', 'Unknown')
        node = TreeNode(node_type)
        
        for key, value in ast.items():
            if key == '_type':
                continue
            if isinstance(value, dict):
                child = self._ast_to_tree(value)
                if child:
                    node.add_child(child)
            elif isinstance(value, list):
                for item in value:
                    child = self._ast_to_tree(item)
                    if child:
                        node.add_child(child)
        
        return node
    
    def _count_nodes(self, node: 'TreeNode') -> int:
        """Count total nodes in tree."""
        if node is None:
            return 0
        return 1 + sum(self._count_nodes(child) for child in node.children)
    
    def _zhang_shasha(self, tree_a: 'TreeNode', tree_b: 'TreeNode') -> int:
        """
        Zhang-Shasha algorithm for tree edit distance.
        
        Simplified implementation for demonstration.
        """
        if tree_a is None and tree_b is None:
            return 0
        if tree_a is None:
            return self._count_nodes(tree_b)
        if tree_b is None:
            return self._count_nodes(tree_a)
        
        # Build tree lists (preorder with keyroots)
        tree_a_list = self._tree_to_list(tree_a)
        tree_b_list = self._tree_to_list(tree_b)
        
        # Simple tree distance using tree size difference as approximation
        # Full Zhang-Shasha is complex; this is a practical approximation
        size_a = self._count_nodes(tree_a)
        size_b = self._count_nodes(tree_b)
        
        # Calculate based on structural similarity
        type_a = self._get_all_types(tree_a)
        type_b = self._get_all_types(tree_b)
        
        common_types = len(type_a.intersection(type_b))
        total_types = len(type_a.union(type_b))
        
        if total_types == 0:
            return 0
        
        # Approximate distance
        type_distance = 1 - (common_types / total_types)
        size_distance = abs(size_a - size_b) / max(size_a, size_b, 1)
        
        return int((type_distance * 0.7 + size_distance * 0.3) * max(size_a, size_b))
    
    def _tree_to_list(self, node: 'TreeNode') -> List['TreeNode']:
        """Convert tree to list in preorder."""
        if node is None:
            return []
        result = [node]
        for child in node.children:
            result.extend(self._tree_to_list(child))
        return result
    
    def _get_all_types(self, node: 'TreeNode') -> Set[str]:
        """Get all node types in tree."""
        if node is None:
            return set()
        types = {node.label}
        for child in node.children:
            types.update(self._get_all_types(child))
        return types


class TreeNode:
    """Simple tree node for AST representation."""
    
    def __init__(self, label: str):
        self.label = label
        self.children: List['TreeNode'] = []
    
    def add_child(self, child: 'TreeNode'):
        self.children.append(child)
    
    def __repr__(self):
        return f"TreeNode({self.label}, {len(self.children)} children)"


class TreeKernelSimilarity:
    """
    Tree Kernel similarity for comparing ASTs.
    
    Uses subtree patterns to measure structural similarity.
    """
    
    def __init__(self):
        self._cache = {}
    
    def calculate_similarity(self, ast_a: Dict[str, Any], ast_b: Dict[str, Any]) -> float:
        """
        Calculate tree kernel similarity between two ASTs.
        
        Args:
            ast_a: First AST
            ast_b: Second AST
            
        Returns:
            Similarity score between 0.0 and 1.0
        """
        # Extract all subtrees up to a certain depth
        subtrees_a = self._extract_subtrees(ast_a, max_depth=4)
        subtrees_b = self._extract_subtrees(ast_b, max_depth=4)
        
        if not subtrees_a and not subtrees_b:
            return 1.0
        if not subtrees_a or not subtrees_b:
            return 0.0
        
        # Count subtree frequencies
        counts_a = Counter(subtrees_a)
        counts_b = Counter(subtrees_b)
        
        # Calculate kernel value
        kernel_value = sum(min(counts_a[s], counts_b[s]) for s in set(subtrees_a) & set(subtrees_b))
        
        # Normalize
        norm_a = sum(c * c for c in counts_a.values())
        norm_b = sum(c * c for c in counts_b.values())
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return kernel_value / (norm_a ** 0.5 * norm_b ** 0.5)
    
    def _extract_subtrees(self, ast: Dict[str, Any], max_depth: int = 4) -> List[str]:
        """Extract subtree patterns from AST."""
        subtrees = []
        
        def traverse(node, depth=0, path=None):
            if path is None:
                path = []
            if depth > max_depth:
                return
            if not isinstance(node, dict):
                return
            
            node_type = node.get('_type', '')
            current_path = path + [node_type]
            
            # Add this subtree pattern
            subtrees.append('->'.join(current_path))
            
            # Continue traversing
            for key, value in node.items():
                if key == '_type':
                    continue
                if isinstance(value, dict):
                    traverse(value, depth + 1, current_path)
                elif isinstance(value, list):
                    for item in value:
                        traverse(item, depth + 1, current_path)
        
        traverse(ast)
        return subtrees


class ControlFlowAnalyzer:
    """
    Control Flow Graph (CFG) analyzer for code comparison.
    
    Extracts control flow patterns for similarity detection.
    """
    
    def analyze(self, ast: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze control flow from AST.
        
        Args:
            ast: AST dictionary
            
        Returns:
            Control flow analysis results
        """
        cfg = {
            'nodes': [],
            'edges': [],
            'entry_point': None,
            'exit_points': [],
            'branching_factor': 0,
            'loop_count': 0,
            'conditional_count': 0
        }
        
        node_counter = [0]  # Use list for mutable counter
        
        def traverse(node, parent_id=None):
            if not isinstance(node, dict):
                return
            
            node_type = node.get('_type', '')
            current_id = node_counter[0]
            node_counter[0] += 1
            
            cfg['nodes'].append({
                'id': current_id,
                'type': node_type
            })
            
            if cfg['entry_point'] is None:
                cfg['entry_point'] = current_id
            
            if parent_id is not None:
                cfg['edges'].append((parent_id, current_id))
            
            # Track control flow structures
            if node_type in ('For', 'While', 'DoWhile'):
                cfg['loop_count'] += 1
            if node_type in ('If', 'Switch', 'Conditional'):
                cfg['conditional_count'] += 1
            
            # Process children
            children = []
            for key, value in node.items():
                if key == '_type':
                    continue
                if isinstance(value, dict):
                    child_id = traverse(value, current_id)
                    if child_id is not None:
                        children.append(child_id)
                elif isinstance(value, list):
                    for item in value:
                        child_id = traverse(item, current_id)
                        if child_id is not None:
                            children.append(child_id)
            
            # Mark exit points
            if node_type in ('Return', 'Break', 'Continue', 'Throw'):
                cfg['exit_points'].append(current_id)
            
            return current_id
        
        traverse(ast)
        
        # Calculate branching factor
        if cfg['nodes']:
            cfg['branching_factor'] = len(cfg['edges']) / len(cfg['nodes'])
        
        return cfg
    
    def compare_cfg(self, cfg_a: Dict[str, Any], cfg_b: Dict[str, Any]) -> float:
        """
        Compare two control flow graphs.
        
        Args:
            cfg_a: First CFG
            cfg_b: Second CFG
            
        Returns:
            Similarity score between 0.0 and 1.0
        """
        # Compare structure metrics
        metrics_a = {
            'loops': cfg_a['loop_count'],
            'conditionals': cfg_a['conditional_count'],
            'branching': cfg_a['branching_factor'],
            'nodes': len(cfg_a['nodes']),
            'edges': len(cfg_a['edges'])
        }
        
        metrics_b = {
            'loops': cfg_b['loop_count'],
            'conditionals': cfg_b['conditional_count'],
            'branching': cfg_b['branching_factor'],
            'nodes': len(cfg_b['nodes']),
            'edges': len(cfg_b['edges'])
        }
        
        # Calculate similarity for each metric
        similarities = []
        for key in metrics_a:
            if metrics_a[key] == 0 and metrics_b[key] == 0:
                similarities.append(1.0)
            elif metrics_a[key] == 0 or metrics_b[key] == 0:
                similarities.append(0.0)
            else:
                similarities.append(min(metrics_a[key], metrics_b[key]) / max(metrics_a[key], metrics_b[key]))
        
        return sum(similarities) / len(similarities)


class PatternCloneDetector:
    """
    Detects pattern-based code clones.
    
    Identifies common programming patterns that may indicate copied code.
    """
    
    # Common suspicious pattern combinations
    SUSPICIOUS_PATTERNS = [
        # Same control flow structure
        ('For', 'For'),
        ('While', 'While'),
        ('For', 'While'),  # Can be converted
        # Same nested depth
        # Same pattern sequence
    ]
    
    def detect_clones(self, analysis_a: Dict[str, Any], analysis_b: Dict[str, Any]) -> Dict[str, Any]:
        """
        Detect code clones between two code analyses.
        
        Args:
            analysis_a: First code analysis result
            analysis_b: Second code analysis result
            
        Returns:
            Clone detection results
        """
        patterns_a = analysis_a.get('patterns', [])
        patterns_b = analysis_b.get('patterns', [])
        
        subtrees_a = set(analysis_a.get('subtrees', []))
        subtrees_b = set(analysis_b.get('subtrees', []))
        
        # Find common patterns
        common_subtrees = subtrees_a & subtrees_b
        common_patterns = []
        
        for p_a in patterns_a:
            for p_b in patterns_b:
                if p_a['type'] == p_b['type']:
                    common_patterns.append({
                        'type': p_a['type'],
                        'signature_a': p_a['signature'],
                        'signature_b': p_b['signature']
                    })
        
        # Calculate clone scores
        subtree_score = len(common_subtrees) / max(len(subtrees_a | subtrees_b), 1)
        pattern_score = len(common_patterns) / max(len(patterns_a), len(patterns_b), 1)
        
        # Combined score
        clone_score = (subtree_score * 0.6 + pattern_score * 0.4)
        
        return {
            'clone_score': clone_score,
            'common_subtree_count': len(common_subtrees),
            'common_pattern_count': len(common_patterns),
            'common_patterns': common_patterns,
            'is_suspicious': clone_score > 0.5
        }


# Convenience function for full analysis
def analyze_code_deep(parsed_code: Dict[str, Any], language: str = 'default') -> Dict[str, Any]:
    """
    Perform comprehensive deep analysis on parsed code.
    
    Args:
        parsed_code: Parsed code representation
        language: Programming language
        
    Returns:
        Comprehensive analysis results
    """
    analyzer = DeepCodeAnalyzer()
    cfg_analyzer = ControlFlowAnalyzer()
    
    # Basic deep analysis
    analysis = analyzer.analyze(parsed_code)
    
    # Control flow analysis
    ast = parsed_code.get('ast')
    if ast:
        analysis['control_flow'] = cfg_analyzer.analyze(ast)
    
    return analysis


def compare_codes_deep(
    parsed_a: Dict[str, Any],
    parsed_b: Dict[str, Any],
    language: str = 'default'
) -> Dict[str, Any]:
    """
    Compare two code files using deep analysis techniques.
    
    Args:
        parsed_a: First parsed code
        parsed_b: Second parsed code
        language: Programming language
        
    Returns:
        Comparison results with detailed scores
    """
    # Perform deep analysis on both
    analysis_a = analyze_code_deep(parsed_a, language)
    analysis_b = analyze_code_deep(parsed_b, language)
    
    # Calculate various similarity metrics
    ted = ASTTreeEditDistance()
    tk = TreeKernelSimilarity()
    cfg_analyzer = ControlFlowAnalyzer()
    clone_detector = PatternCloneDetector()
    
    ast_a = parsed_a.get('ast')
    ast_b = parsed_b.get('ast')
    
    results = {
        'tree_edit_distance': 1.0,
        'tree_kernel_similarity': 0.0,
        'cfg_similarity': 0.0,
        'clone_detection': {},
        'normalized_ast_similarity': 0.0,
        'combined_score': 0.0
    }
    
    if ast_a and ast_b:
        # Tree edit distance (lower is more similar)
        results['tree_edit_distance'] = ted.calculate_distance(ast_a, ast_b)
        
        # Tree kernel similarity
        results['tree_kernel_similarity'] = tk.calculate_similarity(ast_a, ast_b)
        
        # Normalized AST similarity
        analyzer = DeepCodeAnalyzer()
        norm_a = analyzer._normalize_ast(ast_a, language)
        norm_b = analyzer._normalize_ast(ast_b, language)
        results['normalized_ast_similarity'] = _dict_similarity(norm_a, norm_b)
        
        # Control flow comparison
        cfg_a = cfg_analyzer.analyze(ast_a)
        cfg_b = cfg_analyzer.analyze(ast_b)
        results['cfg_similarity'] = cfg_analyzer.compare_cfg(cfg_a, cfg_b)
    
    # Clone detection
    results['clone_detection'] = clone_detector.detect_clones(analysis_a, analysis_b)
    
    # Calculate combined score
    # Weight different metrics appropriately
    ted_similarity = 1.0 - results['tree_edit_distance']  # Convert distance to similarity
    results['combined_score'] = (
        ted_similarity * 0.25 +
        results['tree_kernel_similarity'] * 0.25 +
        results['normalized_ast_similarity'] * 0.20 +
        results['cfg_similarity'] * 0.15 +
        results['clone_detection']['clone_score'] * 0.15
    )
    
    return results


def _dict_similarity(dict_a: Any, dict_b: Any) -> float:
    """Calculate similarity between two dict structures."""
    if type(dict_a) != type(dict_b):
        return 0.0
    
    if isinstance(dict_a, dict):
        keys_a = set(dict_a.keys())
        keys_b = set(dict_b.keys())
        
        if not keys_a and not keys_b:
            return 1.0
        if not keys_a or not keys_b:
            return 0.0
        
        common_keys = keys_a & keys_b
        all_keys = keys_a | keys_b
        
        if not common_keys:
            return 0.0
        
        # Calculate similarity for common keys
        similarities = []
        for key in common_keys:
            similarities.append(_dict_similarity(dict_a[key], dict_b[key]))
        
        return sum(similarities) / len(similarities)
    
    elif isinstance(dict_a, list):
        if len(dict_a) != len(dict_b):
            return 0.0
        if not dict_a:
            return 1.0
        
        similarities = [_dict_similarity(a, b) for a, b in zip(dict_a, dict_b)]
        return sum(similarities) / len(similarities)
    
    else:
        # Primitive comparison
        return 1.0 if dict_a == dict_b else 0.0
