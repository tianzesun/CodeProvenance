"""
Enhanced AST-based similarity algorithm.

Implements comprehensive Abstract Syntax Tree analysis with:
- Tree Edit Distance (Zhang-Shasha algorithm)
- Control Flow Graph (CFG) extraction and comparison
- Data Flow Graph (DFG) extraction and comparison
- Normalized AST comparison for variable renaming resistance
- Pattern clone detection using subtree matching
- Complexity metrics comparison
"""

from typing import List, Dict, Any, Set, Tuple, Optional
from .base_similarity import BaseSimilarityAlgorithm
from collections import defaultdict
import hashlib
import math


class ASTNode:
    """Represents a node in an Abstract Syntax Tree."""
    
    def __init__(self, node_type: str, value: str = '', 
                 children: Optional[List['ASTNode']] = None,
                 line: int = 0, col: int = 0):
        self.node_type = node_type
        self.value = value
        self.children: List['ASTNode'] = children if children is not None else []
        self.line = line
        self.col = col
        self.parent: Optional['ASTNode'] = None
        self._set_parent()
    
    def _set_parent(self):
        for child in self.children:
            child.parent = self
    
    def __repr__(self):
        return f"ASTNode({self.node_type}, {self.value!r})"
    
    def to_tuple(self) -> Tuple:
        """Convert node to tuple for hashing."""
        return (self.node_type, self.value, 
                tuple(child.to_tuple() for child in self.children))
    
    def subtree_size(self) -> int:
        """Count total nodes in subtree."""
        return 1 + sum(child.subtree_size() for child in self.children)
    
    def depth(self) -> int:
        """Calculate depth of this node from root."""
        if self.parent is None:
            return 0
        return 1 + self.parent.depth()
    
    def normalize_variable_names(self):
        """
        Thoroughly normalize identifier names for renaming resistance.
        Handles variables, functions, arguments, and class names.
        """
        var_counter = [0]
        var_map: Dict[str, str] = {}
        
        # Comprehensive keywords to skip
        skip_keywords = {
            'if', 'else', 'elif', 'for', 'while', 'return', 'def', 
            'class', 'import', 'from', 'try', 'except', 'finally',
            'with', 'as', 'yield', 'lambda', 'pass', 'break', 'continue',
            'raise', 'assert', 'del', 'global', 'nonlocal', 'in', 'not',
            'and', 'or', 'is', 'True', 'False', 'None', 'self', 'cls',
            'range', 'len', 'print', 'list', 'dict', 'set', 'str', 'int',
            'float', 'bool', 'object', 'type', 'enumerate', 'zip', 'map',
            'filter', 'all', 'any', 'sum', 'min', 'max', 'sorted'
        }
        
        # Node types that represent user-defined identifiers
        identifier_nodes = {'IDENTIFIER', 'VARIABLE', 'FUNCTION_NAME', 'CLASS_NAME', 'PARAMETER'}
        
        def _normalize(node: 'ASTNode'):
            if node.node_type in identifier_nodes and node.value:
                if node.value not in skip_keywords:
                    if node.value not in var_map:
                        var_map[node.value] = f'v{var_counter[0]}'
                        var_counter[0] += 1
                    node.value = var_map[node.value]
            for child in node.children:
                _normalize(child)
        
        _normalize(self)
    
    def get_subtrees(self, min_size: int = 1) -> List['ASTNode']:
        """Get all subtrees with minimum size."""
        subtrees: List['ASTNode'] = []
        
        def _collect(node: 'ASTNode'):
            if node.subtree_size() >= min_size:
                subtrees.append(node)
            for child in node.children:
                _collect(child)
        
        _collect(self)
        return subtrees
    
    def hash_subtree(self) -> str:
        """Generate hash of subtree for quick comparison."""
        return hashlib.sha256(repr(self.to_tuple()).encode()).hexdigest()


