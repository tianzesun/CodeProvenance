"""Token-based similarity using winnowing algorithm.

Implementation of winnowing for plagiarism detection.
"""
from typing import List, Set, Tuple


def tokenize(code: str) -> List[str]:
    """Tokenize source code into normalized tokens.
    
    Args:
        code: Source code string.
        
    Returns:
        List of lowercase, stripped tokens.
    """
    # Remove whitespace, comments, etc. (handled by normalizer)
    return code.lower().split()


def generate_ngrams(tokens: List[str], k: int = 6) -> List[Tuple[str, ...]]:
    """Generate k-grams from token list.
    
    Args:
        tokens: List of tokens.
        k: Size of each gram.
        
    Returns:
        List of k-gram tuples.
    """
    if len(tokens) < k:
        return [tuple(tokens)]
    return [tuple(tokens[i:i + k]) for i in range(len(tokens) - k + 1)]


def hash_grams(grams: List[Tuple[str, ...]]) -> List[int]:
    """Hash each n-gram.
    
    Args:
        grams: List of n-gram tuples.
        
    Returns:
        List of hash values.
    """
    return [hash(gram) for gram in grams]


def winnow(hashes: List[int], window_size: int = 4) -> List[int]:
    """Apply winnowing to reduce fingerprint size.
    
    Args:
        hashes: List of hash values.
        window_size: Size of sliding window.
        
    Returns:
        List of selected fingerprints (minimum of each window).
    """
    if len(hashes) <= window_size:
        return hashes
    
    selected = set()
    for i in range(len(hashes) - window_size + 1):
        window = hashes[i:i + window_size]
        min_hash = min(window)
        selected.add(min_hash)
    
    return list(selected)


def token_similarity(code1: str, code2: str, k: int = 6, 
                     window_size: int = 4) -> float:
    """Calculate token-based similarity using winnowing.
    
    Args:
        code1: First source code.
        code2: Second source code.
        k: N-gram size.
        window_size: Winnowing window size.
        
    Returns:
        Similarity score between 0.0 and 1.0.
    """
    tokens1 = tokenize(code1)
    tokens2 = tokenize(code2)
    
    grams1 = generate_ngrams(tokens1, k)
    grams2 = generate_ngrams(tokens2, k)
    
    hashes1 = hash_grams(grams1)
    hashes2 = hash_grams(grams2)
    
    fp1 = set(winnow(hashes1, window_size))
    fp2 = set(winnow(hashes2, window_size))
    
    if not fp1 or not fp2:
        return 0.0
    
    intersection = len(fp1 & fp2)
    union = len(fp1 | fp2)
    return intersection / union if union > 0 else 0.0