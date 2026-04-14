"""
Base Intermediate Representation (IR) classes.

Defines the abstract interface and metadata for all IR representations.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime
import hashlib
import json


@dataclass
class IRMetadata:
    """Metadata for any IR representation.
    
    Attributes:
        language: Programming language (e.g., 'python', 'java', 'javascript')
        source_hash: SHA-256 hash of original source code
        timestamp: When the IR was created
        representation_type: Type of IR ('ast', 'token', 'graph')
        file_path: Optional path to source file
        line_count: Number of lines in original source
        char_count: Number of characters in original source
    """
    language: str
    source_hash: str
    timestamp: str
    representation_type: str
    file_path: Optional[str] = None
    line_count: int = 0
    char_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize metadata to dictionary."""
        return {
            "language": self.language,
            "source_hash": self.source_hash,
            "timestamp": self.timestamp,
            "representation_type": self.representation_type,
            "file_path": self.file_path,
            "line_count": self.line_count,
            "char_count": self.char_count,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'IRMetadata':
        """Deserialize metadata from dictionary."""
        return cls(
            language=data["language"],
            source_hash=data["source_hash"],
            timestamp=data["timestamp"],
            representation_type=data["representation_type"],
            file_path=data.get("file_path"),
            line_count=data.get("line_count", 0),
            char_count=data.get("char_count", 0),
        )

    @classmethod
    def create_metadata(
        cls,
        source_code: str,
        language: str,
        representation_type: str,
        file_path: Optional[str] = None,
    ) -> "IRMetadata":
        """Create metadata directly from source code.

        Older callers construct metadata through ``IRMetadata.create_metadata``
        rather than ``BaseIR.create_metadata``. Keeping the helper here
        preserves that public API.
        """
        source_hash = hashlib.sha256(source_code.encode("utf-8")).hexdigest()
        line_count = len(source_code.split("\n"))
        char_count = len(source_code)
        timestamp = datetime.now().isoformat()

        return cls(
            language=language,
            source_hash=source_hash,
            timestamp=timestamp,
            representation_type=representation_type,
            file_path=file_path,
            line_count=line_count,
            char_count=char_count,
        )
    
    def validate(self) -> bool:
        """Validate metadata completeness."""
        required_fields = [
            self.language,
            self.source_hash,
            self.timestamp,
            self.representation_type,
        ]
        return all(field for field in required_fields)


class BaseIR(ABC):
    """Abstract base class for all intermediate representations.
    
    All IR implementations must provide:
    - Serialization to/from dictionary
    - Validation of IR integrity
    - Metadata tracking
    """
    
    def __init__(self, metadata: IRMetadata):
        """Initialize IR with metadata.
        
        Args:
            metadata: IR metadata containing language, hash, timestamp, etc.
        """
        self.metadata = metadata
    
    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """Serialize IR to dictionary format.
        
        Returns:
            Dictionary representation of the IR
        """
        pass
    
    @classmethod
    @abstractmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BaseIR':
        """Deserialize IR from dictionary format.
        
        Args:
            data: Dictionary containing IR data
            
        Returns:
            IR instance
        """
        pass
    
    @abstractmethod
    def validate(self) -> bool:
        """Validate IR integrity and completeness.
        
        Returns:
            True if IR is valid, False otherwise
        """
        pass
    
    @classmethod
    def create_metadata(
        cls,
        source_code: str,
        language: str,
        representation_type: str,
        file_path: Optional[str] = None
    ) -> IRMetadata:
        """Create metadata from source code.
        
        Args:
            source_code: Original source code
            language: Programming language
            representation_type: Type of IR ('ast', 'token', 'graph')
            file_path: Optional path to source file
            
        Returns:
            IRMetadata instance
        """
        return IRMetadata.create_metadata(
            source_code=source_code,
            language=language,
            representation_type=representation_type,
            file_path=file_path,
        )
    
    def save(self, filepath: str) -> None:
        """Save IR to JSON file.
        
        Args:
            filepath: Path to save the IR
        """
        data = {
            "metadata": self.metadata.to_dict(),
            "ir": self.to_dict(),
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    @classmethod
    def load(cls, filepath: str) -> 'BaseIR':
        """Load IR from JSON file.
        
        Args:
            filepath: Path to load the IR from
            
        Returns:
            IR instance
        """
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        metadata = IRMetadata.from_dict(data["metadata"])
        ir_data = data["ir"]
        
        # Create instance with metadata
        instance = cls.__new__(cls)
        instance.metadata = metadata
        
        # Load IR-specific data
        instance._load_from_dict(ir_data)
        
        return instance
    
    def _load_from_dict(self, data: Dict[str, Any]) -> None:
        """Load IR-specific data from dictionary.
        
        Subclasses should override this to load their specific data.
        
        Args:
            data: IR-specific data dictionary
        """
        pass
    
    def __repr__(self) -> str:
        """String representation of IR."""
        return f"{self.__class__.__name__}(language={self.metadata.language}, hash={self.metadata.source_hash[:8]}...)"
    
    def __eq__(self, other: object) -> bool:
        """Check equality based on source hash."""
        if not isinstance(other, BaseIR):
            return False
        return self.metadata.source_hash == other.metadata.source_hash
    
    def __hash__(self) -> int:
        """Hash based on source hash."""
        return hash(self.metadata.source_hash)