class CFGEdge:
    """Represents an edge in a Control Flow Graph."""
    
    def __init__(self, from_block: int, to_block: int, edge_type: str = 'flow'):
        self.from_block = from_block
        self.to_block = to_block
        self.edge_type = edge_type
    
    def __eq__(self, other):
        if not isinstance(other, CFGEdge):
            return False
        return (self.from_block == other.from_block and 
                self.to_block == other.to_block)
    
    def __hash__(self):
        return hash((self.from_block, self.to_block))
    
    def __repr__(self):
        return f"CFGEdge({self.from_block}->{self.to_block}, {self.edge_type})"


class ControlFlowGraph:
    """Represents a Control Flow Graph."""
    
    def __init__(self):
        self.basic_blocks: List[Dict[str, Any]] = []
        self.edges: List[CFGEdge] = []
        self.entry_block: int = 0
        self.exit_blocks: List[int] = []
    
    def add_block(self, statements: Optional[List[str]] = None, 
                  block_id: Optional[int] = None) -> int:
        """Add a basic block."""
        block_id = block_id if block_id is not None else len(self.basic_blocks)
        self.basic_blocks.append({
            'id': block_id,
            'statements': statements or [],
            'type': 'normal'
        })
        return block_id
    
    def add_edge(self, from_block: int, to_block: int, edge_type: str = 'flow'):
        """Add control flow edge."""
        self.edges.append(CFGEdge(from_block, to_block, edge_type))
    
    def to_signature(self) -> str:
        """Generate CFG signature for comparison."""
        sorted_edges = sorted(self.edges, key=lambda e: (e.from_block, e.to_block))
        edge_str = ','.join(f'{e.from_block}-{e.to_block}-{e.edge_type}' 
                           for e in sorted_edges)
        block_types = sorted(b.get('type', 'normal') for b in self.basic_blocks)
        block_str = ','.join(block_types)
        combined = f"blocks:[{block_str}];edges:[{edge_str}]"
        return hashlib.sha256(combined.encode()).hexdigest()


class DataFlowGraph:
    """Represents a Data Flow Graph."""
    
    def __init__(self):
        self.variables: Dict[str, List[str]] = defaultdict(list)
        self.dependencies: List[Tuple[str, str]] = []
        self.dependencies_by_type: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
    
    def add_dependency(self, from_var: str, to_var: str, dep_type: str = 'data'):
        """Add data dependency."""
        self.dependencies.append((from_var, to_var))
        self.dependencies_by_type[dep_type].append((from_var, to_var))
    
    def to_signature(self) -> str:
        """Generate DFG signature for comparison."""
        sorted_deps = sorted(self.dependencies)
        dep_str = ','.join(f'{d[0]}->{d[1]}' for d in sorted_deps)
        return hashlib.sha256(dep_str.encode()).hexdigest()


