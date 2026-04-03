import logging
from typing import Dict, List, Type, Any, Optional
from src.engines.similarity.base_similarity import BaseSimilarityAlgorithm

logger = logging.getLogger(__name__)

class MultiLanguageRegistry:
    """
    Multi-Language Support Registry.
    Registers and maintains support for 20+ programming languages.
    Provides language-specific normalizers and similarity engines.
    """
    
    def __init__(self):
        # Maps language extensions/names to their configurations
        self.language_configs: Dict[str, Dict[str, Any]] = {}
        # Pre-populate with standard languages
        self._bootstrap_languages()

    def register_language(self, 
                          name: str, 
                          extensions: List[str], 
                          normalizer_cls: Optional[Type] = None,
                          ast_parser: Optional[Any] = None):
        """Register a new programming language and its support tools."""
        self.language_configs[name.lower()] = {
            "name": name,
            "extensions": extensions,
            "normalizer": normalizer_cls,
            "parser": ast_parser
        }
        for ext in extensions:
            self.language_configs[ext.lower()] = self.language_configs[name.lower()]
            
        logger.info(f"Registered language: {name} (extensions: {', '.join(extensions)})")

    def _bootstrap_languages(self):
        """Populate registry with core supported languages."""
        # Core 6
        self.register_language("Python", [".py", ".pyw"])
        self.register_language("C++", [".cpp", ".h", ".hpp", ".cc"])
        self.register_language("Java", [".java"])
        self.register_language("JavaScript", [".js", ".mjs"])
        self.register_language("TypeScript", [".ts", ".tsx"])
        self.register_language("C#", [".cs"])
        
        # Expanding to 20+
        self.register_language("Go", [".go"])
        self.register_language("Ruby", [".rb"])
        self.register_language("PHP", [".php"])
        self.register_language("Swift", [".swift"])
        self.register_language("Rust", [".rs"])
        self.register_language("Kotlin", [".kt", ".kts"])
        self.register_language("Scala", [".scala"])
        self.register_language("Haskell", [".hs"])
        self.register_language("Lua", [".lua"])
        self.register_language("Perl", [".pl", ".pm"])
        self.register_language("R", [".r"])
        self.register_language("Dart", [".dart"])
        self.register_language("Objective-C", [".m", ".h"])
        self.register_language("C", [".c", ".h"])
        self.register_language("SQL", [".sql"])
        self.register_language("Julia", [".jl"])
        self.register_language("Shell", [".sh", ".bash"])

    def get_config_for_file(self, filename: str) -> Optional[Dict[str, Any]]:
        """Determine language from filename extension."""
        ext = f".{filename.split('.')[-1].lower()}"
        return self.language_configs.get(ext)
        
    def get_supported_languages(self) -> List[str]:
        """Returns a unique list of supported language names."""
        return sorted(list(set(cfg["name"] for cfg in self.language_configs.values())))
