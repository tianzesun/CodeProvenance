"""AST Token Extractor - Extract tokens with precise character spans from source code.

Uses tree-sitter for accurate AST parsing with byte-level offsets.
Falls back to regex-based extraction when tree-sitter is unavailable.
"""
import re
import logging
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


class ASTTokenExtractor:
    """Extract AST nodes with precise character/span offsets from source code.
    
    This extractor works in two modes:
    1. tree-sitter mode: Uses tree-sitter for accurate AST parsing with byte offsets
    2. Fallback mode: Uses regex-based heuristics for basic token extraction
    
    Attributes:
        language: Programming language for parsing
        use_tree_sitter: Whether to use tree-sitter (auto-detected)
    """
    
    # Language detection patterns
    LANGUAGE_PATTERNS: Dict[str, List[str]] = {
        "python": [r"\bdef\s+\w+", r"\bclass\s+\w+", r"\bimport\s+\w+"],
        "javascript": [r"\bfunction\s+\w+", r"\bconst\s+\w+\s*=", r"\blet\s+\w+\s*="],
        "java": [r"\bpublic\s+class\s+\w+", r"\bprivate\s+\w+\s+\w+", r"\bvoid\s+\w+"],
        "cpp": [r"\b#include\s*", r"\bint\s+main\s*\(", r"\bstd::"],
    }
    
    # Token patterns for fallback mode
    FALLBACK_TOKEN_PATTERN = re.compile(
        r"(?P<identifier>[a-zA-Z_]\w*)|"
        r"(?P<number>\d+\.?\d*)|"
        r"(?P<string>'[^']*'|\"[^\"]*\"|```[^`]*```)|"
        r"(?P<comment>#[^\n]*|//[^\n]*|/\*[\s\S]*?\*/)|"
        r"(?P<keyword>\b(def|class|import|from|return|if|else|elif|for|while|"
        r"try|except|finally|with|as|yield|lambda|pass|break|continue|raise|"
        r"function|const|let|var|var|new|delete|typeof|instanceof|void|"
        r"public|private|protected|static|final|abstract|interface|extends|implements|"
        r"int|float|double|char|bool|boolean|string|void|"
        r"true|false|null|None|True|False|undefined|NaN|Infinity)\b)|"
        r"(?P<operator>[+\-*/%]=?|==|!=|<=|>=|&&|\|\||!|&|\||\^|~|<<|>>|\*\*)|"
        r"(?P<punctuation>[(){}\[\],;.:])"
    )
    
    def __init__(self, language: str = "auto"):
        """Initialize extractor.
        
        Args:
            language: Programming language for parsing. Use 'auto' for auto-detection.
        """
        self.language = language
        self.use_tree_sitter = False
        self._parser = None
        self._try_load_tree_sitter()
    
    def _try_load_tree_sitter(self):
        """Attempt to load tree-sitter for accurate parsing."""
        try:
            import tree_sitter_languages
            self.use_tree_sitter = True
            logger.debug("tree-sitter available for accurate AST parsing")
        except ImportError:
            self.use_tree_sitter = False
            logger.debug("tree-sitter not available, using fallback mode")
    
    def detect_language(self, code: str) -> str:
        """Detect programming language from source code.
        
        Args:
            code: Source code string
            
        Returns:
            Detected language name
        """
        if self.language != "auto":
            return self.language
        
        for lang, patterns in self.LANGUAGE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, code):
                    return lang
        
        return "python"  # Default fallback
    
    def extract(self, code: str, language: str = "auto") -> List[Dict[str, Any]]:
        """Extract AST tokens with character spans from source code.
        
        Args:
            code: Source code to parse
            language: Programming language (auto-detected if 'auto')
            
        Returns:
            List of token dictionaries with keys:
                - type: Node type (e.g., 'function_definition', 'identifier')
                - start: Start byte offset (absolute character position)
                - end: End byte offset (exclusive)
                - start_line: Start line number (1-indexed)
                - end_line: End line number (1-indexed)
                - start_column: Start column (0-indexed)
                - end_column: End column (0-indexed)
                - text: Actual source text
        """
        if not code:
            return []
        
        lang = language if language != "auto" else self.detect_language(code)
        
        if self.use_tree_sitter:
            return self._extract_tree_sitter(code, lang)
        else:
            return self._extract_fallback(code, lang)
    
    def _extract_tree_sitter(self, code: str, language: str) -> List[Dict[str, Any]]:
        """Extract tokens using tree-sitter for accurate AST parsing.
        
        Args:
            code: Source code
            language: Programming language
            
        Returns:
            List of token dictionaries
        """
        try:
            import tree_sitter_languages
            parser = tree_sitter_languages.get_parser(language)
            tree = parser.parse(code.encode())
            
            tokens = []
            self._walk_tree(tree.root_node, code, tokens)
            return tokens
            
        except Exception as e:
            logger.warning(f"tree-sitter parsing failed for {language}: {e}")
            return self._extract_fallback(code, language)
    
    def _walk_tree(self, node, code: str, tokens: List[Dict[str, Any]]):
        """Recursively walk AST tree and extract tokens.
        
        Args:
            node: tree-sitter node
            code: Original source code
            tokens: List to append extracted tokens to
        """
        # Skip anonymous nodes (punctuation, etc.)
        if node.is_named:
            start_byte = node.start_byte
            end_byte = node.end_byte
            start_pos = node.start_point
            end_pos = node.end_point
            
            tokens.append({
                "type": node.type,
                "start": start_byte,
                "end": end_byte,
                "start_line": start_pos[0] + 1,  # 1-indexed
                "end_line": end_pos[0] + 1,
                "start_column": start_pos[1],
                "end_column": end_pos[1],
                "text": code[start_byte:end_byte],
                "is_named": True,
            })
        
        # Recurse into children
        for child in node.children:
            self._walk_tree(child, code, tokens)
    
    def _extract_fallback(self, code: str, language: str) -> List[Dict[str, Any]]:
        """Extract tokens using regex-based fallback.
        
        Provides basic token extraction when tree-sitter is unavailable.
        
        Args:
            code: Source code
            language: Programming language (for future language-specific rules)
            
        Returns:
            List of token dictionaries
        """
        tokens = []
        
        for match in self.FALLBACK_TOKEN_PATTERN.finditer(code):
            group_name = match.lastgroup
            if group_name:
                start = match.start()
                end = match.end()
                start_line = code[:start].count('\n') + 1
                end_line = code[:end].count('\n') + 1
                start_col = start - code.rfind('\n', 0, start) - 1
                end_col = end - code.rfind('\n', 0, end) - 1
                
                # Map to pseudo-AST type
                ast_type = self._token_type_to_ast_type(group_name)
                
                tokens.append({
                    "type": ast_type,
                    "start": start,
                    "end": end,
                    "start_line": start_line,
                    "end_line": end_line,
                    "start_column": start_col,
                    "end_column": end_col,
                    "text": match.group(),
                    "is_named": True,
                })
        
        return tokens
    
    def _token_type_to_ast_type(self, token_type: str) -> str:
        """Map token type to pseudo-AST node type.
        
        Args:
            token_type: Token category from regex
            
        Returns:
            Pseudo-AST node type name
        """
        mapping = {
            "identifier": "identifier",
            "number": "number_literal",
            "string": "string_literal",
            "comment": "comment",
            "keyword": "keyword",
            "operator": "operator",
            "punctuation": "punctuation",
        }
        return mapping.get(token_type, token_type)
    
    def extract_structures(self, code: str) -> List[Dict[str, Any]]:
        """Extract code structures (functions, classes) with their spans.
        
        Useful for AST-level similarity comparison.
        
        Args:
            code: Source code
            
        Returns:
            List of structure dictionaries with:
                - type: 'function' or 'class'
                - name: Structure name
                - start: Start character offset
                - end: End character offset
                - body: Complete source text
                - body_start: Start of body (after signature)
                - body_end: End of body
        """
        if self.use_tree_sitter:
            return self._extract_structures_tree_sitter(code)
        else:
            return self._extract_structures_fallback(code)
    
    def _extract_structures_tree_sitter(self, code: str) -> List[Dict[str, Any]]:
        """Extract structures using tree-sitter.
        
        Args:
            code: Source code
            
        Returns:
            List of structure dictionaries
        """
        lang = self.detect_language(code)
        try:
            import tree_sitter_languages
            parser = tree_sitter_languages.get_parser(lang)
            tree = parser.parse(code.encode())
            
            structures = []
            self._extract_structures_from_node(tree.root_node, code, structures)
            return structures
            
        except Exception as e:
            logger.warning(f"tree-sitter structure extraction failed: {e}")
            return self._extract_structures_fallback(code)
    
    def _extract_structures_from_node(self, node, code: str, structures: List[Dict]):
        """Recursively extract structures from AST node.
        
        Args:
            node: tree-sitter node
            code: Source code
            structures: List to append structures to
        """
        # Function definitions
        if node.type in ('function_definition', 'method_definition', 
                         'arrow_function', 'function_declaration'):
            name = self._get_function_name(node, code)
            structures.append({
                "type": "function",
                "name": name,
                "start": node.start_byte,
                "end": node.end_byte,
                "body": code[node.start_byte:node.end_byte],
            })
        
        # Class definitions
        elif node.type in ('class_definition', 'class_declaration'):
            name = self._get_class_name(node, code)
            structures.append({
                "type": "class",
                "name": name,
                "start": node.start_byte,
                "end": node.end_byte,
                "body": code[node.start_byte:node.end_byte],
            })
        
        # Recurse into children
        for child in node.children:
            self._extract_structures_from_node(child, code, structures)
    
    def _get_function_name(self, node, code: str) -> str:
        """Extract function name from AST node.
        
        Args:
            node: tree-sitter function node
            code: Source code
            
        Returns:
            Function name
        """
        for child in node.children:
            if child.type == 'identifier':
                return code[child.start_byte:child.end_byte]
        return ""
    
    def _get_class_name(self, node, code: str) -> str:
        """Extract class name from AST node.
        
        Args:
            node: tree-sitter class node
            code: Source code
            
        Returns:
            Class name
        """
        for child in node.children:
            if child.type == 'identifier':
                return code[child.start_byte:child.end_byte]
        return ""
    
    def _extract_structures_fallback(self, code: str) -> List[Dict[str, Any]]:
        """Extract structures using regex fallback.
        
        Args:
            code: Source code
            
        Returns:
            List of structure dictionaries
        """
        structures = []
        lines = code.split('\n')
        
        # Python patterns
        func_pattern = re.compile(r'^(def|async\s+def)\s+(\w+)\s*\(')
        class_pattern = re.compile(r'^class\s+(\w+)')
        
        i = 0
        while i < len(lines):
            line = lines[i]
            indent = len(line) - len(line.lstrip())
            
            match = func_pattern.match(line)
            if match:
                name = match.group(2)
                start_offset = sum(len(lines[j]) + 1 for j in range(i))
                end_offset = self._find_structure_end(lines, i, indent)
                structures.append({
                    "type": "function",
                    "name": name,
                    "start": start_offset,
                    "end": end_offset,
                    "body": code[start_offset:end_offset],
                })
                continue
            
            match = class_pattern.match(line)
            if match:
                name = match.group(1)
                start_offset = sum(len(lines[j]) + 1 for j in range(i))
                end_offset = self._find_structure_end(lines, i, indent)
                structures.append({
                    "type": "class",
                    "name": name,
                    "start": start_offset,
                    "end": end_offset,
                    "body": code[start_offset:end_offset],
                })
            
            i += 1
        
        return structures
    
    def _find_structure_end(self, lines: List[str], start: int, indent: int) -> int:
        """Find the end offset of a code structure.
        
        Args:
            lines: All source code lines
            start: Starting line index
            indent: Indentation level of structure definition
            
        Returns:
            Character offset of structure end
        """
        i = start + 1
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            
            # Skip empty lines and comments
            if not stripped or stripped.startswith('#'):
                i += 1
                continue
            
            # Check if indentation decreased (end of block)
            if len(line) - len(stripped) <= indent and stripped:
                break
            
            i += 1
        
        return sum(len(lines[j]) + 1 for j in range(i))