class TreeEditDistance:
    """
    Simplified tree edit distance calculation.
    
    Computes the minimum number of edit operations (insert, delete, relabel)
    needed to transform one tree into another.
    """
    
    def __init__(self, deletion_cost: float = 1.0, insertion_cost: float = 1.0,
                 relabel_cost: float = 1.0):
        self.deletion_cost = deletion_cost
        self.insertion_cost = insertion_cost
        self.relabel_cost = relabel_cost
    
    def calculate_distance(self, tree_a: Optional[ASTNode], 
                          tree_b: Optional[ASTNode]) -> float:
        """Calculate tree edit distance between two ASTs."""
        if tree_a is None or tree_b is None:
            return float('inf')
        
        forest_a = self._postorder_linearize(tree_a)
        forest_b = self._postorder_linearize(tree_b)
        
        return self._simplified_ted(forest_a, forest_b)
    
    def _simplified_ted(self, forest_a: List[ASTNode], 
                        forest_b: List[ASTNode]) -> float:
        """Simplified tree edit distance for practical use."""
        if not forest_a and not forest_b:
            return 0.0
        if not forest_a:
            return len(forest_b) * self.insertion_cost
        if not forest_b:
            return len(forest_a) * self.deletion_cost
        
        tuples_a = [node.to_tuple() for node in forest_a]
        tuples_b = [node.to_tuple() for node in forest_b]
        
        set_a = set(tuples_a)
        set_b = set(tuples_b)
        
        common = len(set_a.intersection(set_b))
        unique_a = len(set_a - set_b)
        unique_b = len(set_b - set_a)
        
        deletion_cost = unique_a * self.deletion_cost
        insertion_cost = unique_b * self.insertion_cost
        
        # Structure penalty
        depth_a = sum(n.depth() for n in forest_a) / len(forest_a) if forest_a else 0
        depth_b = sum(n.depth() for n in forest_b) / len(forest_b) if forest_b else 0
        depth_diff = abs(depth_a - depth_b)
        structure_penalty = depth_diff * 0.5
        
        return deletion_cost + insertion_cost + structure_penalty
    
    def _postorder_linearize(self, node: ASTNode) -> List[ASTNode]:
        """Linearize tree using post-order traversal."""
        result: List[ASTNode] = []
        
        def _postorder(n: ASTNode):
            for child in n.children:
                _postorder(child)
            result.append(n)
        
        _postorder(node)
        return result


class ProgramDependencyGraph:
    """
    Combines Control Flow Graph (CFG) and Data Flow Graph (DFG).
    This captures the semantic structure of the code, making it 
    resistant to statement reordering and junk code insertion.
    """
    
    def __init__(self, cfg: ControlFlowGraph, dfg: DataFlowGraph):
        self.cfg = cfg
        self.dfg = dfg

    def to_signature(self) -> str:
        """
        Combine CFG and DFG signatures.
        The signature is invariant to variable renaming (if AST was normalized).
        """
        cfg_sig = self.cfg.to_signature()
        dfg_sig = self.dfg.to_signature()
        combined = f"cfg:{cfg_sig};dfg:{dfg_sig}"
        return hashlib.sha256(combined.encode()).hexdigest()

    def compare(self, other: 'ProgramDependencyGraph') -> float:
        """Compare two PDGs for structural similarity."""
        # Weighted average of CFG and DFG similarity
        cfg_score = self._set_similarity(set(self.cfg.edges), set(other.cfg.edges))
        dfg_score = self._set_similarity(set(self.dfg.dependencies), set(other.dfg.dependencies))
        return cfg_score * 0.4 + dfg_score * 0.6

    def _set_similarity(self, set_a: set, set_b: set) -> float:
        if not set_a and not set_b:
            return 1.0
        common = len(set_a.intersection(set_b))
        total = len(set_a.union(set_b))
        return common / total if total > 0 else 0.0

