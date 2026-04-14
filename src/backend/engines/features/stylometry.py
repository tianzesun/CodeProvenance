import ast
import re
from typing import Dict, List, Any, Optional
from collections import Counter
import numpy as np

class StylometryExtractor:
    """
    Extracts code style features (stylometry) to distinguish between 
    different authors. Features include:
    - Variable naming habits (snake_case vs camelCase)
    - Comment styles and density
    - Function length distributions
    - Use of specific language features (list comprehensions, decorators)
    - White space usage (tabs vs spaces, indentation level)
    """
    
    def extract(self, code: str) -> Dict[str, Any]:
        features = {}
        
        try:
            tree = ast.parse(code)
            features.update(self._extract_ast_stylometry(tree))
        except SyntaxError:
            # Fallback for non-parseable code
            pass
            
        features.update(self._extract_regex_stylometry(code))
        return features

    def _extract_ast_stylometry(self, tree: ast.AST) -> Dict[str, Any]:
        stats = {
            'var_naming': [],
            'func_lengths': [],
            'comp_count': 0, # comprehensions
            'decorator_count': 0,
            'lambda_count': 0
        }
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                stats['var_naming'].append(node.id)
            elif isinstance(node, ast.FunctionDef):
                length = (node.end_lineno - node.lineno) if hasattr(node, 'end_lineno') else 0
                stats['func_lengths'].append(length)
                stats['decorator_count'] += len(node.decorator_list)
            elif isinstance(node, (ast.ListComp, ast.DictComp, ast.SetComp, ast.GeneratorExp)):
                stats['comp_count'] += 1
            elif isinstance(node, ast.Lambda):
                stats['lambda_count'] += 1
                
        # Aggregate features
        features = {
            'avg_func_length': np.mean(stats['func_lengths']) if stats['func_lengths'] else 0,
            'max_func_length': np.max(stats['func_lengths']) if stats['func_lengths'] else 0,
            'comprehension_density': stats['comp_count'],
            'decorator_density': stats['decorator_count'],
            'lambda_density': stats['lambda_count'],
        }
        
        # Naming style
        if stats['var_naming']:
            is_snake = sum(1 for v in stats['var_naming'] if '_' in v)
            is_camel = sum(1 for v in stats['var_naming'] if any(c.isupper() for c in v) and '_' not in v)
            features['snake_case_ratio'] = is_snake / len(stats['var_naming'])
            features['camel_case_ratio'] = is_camel / len(stats['var_naming'])
        else:
            features['snake_case_ratio'] = 0.5
            features['camel_case_ratio'] = 0.5
            
        return features

    def _extract_regex_stylometry(self, code: str) -> Dict[str, Any]:
        lines = code.splitlines()
        if not lines:
            return {}
            
        # Comment density
        comment_lines = sum(1 for line in lines if line.strip().startswith('#'))
        
        # Indentation
        tabs = sum(1 for line in lines if line.startswith('\t'))
        spaces = sum(1 for line in lines if line.startswith('    '))
        
        # Docstrings
        docstrings = len(re.findall(r'""".*?"""|\'\'\'.*?\'\'\'', code, re.DOTALL))
        
        return {
            'comment_density': comment_lines / len(lines),
            'tab_usage_ratio': tabs / (tabs + spaces + 1e-9),
            'docstring_count': docstrings,
            'avg_line_length': np.mean([len(l) for l in lines])
        }

def compare_stylometry(feat_a: Dict[str, Any], feat_b: Dict[str, Any]) -> float:
    """Compares two stylometry feature sets and returns a similarity score."""
    keys = set(feat_a.keys()).intersection(feat_b.keys())
    if not keys:
        return 0.5
        
    diffs = []
    for k in keys:
        val_a = feat_a[k]
        val_b = feat_b[k]
        max_val = max(abs(val_a), abs(val_b), 1e-9)
        diffs.append(1.0 - abs(val_a - val_b) / max_val)
        
    return np.mean(diffs)
