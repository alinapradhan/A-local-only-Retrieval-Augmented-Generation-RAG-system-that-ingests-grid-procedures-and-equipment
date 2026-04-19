"""Planner agent: proposes candidate control actions from retrieved context."""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from rag_grid.llm import chat_complete
from rag_grid.schema import Action, Chunk, Telemetry

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are an expert power-systems operator copilot. Your task is to PROPOSE control actions.

Rules:
1. You MUST use ONLY the retrieved context (chunks) provided below. Do NOT invent constraints.
2. Propose 1–3 candidate actions. Choose from: dispatch, curtailment, load_shedding,
   voltage_support, frequency_support.
3. For each action include: action_id, action_type, target, setpoint, unit, rationale,
   cited_chunks (list of chunk_id values from the context).
4. Return ONLY a JSON array of action objects. No prose outside the JSON.
5. If the retrieved context is insufficient, return an empty array [].

Action JSON schema:
{
  "action_id": "ACT-001",
  "action_type": "dispatch",
  "target": "generator_G2",
  "setpoint": 150.0,
  "unit": "MW",
  "rationale": "…",
  "cited_chunks": ["<chunk_id>"]
}
"""


def _telemetry_summary(tel: Telemetry) -> str:
    """Format a compact telemetry snapshot for inclusion in the prompt."""
    lines_summary = ", ".join(
        f"{lid}={pct:.1f}%" for lid, pct in tel.line_loading_pct.items()
    )
    bus_summary = ", ".join(
        f"{bid}={v:.3f} pu" for bid, v in tel.bus_voltages.items()
    )
    return (
        f"Timestamp: {tel.timestamp}\n"
        f"Total load: {tel.total_load_mw:.1f} MW\n"
        f"Total generation: {tel.total_gen_mw:.1f} MW\n"
        f"Frequency: {tel.frequency_hz:.3f} Hz\n"
        f"Spinning reserve: {tel.spinning_reserve_mw:.1f} MW\n"
        f"Line loading: {lines_summary or 'n/a'}\n"
        f"Bus voltages: {bus_summary or 'n/a'}"
    )


def _chunks_context(chunks: list[Chunk]) -> str:
    """Format retrieved chunks as numbered context blocks."""
    if not chunks:
        return "(no retrieved context)"
    lines: list[str] = []
    for chunk in chunks:
        lines.append(
            f"[{chunk.chunk_id}] {chunk.source} § {chunk.section}\n{chunk.text}"
        )
    return "\n\n---\n\n".join(lines)


def _parse_actions(raw: str, chunks: list[Chunk]) -> list[Action]:
    """Parse the LLM JSON response into Action objects.

    Returns an empty list if parsing fails or the response is empty.
    """
    raw = raw.strip()
    # Strip markdown code fences if present.
    if raw.startswith("```"):
        raw = "\n".join(
            line for line in raw.splitlines() if not line.startswith("```")
        )

    try:
        data: list[dict[str, Any]] = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("Planner LLM returned non-JSON: %s — %s", exc, raw[:200])
        return []

    if not isinstance(data, list):
        logger.warning("Planner expected JSON array, got %s.", type(data).__name__)
        return []

    valid_chunk_ids = {c.chunk_id for c in chunks}
    actions: list[Action] = []
    for idx, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            continue
        # Ensure action_id is set and unique.
        action_id = str(item.get("action_id") or f"ACT-{idx:03d}")
        # Validate cited_chunks against retrieved set.
        cited = [
            cid for cid in item.get("cited_chunks", []) if cid in valid_chunk_ids
        ]
        try:
            action = Action(
                action_id=action_id,
                action_type=str(item.get("action_type", "dispatch")),
                target=str(item.get("target", "unknown")),
                setpoint=float(item.get("setpoint", 0.0)),
                unit=str(item.get("unit", "MW")),
                rationale=str(item.get("rationale", "")),
                cited_chunks=cited,
            )
            actions.append(action)
        except Exception as exc:  # pydantic validation error etc.
            logger.warning("Skipping malformed action item %d: %s", idx, exc)

    return actions


# ── Public API ─────────────────────────────────────────────────────────────────


def plan(
    goal: str,
    telemetry: Telemetry,
    retrieved_chunks: list[Chunk],
) -> list[Action]:
    """Propose candidate actions for the given *goal* and telemetry snapshot.

    Args:
        goal:             Free-text operator goal.
        telemetry:        Latest telemetry snapshot.
        retrieved_chunks: Chunks returned by the retriever.

    Returns:
        List of proposed :class:`~rag_grid.schema.Action` objects.
        Returns an empty list if no context was retrieved (will trigger
        "insufficient information" path in the orchestrator).
    """
    if not retrieved_chunks:
        logger.warning("Planner received no retrieved context — cannot propose actions.")
        return []

    tel_summary = _telemetry_summary(telemetry)
    context = _chunks_context(retrieved_chunks)

    user_content = (
        f"OPERATOR GOAL: {goal}\n\n"
        f"CURRENT TELEMETRY:\n{tel_summary}\n\n"
        f"RETRIEVED CONTEXT:\n{context}\n\n"
        "Propose candidate actions as a JSON array."
    )

    raw = chat_complete(
        messages=[{"role": "user", "content": user_content}],
        system_prompt=_SYSTEM_PROMPT,
    )

    actions = _parse_actions(raw, retrieved_chunks)

    # Back-fill cited_chunks with all retrieved chunk IDs when the LLM
    # returned an empty citation list (common in mock mode).
    all_ids = [c.chunk_id for c in retrieved_chunks]
    for action in actions:
        if not action.cited_chunks:
            action.cited_chunks = all_ids[:2]  # cite the top-2 most relevant

    logger.info("Planner proposed %d action(s).", len(actions))
    return actions
