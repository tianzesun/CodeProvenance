"""
Utils Module - Stateless Helper Functions Only

This module contains stateless, pure helper functions only.
It does NOT contain business logic or core primitives.

Responsibility: String manipulation, file I/O, date/time, formatting
"""

from typing import Any, Dict, List, Optional, Union
from pathlib import Path
import re
import json
from datetime import datetime, timedelta
import hashlib


# ============================================================================
# STRING UTILITIES
# ============================================================================

def slugify(text: str) -> str:
    """Convert text to URL-friendly slug."""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text


def truncate(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Truncate text to maximum length."""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def extract_keywords(text: str, min_length: int = 3) -> List[str]:
    """Extract keywords from text."""
    words = re.findall(r'\b\w+\b', text.lower())
    return [w for w in words if len(w) >= min_length]


def normalize_whitespace(text: str) -> str:
    """Normalize whitespace in text."""
    return ' '.join(text.split())


# ============================================================================
# FILE UTILITIES
# ============================================================================

def read_json(file_path: Union[str, Path]) -> Dict[str, Any]:
    """Read JSON file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def write_json(data: Dict[str, Any], file_path: Union[str, Path], indent: int = 2) -> None:
    """Write JSON file."""
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)


def read_text(file_path: Union[str, Path]) -> str:
    """Read text file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()


def write_text(text: str, file_path: Union[str, Path]) -> None:
    """Write text file."""
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(text)


def ensure_directory(dir_path: Union[str, Path]) -> Path:
    """Ensure directory exists."""
    path = Path(dir_path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_file_extension(file_path: Union[str, Path]) -> str:
    """Get file extension."""
    return Path(file_path).suffix


def get_file_name(file_path: Union[str, Path]) -> str:
    """Get file name without extension."""
    return Path(file_path).stem


# ============================================================================
# DATE/TIME UTILITIES
# ============================================================================

def format_datetime(dt: datetime, format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Format datetime to string."""
    return dt.strftime(format_str)


def parse_datetime(date_str: str, format_str: str = "%Y-%m-%d %H:%M:%S") -> datetime:
    """Parse datetime from string."""
    return datetime.strptime(date_str, format_str)


def get_current_timestamp() -> str:
    """Get current timestamp as string."""
    return format_datetime(datetime.now())


def add_days(date: datetime, days: int) -> datetime:
    """Add days to date."""
    return date + timedelta(days=days)


def days_between(date1: datetime, date2: datetime) -> int:
    """Calculate days between two dates."""
    return abs((date2 - date1).days)


# ============================================================================
# FORMATTING UTILITIES
# ============================================================================

def format_bytes(bytes_count: int) -> str:
    """Format bytes to human-readable string."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_count < 1024.0:
            return f"{bytes_count:.2f} {unit}"
        bytes_count /= 1024.0
    return f"{bytes_count:.2f} PB"


def format_duration(seconds: float) -> str:
    """Format duration to human-readable string."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"


def format_number(number: int) -> str:
    """Format number with commas."""
    return f"{number:,}"


def format_percentage(value: float, decimals: int = 2) -> str:
    """Format percentage."""
    return f"{value:.{decimals}%}"


# ============================================================================
# HASHING UTILITIES
# ============================================================================

def hash_string(text: str) -> str:
    """Hash string using SHA-256."""
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def hash_file(file_path: Union[str, Path]) -> str:
    """Hash file using SHA-256."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


# ============================================================================
# VALIDATION UTILITIES
# ============================================================================

def is_valid_email(email: str) -> bool:
    """Validate email format."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def is_valid_url(url: str) -> bool:
    """Validate URL format."""
    pattern = r'^https?://[^\s/$.?#].[^\s]*$'
    return bool(re.match(pattern, url))


def is_empty(value: Any) -> bool:
    """Check if value is empty."""
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, dict)):
        return len(value) == 0
    return False