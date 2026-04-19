"""Configuration loaded from environment variables with safe defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class Config:
    """Central configuration object.

    All values can be overridden via environment variables.  When
    ``OPENAI_API_KEY`` is absent the system falls back to mock mode
    (TF-IDF embeddings + deterministic LLM stubs).
    """

    # ── LLM provider ──────────────────────────────────────────────────────────
    openai_api_key: str = field(
        default_factory=lambda: os.getenv("OPENAI_API_KEY", "")
    )
    openai_base_url: str = field(
        default_factory=lambda: os.getenv(
            "OPENAI_BASE_URL", "https://api.openai.com/v1"
        )
    )
    chat_model: str = field(
        default_factory=lambda: os.getenv("RAG_CHAT_MODEL", "gpt-4o-mini")
    )
    embedding_model: str = field(
        default_factory=lambda: os.getenv(
            "RAG_EMBEDDING_MODEL", "text-embedding-3-small"
        )
    )

    # ── Chunking ──────────────────────────────────────────────────────────────
    chunk_size: int = field(
        default_factory=lambda: int(os.getenv("RAG_CHUNK_SIZE", "400"))
    )
    chunk_overlap: int = field(
        default_factory=lambda: int(os.getenv("RAG_CHUNK_OVERLAP", "60"))
    )

    # ── Retrieval ─────────────────────────────────────────────────────────────
    top_k: int = field(
        default_factory=lambda: int(os.getenv("RAG_TOP_K", "5"))
    )

    # ── Paths ─────────────────────────────────────────────────────────────────
    index_dir: str = field(
        default_factory=lambda: os.getenv("RAG_INDEX_DIR", "rag_grid_index")
    )
    chunks_file: str = field(
        default_factory=lambda: os.getenv("RAG_CHUNKS_FILE", "rag_grid_chunks.json")
    )
    audit_log: str = field(
        default_factory=lambda: os.getenv("RAG_AUDIT_LOG", "rag_grid_audit.log")
    )

    # ── Safety limits (all configurable) ─────────────────────────────────────
    freq_min_hz: float = field(
        default_factory=lambda: float(os.getenv("GRID_FREQ_MIN_HZ", "59.5"))
    )
    freq_max_hz: float = field(
        default_factory=lambda: float(os.getenv("GRID_FREQ_MAX_HZ", "60.5"))
    )
    freq_alert_low_hz: float = field(
        default_factory=lambda: float(os.getenv("GRID_FREQ_ALERT_LOW_HZ", "59.7"))
    )
    freq_alert_high_hz: float = field(
        default_factory=lambda: float(os.getenv("GRID_FREQ_ALERT_HIGH_HZ", "60.3"))
    )
    line_max_pct: float = field(
        default_factory=lambda: float(os.getenv("GRID_LINE_MAX_PCT", "100.0"))
    )
    line_warn_pct: float = field(
        default_factory=lambda: float(os.getenv("GRID_LINE_WARN_PCT", "90.0"))
    )
    ramp_rate_mw_per_5min: float = field(
        default_factory=lambda: float(os.getenv("GRID_RAMP_RATE_MW_PER_5MIN", "50.0"))
    )
    max_load_shed_mw: float = field(
        default_factory=lambda: float(os.getenv("GRID_MAX_LOAD_SHED_MW", "100.0"))
    )
    min_spinning_reserve_mw: float = field(
        default_factory=lambda: float(
            os.getenv("GRID_MIN_SPINNING_RESERVE_MW", "50.0")
        )
    )
    volt_min_pu: float = field(
        default_factory=lambda: float(os.getenv("GRID_VOLT_MIN_PU", "0.95"))
    )
    volt_max_pu: float = field(
        default_factory=lambda: float(os.getenv("GRID_VOLT_MAX_PU", "1.05"))
    )

    # ── Derived ───────────────────────────────────────────────────────────────
    @property
    def mock_mode(self) -> bool:
        """True when no real LLM API key is configured."""
        return not bool(self.openai_api_key)


# Module-level singleton — import this everywhere.
config = Config()
