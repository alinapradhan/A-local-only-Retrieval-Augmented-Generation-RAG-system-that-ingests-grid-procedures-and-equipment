"""Build and persist the vector index; load it back for retrieval."""

from __future__ import annotations

import logging
import pickle
from pathlib import Path
from typing import Any

import numpy as np

from rag_grid.config import config
from rag_grid.schema import Chunk

logger = logging.getLogger(__name__)

# Type aliases
_NpMatrix = np.ndarray  # shape (N, D), float32


def _normalize(matrix: _NpMatrix) -> _NpMatrix:
    """L2-normalise every row of *matrix* in-place; returns the matrix."""
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    matrix /= norms
    return matrix


# ── Index build ────────────────────────────────────────────────────────────────


def build_index(chunks: list[Chunk], index_dir: Path) -> None:
    """Embed *chunks* and write the vector index to *index_dir*.

    In mock mode a TF-IDF vectorizer is fitted and saved; in real mode
    embeddings come from the OpenAI API and (if available) FAISS is used.

    Directory layout after build::

        index_dir/
            chunks.json        — serialised chunk metadata + text
            vectors.npy        — embedding matrix (numpy fallback)
            tfidf.pkl          — TF-IDF vectorizer (mock mode only)
            vectors.faiss      — FAISS flat-IP index (real mode, if faiss installed)
    """
    import json

    from rag_grid.llm import fit_tfidf, get_embeddings

    index_dir.mkdir(parents=True, exist_ok=True)

    texts = [c.text for c in chunks]

    # In mock mode, first fit the TF-IDF vectorizer so embeddings are meaningful.
    if config.mock_mode:
        fit_tfidf(texts)
        # Persist vectorizer for later use by the retriever.
        from rag_grid import llm as llm_module

        if llm_module._tfidf is not None:
            with open(index_dir / "tfidf.pkl", "wb") as fh:
                pickle.dump(llm_module._tfidf, fh)
            logger.info("TF-IDF vectorizer saved.")

    embeddings = get_embeddings(texts)
    matrix = np.array(embeddings, dtype=np.float32)
    _normalize(matrix)

    # Try FAISS (optional dependency).
    faiss_ok = False
    if not config.mock_mode:
        try:
            import faiss  # type: ignore[import]

            dim = matrix.shape[1]
            idx: Any = faiss.IndexFlatIP(dim)
            idx.add(matrix)
            faiss.write_index(idx, str(index_dir / "vectors.faiss"))
            faiss_ok = True
            logger.info("FAISS index written (%d vectors, dim=%d).", len(chunks), dim)
        except ImportError:
            logger.info("faiss-cpu not installed; using numpy fallback.")

    # Always write numpy matrix as fallback / mock backing store.
    np.save(str(index_dir / "vectors.npy"), matrix)

    # Write chunk metadata.
    with open(index_dir / "chunks.json", "w", encoding="utf-8") as fh:
        json.dump([c.model_dump() for c in chunks], fh, indent=2)

    logger.info(
        "Index built: %d chunks, backend=%s.",
        len(chunks),
        "faiss" if faiss_ok else "numpy",
    )


# ── Index load ─────────────────────────────────────────────────────────────────


def load_index(
    index_dir: Path,
) -> tuple[list[Chunk], Any, str]:
    """Load the vector index from *index_dir*.

    Returns:
        (chunks, index_object, backend_name)
        where *backend_name* is ``"faiss"`` or ``"numpy"``.

    Raises:
        FileNotFoundError: if the index has not been built yet.
    """
    import json

    chunks_path = index_dir / "chunks.json"
    if not chunks_path.exists():
        raise FileNotFoundError(
            f"No index found at {index_dir}. "
            "Run 'python -m rag_grid index' first."
        )

    with open(chunks_path, encoding="utf-8") as fh:
        chunks = [Chunk(**item) for item in json.load(fh)]

    # Restore TF-IDF vectorizer if present (mock mode).
    tfidf_path = index_dir / "tfidf.pkl"
    if tfidf_path.exists():
        with open(tfidf_path, "rb") as fh:
            vectorizer = pickle.load(fh)
        from rag_grid.llm import load_tfidf

        load_tfidf(vectorizer)
        logger.debug("TF-IDF vectorizer restored from %s.", tfidf_path)

    # Prefer FAISS if available and index file exists.
    faiss_path = index_dir / "vectors.faiss"
    if faiss_path.exists():
        try:
            import faiss  # type: ignore[import]

            idx = faiss.read_index(str(faiss_path))
            logger.info("FAISS index loaded (%d vectors).", idx.ntotal)
            return chunks, idx, "faiss"
        except ImportError:
            logger.warning("faiss-cpu not installed; falling back to numpy.")

    numpy_path = index_dir / "vectors.npy"
    if numpy_path.exists():
        matrix = np.load(str(numpy_path))
        logger.info("Numpy index loaded (shape=%s).", matrix.shape)
        return chunks, matrix, "numpy"

    raise FileNotFoundError(
        f"Neither vectors.faiss nor vectors.npy found in {index_dir}."
    )
