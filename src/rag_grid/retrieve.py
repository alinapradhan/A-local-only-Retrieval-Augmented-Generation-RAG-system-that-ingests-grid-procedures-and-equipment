"""Top-k chunk retrieval against the built vector index."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np

from rag_grid.config import config
from rag_grid.index import load_index, _normalize
from rag_grid.llm import get_embeddings
from rag_grid.schema import Chunk

logger = logging.getLogger(__name__)


def retrieve(
    query: str,
    index_dir: Path,
    top_k: int | None = None,
) -> list[Chunk]:
    """Return the top-*k* chunks most relevant to *query*.

    Args:
        query:     Free-text query string.
        index_dir: Directory produced by :func:`~rag_grid.index.build_index`.
        top_k:     Number of results to return (defaults to ``config.top_k``).

    Returns:
        Ordered list of :class:`~rag_grid.schema.Chunk` objects (most relevant first).
        Returns an empty list if the index is empty.

    Raises:
        FileNotFoundError: if the index does not exist.
    """
    top_k = top_k if top_k is not None else config.top_k

    chunks, idx, backend = load_index(index_dir)
    if not chunks:
        logger.warning("Index is empty; returning no results.")
        return []

    # Embed query.
    query_emb = np.array(get_embeddings([query]), dtype=np.float32)
    _normalize(query_emb)  # shape (1, D)

    if backend == "faiss":
        import faiss  # type: ignore[import]

        k = min(top_k, len(chunks))
        _distances, indices = idx.search(query_emb, k)
        result_indices = [i for i in indices[0] if 0 <= i < len(chunks)]
    else:
        # numpy cosine similarity (dot product on L2-normalised vectors).
        matrix: np.ndarray = idx  # shape (N, D)
        scores = matrix @ query_emb.T  # shape (N, 1)
        scores = scores.flatten()
        k = min(top_k, len(scores))
        result_indices = list(np.argsort(scores)[::-1][:k])

    results = [chunks[i] for i in result_indices]
    logger.info(
        "Retrieved %d/%d chunks for query: %.60s…", len(results), top_k, query
    )
    return results
