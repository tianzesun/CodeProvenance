"""
JPlag-level 3-layer plagiarism detection pipeline.

Layer 1: MinHash LSH Indexing (fast filtering - eliminates 99% of pairs)
Layer 2: Hybrid Similarity Engine (AST + token fingerprints)
Layer 3: Optional alignment refinement
"""
import random
import ast
from collections import defaultdict, Counter
from typing import Dict, Set, Tuple, List, Any

from src.engines.similarity.token_similarity import TokenSimilarity
from src.engines.features.ast_normalizer import ASTNormalizer


class MinHash:
    """MinHash signature generation for set similarity estimation."""
    
    def __init__(self, num_perm: int = 64) -> None:
        self.num_perm = num_perm
        self.seeds = [random.randint(1, 10**9) for _ in range(num_perm)]
    
    def hash_set(self, items: Set[int]) -> Tuple[int, ...]:
        """Generate MinHash signature for a set of items."""
        signatures = [float('inf')] * self.num_perm
        
        for item in items:
            for i, seed in enumerate(self.seeds):
                h = hash((item, seed))
                if h < signatures[i]:
                    signatures[i] = h
        
        return tuple(signatures)


class LSHIndex:
    """Locality Sensitive Hashing index for fast candidate retrieval."""
    
    def __init__(self) -> None:
        self.buckets = defaultdict(list)
        self._feature_store: Dict[str, Any] = {}
    
    def add(self, file_id: str, signature: Tuple[int, ...], features: Any = None, bands: int = 8) -> None:
        """Add a file to the LSH index."""
        rows = len(signature) // bands
        
        for i in range(bands):
            band = signature[i*rows:(i+1)*rows]
            self.buckets[hash(band)].append(file_id)
        
        if features is not None:
            self._feature_store[file_id] = features
    
    def query(self, signature: Tuple[int, ...], bands: int = 8) -> Set[str]:
        """Query for candidate files similar to the given signature."""
        rows = len(signature) // bands
        candidates = set()
        
        for i in range(bands):
            band = signature[i*rows:(i+1)*rows]
            candidates.update(self.buckets.get(hash(band), []))
        
        return candidates
    
    def get_features(self, file_id: str) -> Any:
        """Get stored features for a file ID."""
        return self._feature_store.get(file_id)


class UnifiedFeatureExtractor:
    """Extracts both AST and token fingerprints from source code."""
    
    def __init__(self, min_subtree_size: int = 3, ast_window: int = 5, token_window: int = 4) -> None:
        self.min_subtree_size = min_subtree_size
        self.ast_window = ast_window
        self.token_window = token_window
        self.ast_normalizer = ASTNormalizer()
        self.token_sim = TokenSimilarity()
    
    def _hash_node(self, node: ast.AST, memo: Dict[int, Tuple[int, int]] = None) -> Tuple[int, int]:
        """Bottom-up subtree hashing with memoization."""
        if memo is None:
            memo = {}
        
        node_id = id(node)
        if node_id in memo:
            return memo[node_id]
        
        child_hashes = []
        size = 1
        
        for child in ast.iter_child_nodes(node):
            h, s = self._hash_node(child, memo)
            child_hashes.append(h)
            size += s
        
        node_type = type(node).__name__
        
        if isinstance(node, ast.Constant):
            value = ("CONST", type(node.value).__name__)
        elif isinstance(node, ast.Name):
            value = ("NAME", node.id)
        else:
            value = ()
        
        subtree_hash = hash((node_type, value, tuple(child_hashes)))
        result = (subtree_hash, size)
        memo[node_id] = result
        return result
    
    def _collect_hash_sequence(self, node: ast.AST) -> List[int]:
        """Collect subtree hashes in pre-order traversal."""
        sequence = []
        
        def dfs(n: ast.AST) -> None:
            h, size = self._hash_node(n)
            if size >= self.min_subtree_size:
                sequence.append(h)
            for c in ast.iter_child_nodes(n):
                dfs(c)
        
        dfs(node)
        return sequence
    
    def _winnow(self, hashes: List[int], window_size: int) -> Set[int]:
        """Winnowing algorithm to select representative fingerprints."""
        if len(hashes) < window_size:
            return set(hashes)
        
        fingerprints = set()
        min_idx = -1
        
        for i in range(len(hashes) - window_size + 1):
            if min_idx < i:
                window = hashes[i:i + window_size]
                min_val = min(window)
                min_idx = i + window.index(min_val)
            else:
                new_val = hashes[i + window_size - 1]
                if new_val <= hashes[min_idx]:
                    min_val = new_val
                    min_idx = i + window_size - 1
                else:
                    min_val = hashes[min_idx]
            
            fingerprints.add(min_val)
        
        return fingerprints
    
    def extract_ast_fingerprints(self, code: str) -> Set[int]:
        """Extract winnowed AST subtree fingerprints."""
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return set()
        
        # Normalize identifiers
        class Normalizer(ast.NodeTransformer):
            def __init__(self):
                self.var_map = {}
                self.func_map = {}
                self.var_counter = 0
                self.func_counter = 0
            
            def _get_var(self, name):
                if name not in self.var_map:
                    self.var_counter += 1
                    self.var_map[name] = f"VAR_{self.var_counter}"
                return self.var_map[name]
            
            def visit_Name(self, node):
                return ast.copy_location(
                    ast.Name(id=self._get_var(node.id), ctx=node.ctx),
                    node
                )
            
            def visit_FunctionDef(self, node):
                if node.name not in self.func_map:
                    self.func_counter += 1
                    self.func_map[node.name] = f"FUNC_{self.func_counter}"
                node.name = self.func_map[node.name]
                self.generic_visit(node)
                return node
            
            def visit_arg(self, node):
                node.arg = self._get_var(node.arg)
                return node
        
        norm = Normalizer()
        tree = norm.visit(tree)
        ast.fix_missing_locations(tree)
        
        seq = self._collect_hash_sequence(tree)
        return self._winnow(seq, self.ast_window)
    
    def extract_token_fingerprints(self, code: str) -> Set[int]:
        """Extract winnowed normalized token fingerprints."""
        tokens = self.token_sim._extract_tokens({"raw": code})
        norm_tokens = self.token_sim._normalize_identifiers(tokens)
        
        # Generate k-gram hashes
        k = 5
        kgram_hashes = []
        for i in range(len(norm_tokens) - k + 1):
            kgram = tuple(norm_tokens[i:i+k])
            kgram_hashes.append(hash(kgram))
        
        return self._winnow(kgram_hashes, self.token_window)
    
    def extract_features(self, code: str) -> Dict[str, Set[int]]:
        """Extract unified feature set: AST + token fingerprints."""
        return {
            "ast": self.extract_ast_fingerprints(code),
            "tok": self.extract_token_fingerprints(code),
        }