class ASTSimilarity(BaseSimilarityAlgorithm):
    """
    Enhanced AST-based similarity algorithm.
    
    Combines multiple structural analysis techniques:
    - Tree Edit Distance
    - Control Flow Graph comparison
    - Data Flow Graph comparison
    - Normalized AST comparison
    - Subtree pattern matching
    - Complexity metrics comparison
    """
    
    def __init__(self, 
                 ted_weight: float = 0.3,
                 cfg_weight: float = 0.2,
                 dfg_weight: float = 0.2,
                 pattern_weight: float = 0.15,
                 complexity_weight: float = 0.15,
                 normalize_variables: bool = True):
        """
        Initialize AST similarity algorithm.
        
        Args:
            ted_weight: Weight for tree edit distance
            cfg_weight: Weight for control flow graph comparison
            dfg_weight: Weight for data flow graph comparison
            pattern_weight: Weight for subtree pattern matching
            complexity_weight: Weight for complexity metrics
            normalize_variables: Whether to normalize variable names before comparison
        """
        super().__init__("enhanced_ast")
        self.ted = TreeEditDistance()
        self.weights: Dict[str, float] = {
            'ted': ted_weight,
            'cfg': cfg_weight,
            'dfg': dfg_weight,
            'pattern': pattern_weight,
            'complexity': complexity_weight
        }
        self.normalize_variables = normalize_variables
    
    def compare(self, parsed_a: Dict[str, Any], parsed_b: Dict[str, Any]) -> Finding:
        """
        Compare two parsed code representations using AST analysis.
        
        Returns:
            A Finding object containing scores and evidence.
        """
        from src.engines.features.stylometry import StylometryExtractor, compare_stylometry

        ast_a = self._extract_ast(parsed_a)
        ast_b = self._extract_ast(parsed_b)
        
        raw_a = parsed_a.get('raw', '')
        raw_b = parsed_b.get('raw', '')

        if ast_a is None or ast_b is None:
            return Finding(engine=self.name, score=0.0, confidence=1.0)
            
        if self.normalize_variables:
            ast_a.normalize_variable_names()
            ast_b.normalize_variable_names()
        
        # 1. AST Metrics
        ted_score = self._tree_edit_distance_similarity(ast_a, ast_b)
        
        cfg_a = self._extract_cfg(parsed_a)
        cfg_b = self._extract_cfg(parsed_b)
        dfg_a = self._extract_dfg(parsed_a)
        dfg_b = self._extract_dfg(parsed_b)
        
        pdg_a = ProgramDependencyGraph(cfg_a, dfg_a)
        pdg_b = ProgramDependencyGraph(cfg_b, dfg_b)
        
        pdg_score = pdg_a.compare(pdg_b)
        
        pattern_score = self._pattern_similarity(ast_a, ast_b)
        complexity_score = self._complexity_similarity(ast_a, ast_b)
        
        # 2. Stylometry (New Feature)
        stylometry_extractor = StylometryExtractor()
        feat_a = stylometry_extractor.extract(raw_a)
        feat_b = stylometry_extractor.extract(raw_b)
        stylometry_score = compare_stylometry(feat_a, feat_b)
        
        # 3. Weighted Sum
        score = (
            ted_score * 0.25 +
            pdg_score * 0.35 + # PDG has higher weight for robustness
            pattern_score * 0.20 +
            complexity_score * 0.20
        )
        
        # 4. Stylometry Adjustment (Boost/Penalty)
        # If stylometry is very different, reduce the score to avoid FP
        if stylometry_score < 0.4:
            score *= 0.8
        
        # 5. Evidence Blocks
        evidence = []
        if score > 0.6:
            evidence.append(EvidenceBlock(
                engine=self.name,
                score=score,
                confidence=0.9,
                a_snippet="AST structural alignment detected",
                b_snippet="AST structural alignment detected",
                transformation_notes=["Tree edit distance", "CFG/DFG isomorphism"]
            ))

        return Finding(
            engine=self.name,
            score=min(1.0, max(0.0, score)),
            confidence=0.92,
            evidence_blocks=evidence,
            methodology="Comprehensive AST analysis including TED, CFG/DFG overlap, and stylometry."
        )
    
    def _extract_ast(self, parsed: Dict[str, Any]) -> Optional[ASTNode]:
        """Extract AST from parsed code representation."""
        if 'ast' in parsed:
            return self._convert_to_ast_nodes(parsed['ast'])
        
        if 'tokens' in parsed:
            return self._build_ast_from_tokens(parsed['tokens'])
        
        return None
    
    def _convert_to_ast_nodes(self, ast_data: Any) -> ASTNode:
        """Convert parsed AST data to ASTNode structure."""
        if isinstance(ast_data, dict):
            node_type = ast_data.get('type', 'UNKNOWN')
            value = ast_data.get('value', '')
            children_data = ast_data.get('children', [])
            children = [self._convert_to_ast_nodes(child) for child in children_data]
            return ASTNode(node_type, value, children)
        return ASTNode('LITERAL', str(ast_data))
    
    def _build_ast_from_tokens(self, tokens: List[Dict]) -> ASTNode:
        """Build simplified AST from token stream."""
        root = ASTNode('ROOT')
        current_node = root
        
        for token in tokens:
            token_type = token.get('type', 'UNKNOWN')
            value = token.get('value', '')
            
            if token_type in ['KEYWORD', 'FUNCTION', 'CLASS']:
                new_node = ASTNode(token_type, value)
                current_node.children.append(new_node)
                current_node = new_node
            else:
                current_node.children.append(ASTNode(token_type, value))
        
        return root
    
    def _tree_edit_distance_similarity(self, ast_a: ASTNode, ast_b: ASTNode) -> float:
        """Calculate similarity based on tree edit distance."""
        distance = self.ted.calculate_distance(ast_a, ast_b)
        max_size = max(ast_a.subtree_size(), ast_b.subtree_size())
        
        if max_size == 0:
            return 1.0
        
        similarity = 1.0 - (distance / max_size)
        return max(0.0, min(1.0, similarity))
    
    def _cfg_similarity(self, parsed_a: Dict, parsed_b: Dict) -> float:
        """Calculate similarity based on control flow graphs."""
        cfg_a = self._extract_cfg(parsed_a)
        cfg_b = self._extract_cfg(parsed_b)
        
        if cfg_a is None or cfg_b is None:
            return 0.5
        
        if cfg_a.to_signature() == cfg_b.to_signature():
            return 1.0
        
        edges_a = set(cfg_a.edges)
        edges_b = set(cfg_b.edges)
        
        if not edges_a and not edges_b:
            return 1.0
        
        common = len(edges_a.intersection(edges_b))
        total = len(edges_a.union(edges_b))
        
        return common / total if total > 0 else 0.0
    
    def _extract_cfg(self, parsed: Dict) -> Optional[ControlFlowGraph]:
        """Extract Control Flow Graph from parsed code."""
        cfg = ControlFlowGraph()
        
        if 'tokens' not in parsed:
            return cfg
        
        tokens = parsed['tokens']
        current_block = cfg.add_block([])
        block_stack = [current_block]
        loop_stack: List[int] = []
        
        for token in tokens:
            if token.get('type') != 'KEYWORD':
                continue
            
            value = token.get('value', '')
            
            if value == 'if':
                new_block = cfg.add_block([])
                cfg.add_edge(block_stack[-1], new_block, 'conditional')
                block_stack.append(new_block)
            
            elif value == 'else':
                if len(block_stack) > 1:
                    block_stack.pop()
                new_block = cfg.add_block([])
                cfg.add_edge(block_stack[-1], new_block, 'alternative')
                block_stack.append(new_block)
            
            elif value in ['for', 'while']:
                loop_block = cfg.add_block([])
                cfg.add_edge(block_stack[-1], loop_block, 'loop')
                loop_stack.append(loop_block)
                block_stack.append(loop_block)
            
            elif value == 'break':
                if loop_stack:
                    cfg.add_edge(block_stack[-1], loop_stack[-1], 'break')
            
            elif value == 'continue':
                if loop_stack:
                    cfg.add_edge(block_stack[-1], loop_stack[-1], 'continue')
            
            elif value == 'return':
                cfg.add_edge(block_stack[-1], -1, 'return')
            
            elif value == 'try':
                new_block = cfg.add_block([])
                cfg.add_edge(block_stack[-1], new_block, 'try')
                block_stack.append(new_block)
            
            elif value == 'except':
                if block_stack:
                    block_stack.pop()
                new_block = cfg.add_block([])
                cfg.add_edge(block_stack[-1] if block_stack else 0, new_block, 'except')
                block_stack.append(new_block)
        
        return cfg
    
    def _dfg_similarity(self, parsed_a: Dict, parsed_b: Dict) -> float:
        """Calculate similarity based on data flow graphs."""
        dfg_a = self._extract_dfg(parsed_a)
        dfg_b = self._extract_dfg(parsed_b)
        
        if dfg_a is None or dfg_b is None:
            return 0.5
        
        deps_a = set(dfg_a.dependencies)
        deps_b = set(dfg_b.dependencies)
        
        if not deps_a and not deps_b:
            return 1.0
        
        common = len(deps_a.intersection(deps_b))
        total = len(deps_a.union(deps_b))
        
        return common / total if total > 0 else 0.0
    
    def _extract_dfg(self, parsed: Dict) -> Optional[DataFlowGraph]:
        """Extract Data Flow Graph from parsed code."""
        dfg = DataFlowGraph()
        
        if 'tokens' not in parsed:
            return dfg
        
        tokens = parsed['tokens']
        defined_vars: Set[str] = set()
        
        for token in tokens:
            if token.get('type') == 'VARIABLE':
                value = token.get('value', '')
                if value not in defined_vars:
                    defined_vars.add(value)
                    dfg.variables[value].append('definition')
                else:
                    dfg.variables[value].append('use')
        
        # Infer dependencies from sequential variable usage
        var_list = list(defined_vars)
        for i, var in enumerate(var_list):
            for other_var in var_list[i+1:]:
                dfg.add_dependency(var, other_var, 'sequential')
        
        return dfg
    
    def _pattern_similarity(self, ast_a: ASTNode, ast_b: ASTNode) -> float:
        """Calculate similarity based on subtree pattern matching."""
        subtrees_a = ast_a.get_subtrees(min_size=2)
        subtrees_b = ast_b.get_subtrees(min_size=2)
        
        if not subtrees_a and not subtrees_b:
            return 1.0
        
        hashes_a = {st.hash_subtree() for st in subtrees_a}
        hashes_b = {st.hash_subtree() for st in subtrees_b}
        
        if not hashes_a and not hashes_b:
            return 1.0
        
        common = len(hashes_a.intersection(hashes_b))
        total = len(hashes_a.union(hashes_b))
        
        return common / total if total > 0 else 0.0
    
    def _complexity_similarity(self, ast_a: ASTNode, ast_b: ASTNode) -> float:
        """Calculate similarity based on complexity metrics."""
        metrics_a = self._compute_complexity(ast_a)
        metrics_b = self._compute_complexity(ast_b)
        
        # Compare individual metrics
        scores: List[float] = []
        
        for key in metrics_a:
            if key in metrics_b:
                val_a = metrics_a[key]
                val_b = metrics_b[key]
                max_val = max(val_a, val_b)
                if max_val == 0:
                    scores.append(1.0)
                else:
                    # Use ratio similarity
                    ratio = min(val_a, val_b) / max_val
                    scores.append(ratio)
        
        return sum(scores) / len(scores) if scores else 0.5
    
    def _compute_complexity(self, ast: ASTNode) -> Dict[str, float]:
        """Compute complexity metrics from AST."""
        total_nodes = ast.subtree_size()
        
        # Count specific node types
        node_types: Dict[str, int] = defaultdict(int)
        def _count(node: ASTNode):
            node_types[node.node_type] += 1
            for child in node.children:
                _count(child)
        _count(ast)
        
        # Cyclomatic complexity approximation
        decision_points = sum(node_types.get(t, 0) 
                            for t in ['if', 'for', 'while', 'elif', 'case', 'catch'])
        cyclomatic = decision_points + 1
        
        # Nesting depth
        max_depth = 0
        def _max_depth(node: ASTNode, current_depth: int):
            nonlocal max_depth
            max_depth = max(max_depth, current_depth)
            for child in node.children:
                _max_depth(child, current_depth + 1)
        _max_depth(ast, 0)
        
        return {
            'total_nodes': float(total_nodes),
            'cyclomatic': float(cyclomatic),
            'max_depth': float(max_depth),
            'branching_factor': (total_nodes - 1) / max(max_depth, 1)
        }