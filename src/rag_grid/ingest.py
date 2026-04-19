"""Document ingestion: load and chunk markdown/txt files with metadata."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from pathlib import Path

from rag_grid.config import config
from rag_grid.schema import Chunk

logger = logging.getLogger(__name__)


# ── Text splitting ─────────────────────────────────────────────────────────────


def _split_words(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Split *text* into overlapping word-count windows.

    Args:
        text:       Source text.
        chunk_size: Maximum words per chunk.
        overlap:    Words shared between consecutive chunks.

    Returns:
        List of text chunks (may be shorter than *chunk_size* for the last one).
    """
    words = text.split()
    if not words:
        return []
    chunks: list[str] = []
    step = max(1, chunk_size - overlap)
    for i in range(0, len(words), step):
        chunk = " ".join(words[i : i + chunk_size])
        if chunk:
            chunks.append(chunk)
    return chunks


# ── Section extraction ─────────────────────────────────────────────────────────


def _extract_sections(text: str) -> list[tuple[str, str]]:
    """Split a markdown document into (heading, body) pairs.

    Headings are detected via ``# …``, ``## …``, or ``### …`` prefixes.
    Text before the first heading is grouped under "Introduction".

    Returns:
        List of (heading, content) 2-tuples, content possibly empty.
    """
    sections: list[tuple[str, str]] = []
    current_heading = "Introduction"
    current_lines: list[str] = []

    for line in text.splitlines():
        m = re.match(r"^#{1,4}\s+(.+)", line)
        if m:
            if current_lines:
                sections.append((current_heading, "\n".join(current_lines).strip()))
            current_heading = m.group(1).strip()
            current_lines = []
        else:
            current_lines.append(line)

    if current_lines:
        sections.append((current_heading, "\n".join(current_lines).strip()))

    return sections


# ── Per-file ingestion ─────────────────────────────────────────────────────────


def ingest_file(
    path: Path,
    chunk_size: int | None = None,
    overlap: int | None = None,
) -> list[Chunk]:
    """Load *path* and return a list of :class:`Chunk` objects.

    Args:
        path:       Path to a ``.md`` or ``.txt`` file.
        chunk_size: Word-count window size (defaults to ``config.chunk_size``).
        overlap:    Overlap in words (defaults to ``config.chunk_overlap``).

    Returns:
        Ordered list of chunks with provenance metadata.
    """
    chunk_size = chunk_size or config.chunk_size
    overlap = overlap or config.chunk_overlap

    text = path.read_text(encoding="utf-8")
    sections = _extract_sections(text)
    chunks: list[Chunk] = []

    for heading, body in sections:
        if not body.strip():
            continue
        sub_chunks = _split_words(body, chunk_size, overlap)
        for idx, chunk_text in enumerate(sub_chunks):
            raw_id = f"{path.name}:{heading}:{idx}"
            chunk_id = hashlib.md5(raw_id.encode()).hexdigest()[:8]
            chunks.append(
                Chunk(
                    chunk_id=chunk_id,
                    source=path.name,
                    section=heading,
                    text=chunk_text,
                )
            )

    logger.info("Ingested %d chunks from %s.", len(chunks), path.name)
    return chunks


# ── Directory ingestion ────────────────────────────────────────────────────────


def ingest_directory(docs_dir: Path) -> list[Chunk]:
    """Recursively ingest all ``.md`` and ``.txt`` files under *docs_dir*.

    Returns:
        Concatenated list of chunks from all files (sorted by filename).
    """
    all_chunks: list[Chunk] = []
    found = sorted(
        list(docs_dir.glob("*.md")) + list(docs_dir.glob("*.txt"))
    )
    if not found:
        logger.warning("No .md or .txt files found in %s.", docs_dir)
    for file_path in found:
        file_chunks = ingest_file(file_path)
        all_chunks.extend(file_chunks)
    logger.info("Total chunks ingested: %d from %d files.", len(all_chunks), len(found))
    return all_chunks


# ── Persistence helpers ────────────────────────────────────────────────────────


def save_chunks(chunks: list[Chunk], out_path: Path) -> None:
    """Serialise *chunks* to a JSON file."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump([c.model_dump() for c in chunks], fh, indent=2)
    logger.info("Saved %d chunks to %s.", len(chunks), out_path)


def load_chunks(path: Path) -> list[Chunk]:
    """Deserialise chunks from a JSON file written by :func:`save_chunks`."""
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    return [Chunk(**item) for item in data]