def jaccard_set(a: Set[int], b: Set[int]) -> float:
    """Jaccard similarity between two sets."""
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def hybrid_similarity(featA: Dict[str, Set[int]], featB: Dict[str, Set[int]]) -> float:
    """Hybrid similarity score combining AST and token fingerprints."""
    ast_sim = jaccard_set(featA["ast"], featB["ast"])
    tok_sim = jaccard_set(featA["tok"], featB["tok"])
    
    score = 0.60 * ast_sim + 0.40 * tok_sim
    
    # JPlag-style confidence boost
    if ast_sim > 0.85:
        score = max(score, 0.92)
    
    # Penalize strong disagreement between signals
    if abs(ast_sim - tok_sim) > 0.5:
        score *= 0.9
    
    return min(1.0, max(0.0, score))


class PlagiarismEngine:
    """Production-grade 3-layer plagiarism detection engine."""
    
    def __init__(self, num_perm: int = 64) -> None:
        self.minhash = MinHash(num_perm=num_perm)
        self.lsh = LSHIndex()
        self.feature_extractor = UnifiedFeatureExtractor()
        self._files: Dict[str, str] = {}
    
    def index_file(self, file_id: str, code: str) -> Tuple[Dict[str, Set[int]], Tuple[int, ...]]:
        """Index a single file into the system."""
        feats = self.feature_extractor.extract_features(code)
        all_features = feats["ast"] | feats["tok"]
        signature = self.minhash.hash_set(all_features)
        
        self.lsh.add(file_id, signature, feats)
        self._files[file_id] = code
        
        return feats, signature
    
    def query_file(self, file_id: str, code: str = None) -> List[Tuple[str, float]]:
        """Query for similar files, returns sorted list of (file_id, score)."""
        if code is None:
            code = self._files.get(file_id, "")
        
        feats = self.feature_extractor.extract_features(code)
        all_features = feats["ast"] | feats["tok"]
        signature = self.minhash.hash_set(all_features)
        
        candidates = self.lsh.query(signature)
        candidates.discard(file_id)  # Remove self
        
        results = []
        for cid in candidates:
            cfeats = self.lsh.get_features(cid)
            if cfeats is None:
                continue
            
            score = hybrid_similarity(feats, cfeats)
            if score > 0.3:  # Minimum threshold
                results.append((cid, score))
        
        return sorted(results, key=lambda x: x[1], reverse=True)
    
    def batch_index(self, files: List[Tuple[str, str]], num_workers: int = 8) -> None:
        """Batch index multiple files (uses multiprocessing for speed)."""
        from multiprocessing import Pool
        
        def process_task(args: Tuple[str, str]) -> Tuple[str, Dict[str, Set[int]], Tuple[int, ...]]:
            fid, code = args
            feats = self.feature_extractor.extract_features(code)
            all_features = feats["ast"] | feats["tok"]
            sig = self.minhash.hash_set(all_features)
            return fid, feats, sig
        
        with Pool(num_workers) as p:
            results = p.map(process_task, files)
        
        for fid, feats, sig in results:
            self.lsh.add(fid, sig, feats)
            self._files[fid] = files[[f for f, _ in files].index(fid)][1]
