"""
Recursive character text splitter with overlap.
Produces chunks with stable IDs derived from content hash.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

from core.config import get_settings


@dataclass
class Chunk:
    text: str
    chunk_id: str
    ticker: str
    filing_type: str
    period: str
    filed_at: str
    source_url: str
    chunk_index: int
    metadata: dict = field(default_factory=dict)


def _split_text(text: str, size: int, overlap: int) -> list[str]:
    """Recursive character splitter respecting paragraph boundaries."""
    separators = ["\n\n", "\n", ". ", " ", ""]

    def _split(text: str, separators: list[str]) -> list[str]:
        sep = separators[0]
        remaining_separators = separators[1:]

        if not sep:
            # Character-level split
            chunks = []
            for i in range(0, len(text), size - overlap):
                chunks.append(text[i : i + size])
            return chunks

        splits = re.split(re.escape(sep), text)
        chunks = []
        current = ""

        for split in splits:
            candidate = (current + sep + split).lstrip(sep) if current else split
            if len(candidate) <= size:
                current = candidate
            else:
                if current:
                    chunks.append(current)
                if len(split) > size and remaining_separators:
                    chunks.extend(_split(split, remaining_separators))
                else:
                    current = split

        if current:
            chunks.append(current)

        return chunks

    raw_chunks = _split(text, separators)

    # Apply overlap
    result = []
    for i, chunk in enumerate(raw_chunks):
        if i > 0 and overlap > 0:
            prev = raw_chunks[i - 1]
            overlap_text = prev[-overlap:]
            chunk = overlap_text + chunk
        result.append(chunk[:size])

    return result


def chunk_document(
    text: str,
    ticker: str,
    filing_type: str,
    period: str,
    filed_at: str,
    source_url: str,
    metadata: dict | None = None,
) -> list[Chunk]:
    settings = get_settings()
    raw_chunks = _split_text(text, settings.chunk_size, settings.chunk_overlap)
    chunks = []

    for i, chunk_text in enumerate(raw_chunks):
        chunk_text = chunk_text.strip()
        if len(chunk_text) < 50:
            continue

        chunk_hash = hashlib.sha256(
            f"{ticker}:{filing_type}:{period}:{i}:{chunk_text[:100]}".encode()
        ).hexdigest()[:16]

        chunks.append(
            Chunk(
                text=chunk_text,
                chunk_id=chunk_hash,
                ticker=ticker,
                filing_type=filing_type,
                period=period,
                filed_at=filed_at,
                source_url=source_url,
                chunk_index=i,
                metadata=metadata or {},
            )
        )

    return chunks
