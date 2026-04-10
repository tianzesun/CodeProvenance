"""Hash helpers with optional xxhash acceleration."""

from __future__ import annotations

import hashlib
from typing import Union

BytesLike = Union[bytes, bytearray, memoryview]

try:
    import xxhash as _xxhash  # type: ignore
except ImportError:  # pragma: no cover - exercised indirectly in smoke tests
    _xxhash = None


def fast_hash64(data: BytesLike | str) -> int:
    """Return a stable 64-bit hash, using xxhash when available."""
    if isinstance(data, str):
        payload = data.encode("utf-8")
    else:
        payload = bytes(data)

    if _xxhash is not None:
        return int(_xxhash.xxh3_64_intdigest(payload))

    digest = hashlib.blake2b(payload, digest_size=8).digest()
    return int.from_bytes(digest, byteorder="big", signed=False)
