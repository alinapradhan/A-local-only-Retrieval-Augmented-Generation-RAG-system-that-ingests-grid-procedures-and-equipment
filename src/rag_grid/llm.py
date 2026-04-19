"""LLM provider wrapper supporting OpenAI and deterministic mock mode."""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

import numpy as np

from rag_grid.config import config

logger = logging.getLogger(__name__)

# ── Mock embedding helpers ─────────────────────────────────────────────────────

_MOCK_DIM = 512


def _hash_embed(text: str) -> list[float]:
    """Stable bag-of-words hash embedding (512-d, L2-normalised).

    Each word is hashed to a dimension index; term frequency is accumulated.
    The result is L2-normalised so cosine similarity == dot product.
    """
    vec = np.zeros(_MOCK_DIM, dtype=np.float32)
    for word in text.lower().split():
        idx = int(hashlib.md5(word.encode()).hexdigest(), 16) % _MOCK_DIM
        vec[idx] += 1.0
    norm = float(np.linalg.norm(vec))
    if norm > 0:
        vec /= norm
    return vec.tolist()


# ── TF-IDF based embeddings for mock index building ───────────────────────────

_tfidf: Any | None = None  # sklearn TfidfVectorizer fitted on corpus


def fit_tfidf(texts: list[str]) -> None:
    """Fit a TF-IDF vectorizer on *texts*.  Call this once during index build."""
    global _tfidf
    from sklearn.feature_extraction.text import TfidfVectorizer

    _tfidf = TfidfVectorizer(max_features=_MOCK_DIM, sublinear_tf=True)
    _tfidf.fit(texts)
    logger.info("TF-IDF vectorizer fitted on %d documents.", len(texts))


def _tfidf_embed(texts: list[str]) -> list[list[float]]:
    """Return TF-IDF embeddings using the fitted vectorizer.

    Falls back to hash embeddings if the vectorizer is not yet fitted.
    """
    if _tfidf is None:
        return [_hash_embed(t) for t in texts]
    matrix = _tfidf.transform(texts).toarray().astype(np.float32)
    # L2-normalise rows
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    matrix /= norms
    return matrix.tolist()


def load_tfidf(vectorizer: Any) -> None:
    """Restore a previously serialised TF-IDF vectorizer (called by index loader)."""
    global _tfidf
    _tfidf = vectorizer


# ── Public embedding API ───────────────────────────────────────────────────────


def get_embeddings(texts: list[str]) -> list[list[float]]:
    """Return embeddings for *texts*.

    Uses OpenAI when an API key is configured; otherwise TF-IDF / hash mock.
    """
    if config.mock_mode:
        return _tfidf_embed(texts)

    from openai import OpenAI

    client = OpenAI(
        api_key=config.openai_api_key, base_url=config.openai_base_url
    )
    response = client.embeddings.create(
        model=config.embedding_model,
        input=texts,
    )
    return [item.embedding for item in response.data]


# ── Public chat API ────────────────────────────────────────────────────────────

_PLANNER_MOCK_ACTIONS = [
    {
        "action_id": "ACT-001",
        "action_type": "frequency_support",
        "target": "generator_G1",
        "setpoint": 60.0,
        "unit": "Hz",
        "rationale": (
            "Frequency deviation detected. Adjusting governor setpoint on G1 to"
            " restore nominal 60 Hz per grid frequency-control policy."
        ),
        "cited_chunks": [],
    },
    {
        "action_id": "ACT-002",
        "action_type": "dispatch",
        "target": "generator_G2",
        "setpoint": 150.0,
        "unit": "MW",
        "rationale": (
            "Increase generation dispatch on G2 to close the load-generation"
            " imbalance and rebuild spinning reserve per operator playbook."
        ),
        "cited_chunks": [],
    },
    {
        "action_id": "ACT-003",
        "action_type": "curtailment",
        "target": "generator_G3",
        "setpoint": 80.0,
        "unit": "MW",
        "rationale": (
            "Curtail renewable output on G3 to prevent over-frequency and"
            " line overloads per equipment limit constraints."
        ),
        "cited_chunks": [],
    },
]

_EXPLANATION_MOCK = (
    "OPERATOR COPILOT SUMMARY (MOCK MODE)\n\n"
    "Based on retrieved grid policies and equipment constraints, the following"
    " actions are recommended:\n"
    "  1. [ACT-001] Frequency support — governor setpoint adjustment on G1\n"
    "     Citation: grid_policies.md § Frequency Control Policy\n"
    "  2. [ACT-002] Dispatch increase on G2 to cover generation deficit\n"
    "     Citation: operator_playbook.md § Generation Dispatch Procedures\n"
    "  3. [ACT-003] Curtailment of G3 to prevent line overload\n"
    "     Citation: equipment_limits.md § Line Thermal Limits\n\n"
    "All actions have been evaluated by the Safety Agent. Human approval is"
    " required before execution. This is a simulation only — no SCADA"
    " connection is made."
)


def _mock_chat_complete(messages: list[dict], system_prompt: str) -> str:
    """Deterministic mock LLM — returns canned JSON or text based on intent."""
    combined = system_prompt.lower() + " ".join(
        m.get("content", "") for m in messages
    ).lower()

    if any(kw in combined for kw in ("propose", "planner", "candidate action")):
        return json.dumps(_PLANNER_MOCK_ACTIONS)

    if any(kw in combined for kw in ("explanation", "summary", "final")):
        return _EXPLANATION_MOCK

    return (
        "Insufficient context to generate a specific recommendation."
        " Please ingest additional policy documents."
    )


def chat_complete(
    messages: list[dict],
    system_prompt: str = "",
) -> str:
    """Send a chat request to the configured LLM.

    Returns the assistant's response as a plain string.
    Falls back to mock mode when no API key is set.
    """
    if config.mock_mode:
        logger.debug("Mock LLM: returning deterministic stub.")
        return _mock_chat_complete(messages, system_prompt)

    from openai import OpenAI

    client = OpenAI(
        api_key=config.openai_api_key, base_url=config.openai_base_url
    )
    full_messages: list[dict] = []
    if system_prompt:
        full_messages.append({"role": "system", "content": system_prompt})
    full_messages.extend(messages)

    response = client.chat.completions.create(
        model=config.chat_model,
        messages=full_messages,
        temperature=0.1,
    )
    return response.choices[0].message.content or ""
