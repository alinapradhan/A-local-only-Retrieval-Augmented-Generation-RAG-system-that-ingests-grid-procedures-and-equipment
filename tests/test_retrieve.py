"""Unit tests for document ingestion and chunk retrieval."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from rag_grid.ingest import (
    _extract_sections,
    _split_words,
    ingest_file,
    ingest_directory,
    load_chunks,
    save_chunks,
)
from rag_grid.schema import Chunk


# ── _split_words ───────────────────────────────────────────────────────────────


def test_split_words_basic():
    text = " ".join(str(i) for i in range(20))  # "0 1 2 ... 19"
    chunks = _split_words(text, chunk_size=10, overlap=2)
    assert len(chunks) == 3  # [0-9], [8-17], [16-19]
    # First chunk has 10 words
    assert len(chunks[0].split()) == 10


def test_split_words_overlap():
    text = "a b c d e f g h i j"
    chunks = _split_words(text, chunk_size=5, overlap=2)
    # First chunk: a b c d e; step=3 → next: d e f g h; next: g h i j
    assert chunks[0].startswith("a b c d e")
    # Overlap: last word of chunk[0] appears in chunk[1]
    assert "e" in chunks[1]


def test_split_words_empty():
    assert _split_words("", chunk_size=10, overlap=2) == []


def test_split_words_shorter_than_chunk():
    text = "only three words"
    chunks = _split_words(text, chunk_size=10, overlap=2)
    assert len(chunks) == 1
    assert chunks[0] == "only three words"


# ── _extract_sections ──────────────────────────────────────────────────────────


def test_extract_sections_basic():
    md = "# Section A\nContent A\n## Section B\nContent B"
    sections = _extract_sections(md)
    headings = [h for h, _ in sections]
    assert "Section A" in headings
    assert "Section B" in headings


def test_extract_sections_no_heading():
    md = "Just a paragraph\nwith no heading."
    sections = _extract_sections(md)
    assert len(sections) == 1
    assert sections[0][0] == "Introduction"
    assert "Just a paragraph" in sections[0][1]


def test_extract_sections_empty_body():
    md = "# Heading\n\n## Another"
    sections = _extract_sections(md)
    # Heading section has empty body — it will be skipped during ingestion
    bodies = [body for _, body in sections]
    # At least one section found
    assert len(sections) >= 1


# ── ingest_file ────────────────────────────────────────────────────────────────


def test_ingest_file_returns_chunks(tmp_path):
    doc = tmp_path / "test.md"
    doc.write_text(
        "# Frequency Policy\n"
        "Maintain frequency within 59.5 to 60.5 Hz at all times.\n"
        "Operators must respond within 5 minutes.\n\n"
        "# Load Shedding\n"
        "Shed load in blocks of 100 MW maximum per interval.\n",
        encoding="utf-8",
    )
    chunks = ingest_file(doc)
    assert len(chunks) >= 2
    # Each chunk has required fields
    for chunk in chunks:
        assert chunk.chunk_id
        assert chunk.source == "test.md"
        assert chunk.section
        assert chunk.text


def test_ingest_file_chunk_ids_unique(tmp_path):
    doc = tmp_path / "policy.md"
    # Long enough to produce multiple chunks
    content = "# Section\n" + ("word " * 600)
    doc.write_text(content, encoding="utf-8")
    chunks = ingest_file(doc, chunk_size=100, overlap=10)
    ids = [c.chunk_id for c in chunks]
    assert len(ids) == len(set(ids)), "Chunk IDs must be unique"


def test_ingest_directory(tmp_path):
    (tmp_path / "a.md").write_text("# A\nContent of A.", encoding="utf-8")
    (tmp_path / "b.md").write_text("# B\nContent of B.", encoding="utf-8")
    (tmp_path / "ignore.py").write_text("# not a doc", encoding="utf-8")
    chunks = ingest_directory(tmp_path)
    sources = {c.source for c in chunks}
    assert "a.md" in sources
    assert "b.md" in sources
    assert "ignore.py" not in sources


# ── save_chunks / load_chunks ──────────────────────────────────────────────────


def test_round_trip_chunks(tmp_path):
    original = [
        Chunk(chunk_id="aa1", source="doc.md", section="Intro", text="hello world"),
        Chunk(chunk_id="bb2", source="doc.md", section="Policy", text="never exceed limits"),
    ]
    path = tmp_path / "chunks.json"
    save_chunks(original, path)
    loaded = load_chunks(path)
    assert len(loaded) == len(original)
    assert loaded[0].chunk_id == "aa1"
    assert loaded[1].text == "never exceed limits"


# ── retrieval smoke test (mock mode, no external calls) ───────────────────────


def test_retrieve_returns_relevant_chunks(tmp_path):
    """Build a tiny in-memory index and verify retrieval is sensible."""
    # This test exercises the full ingest → index → retrieve pipeline in mock mode.
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "freq_policy.md").write_text(
        "# Frequency Control\n"
        "System frequency must stay between 59.5 Hz and 60.5 Hz. "
        "Governor response activates immediately on frequency deviation.\n",
        encoding="utf-8",
    )
    (docs_dir / "voltage_policy.md").write_text(
        "# Voltage Limits\n"
        "Bus voltages must remain within 0.95 to 1.05 per unit. "
        "Capacitor banks support low voltage situations.\n",
        encoding="utf-8",
    )

    from rag_grid.ingest import ingest_directory
    from rag_grid.index import build_index
    from rag_grid.retrieve import retrieve

    index_dir = tmp_path / "index"
    chunks = ingest_directory(docs_dir)
    build_index(chunks, index_dir)

    results = retrieve("frequency deviation governor response", index_dir, top_k=2)
    assert len(results) >= 1
    # The frequency doc should be ranked first or second.
    sources = [r.source for r in results]
    assert "freq_policy.md" in sources


def test_retrieve_empty_query(tmp_path):
    """Retrieval with an empty query should return results without crashing."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "a.md").write_text("# Policy\nSome content here.\n", encoding="utf-8")

    from rag_grid.ingest import ingest_directory
    from rag_grid.index import build_index
    from rag_grid.retrieve import retrieve

    index_dir = tmp_path / "index"
    chunks = ingest_directory(docs_dir)
    build_index(chunks, index_dir)

    results = retrieve("", index_dir, top_k=3)
    # Should not raise; may return chunks or empty list.
    assert isinstance(results, list)
