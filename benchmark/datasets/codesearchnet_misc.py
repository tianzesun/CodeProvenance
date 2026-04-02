"""
CodeSearchNet Dataset Loader (Multi-language subset).

Loads CodeSearchNet multi-language functions (JavaScript, Go, PHP, Ruby).
Contains 1,016,504 functions across 4 languages.

Reference: https://huggingface.co/datasets/code_search_net
"""
from typing import Dict, List, Any, Optional
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class CodeSearchNetMiscSample:
    """A multi-language code sample from CodeSearchNet."""
    id: str
    code: str
    docstring: str
    language: str  # javascript, go, php, ruby
    func_name: str = ""
    split: str = "train"


class CodeSearchNetMiscDataset:
    """
    Loads CodeSearchNet multi-language dataset.
    
    Dataset structure:
        codesearchnet_misc/
        └── huggingface/
            ├── javascript/
            │   ├── train/
            │   ├── test/
            │   └── validation/
            ├── go/
            ├── php/
            └── ruby/
    """
    
    # Language breakdown from manifest
    LANGUAGE_COUNTS = {
        "javascript": 123889,
        "go": 317832,
        "php": 523712,
        "ruby": 48791,
    }
    
    def __init__(self, data_dir: Path = Path("benchmark/data/codesearchnet_misc")):
        self.data_dir = data_dir
        self.hf_dir = data_dir / "huggingface"
        self._samples: List[CodeSearchNetMiscSample] = []
        self._dataset = None
    
    def load(
        self,
        language: Optional[str] = None,
        split: str = "train",
        max_samples: Optional[int] = None
    ) -> List[CodeSearchNetMiscSample]:
        """
        Load CodeSearchNet samples from HuggingFace Arrow format.
        
        Args:
            language: Specific language to load ('javascript', 'go', 'php', 'ruby')
                     If None, loads from first available language
            split: Dataset split ('train', 'test', 'validation')
            max_samples: Maximum number of samples to load
            
        Returns:
            List of CodeSearchNetMiscSample objects
        """
        try:
            from datasets import load_from_disk
        except ImportError:
            raise ImportError(
                "datasets library required. Install with: pip install datasets"
            )
        
        # Determine which language to load
        if language is None:
            available_langs = self._get_available_languages()
            if not available_langs:
                raise FileNotFoundError(
                    f"No language datasets found at {self.hf_dir}"
                )
            language = available_langs[0]
        
        lang_dir = self.hf_dir / language
        if not lang_dir.exists():
            raise FileNotFoundError(
                f"Language '{language}' not found at {lang_dir}. "
                f"Available languages: {self._get_available_languages()}"
            )
        
        split_dir = lang_dir / split
        if not split_dir.exists():
            raise FileNotFoundError(
                f"Split '{split}' not found for language '{language}'. "
                f"Available splits: {self._get_available_splits(language)}"
            )
        
        # Load dataset from disk
        dataset = load_from_disk(str(split_dir))
        self._dataset = dataset
        
        # Convert to our format
        samples = []
        for i, item in enumerate(dataset):
            if max_samples and i >= max_samples:
                break
            
            sample = CodeSearchNetMiscSample(
                id=f"{language}_{split}_{i}",
                code=item.get("func_code_string", ""),
                docstring=item.get("func_documentation_string", ""),
                language=language,
                func_name=item.get("func_name", ""),
                split=split,
            )
            samples.append(sample)
        
        self._samples = samples
        return samples
    
    def _get_available_languages(self) -> List[str]:
        """Get available language directories."""
        if not self.hf_dir.exists():
            return []
        return [d.name for d in self.hf_dir.iterdir() if d.is_dir()]
    
    def _get_available_splits(self, language: str) -> List[str]:
        """Get available splits for a language."""
        lang_dir = self.hf_dir / language
        if not lang_dir.exists():
            return []
        return [d.name for d in lang_dir.iterdir() if d.is_dir()]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get dataset statistics."""
        stats = {
            "name": "CodeSearchNet (Multi-language)",
            "languages": list(self.LANGUAGE_COUNTS.keys()),
            "language_counts": self.LANGUAGE_COUNTS,
            "total_functions": sum(self.LANGUAGE_COUNTS.values()),
            "huggingface_dir": str(self.hf_dir),
            "available_languages": self._get_available_languages(),
            "samples_loaded": len(self._samples),
        }
        
        if self._samples:
            stats["avg_code_length"] = sum(len(s.code) for s in self._samples) / len(self._samples)
            stats["avg_docstring_length"] = sum(len(s.docstring) for s in self._samples) / len(self._samples)
            stats["languages_loaded"] = list(set(s.language for s in self._samples))
        
        return stats
    
    def check_availability(self) -> Dict[str, bool]:
        """Check dataset availability."""
        available_langs = self._get_available_languages()
        return {
            "data_dir": self.data_dir.exists(),
            "huggingface_dir": self.hf_dir.exists(),
            "javascript": "javascript" in available_langs,
            "go": "go" in available_langs,
            "php": "php" in available_langs,
            "ruby": "ruby" in available_langs,
        }