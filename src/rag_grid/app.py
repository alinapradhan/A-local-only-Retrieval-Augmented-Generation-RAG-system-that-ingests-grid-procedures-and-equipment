"""Orchestrator: wires retrieval → planning → safety → control → simulation."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from rag_grid.agents import controller, planner, safety
from rag_grid.config import config
from rag_grid.index import build_index
from rag_grid.ingest import ingest_directory, load_chunks, save_chunks
from rag_grid.retrieve import retrieve
from rag_grid.schema import (
    CommandPlan,
    CommandStep,
    FinalOutput,
    SimulationResult,
    Telemetry,
)
from rag_grid.sim import grid_model

logger = logging.getLogger(__name__)


# ── Telemetry helpers ──────────────────────────────────────────────────────────


def load_telemetry(csv_path: Path) -> Telemetry:
    """Load the *last* row from a telemetry CSV as a Telemetry snapshot.

    Expected columns:
        timestamp, total_load_mw, total_gen_mw, frequency_hz,
        spinning_reserve_mw
    Optional columns (prefix ``bus_`` or ``line_``) are collected into dicts.
    """
    import pandas as pd

    df = pd.read_csv(csv_path)
    if df.empty:
        raise ValueError(f"Telemetry CSV is empty: {csv_path}")

    row = df.iloc[-1]  # use the most recent reading

    bus_voltages: dict[str, float] = {}
    line_loading: dict[str, float] = {}

    for col in df.columns:
        if col.startswith("bus_"):
            bus_voltages[col[len("bus_"):]] = float(row[col])
        elif col.startswith("line_"):
            line_loading[col[len("line_"):]] = float(row[col])

    return Telemetry(
        timestamp=str(row.get("timestamp", datetime.now(tz=timezone.utc).isoformat())),
        total_load_mw=float(row["total_load_mw"]),
        total_gen_mw=float(row["total_gen_mw"]),
        frequency_hz=float(row["frequency_hz"]),
        spinning_reserve_mw=float(row["spinning_reserve_mw"]),
        bus_voltages=bus_voltages,
        line_loading_pct=line_loading,
    )


# ── Explanation generation ─────────────────────────────────────────────────────


def _build_explanation(output: FinalOutput) -> str:
    """Generate a human-readable explanation with citations."""
    from rag_grid.llm import chat_complete

    chunk_refs = "; ".join(
        f"{c.source} § {c.section} [{c.chunk_id}]"
        for c in output.retrieved_chunks
    )

    approved_ids = {
        step.action.action_id
        for step in output.approved_command_plan.steps
        if step.approved
    }
    blocked_ids = {
        r.action_id
        for r in output.safety_evaluation
        if not r.approved
    }

    action_lines = []
    for action in output.proposed_actions:
        status = "✓ APPROVED" if action.action_id in approved_ids else "✗ BLOCKED"
        cited = (
            ", ".join(f"[{cid}]" for cid in action.cited_chunks)
            if action.cited_chunks
            else "no direct citation"
        )
        action_lines.append(
            f"  • [{status}] {action.action_id}: {action.action_type} on"
            f" {action.target} → {action.setpoint} {action.unit}\n"
            f"    Rationale: {action.rationale}\n"
            f"    Citations: {cited}"
        )

    prompt = (
        f"You are a power-systems operator copilot. Write a concise explanation"
        f" (3–5 sentences) summarising the recommended actions, their rationale,"
        f" and safety status. Cite document sources where relevant.\n\n"
        f"Retrieved context sources: {chunk_refs}\n\n"
        f"Actions:\n" + "\n".join(action_lines)
    )

    raw = chat_complete(
        messages=[{"role": "user", "content": prompt}],
        system_prompt="explanation summary",
    )
    return raw.strip()


# ── Audit logging ──────────────────────────────────────────────────────────────


def _audit_log(output: FinalOutput) -> None:
    """Append a JSONL audit entry to the configured audit log file."""
    entry = {
        "ts": datetime.now(tz=timezone.utc).isoformat(),
        "plan_id": output.approved_command_plan.plan_id,
        "goal": output.approved_command_plan.goal,
        "retrieved_chunk_ids": [c.chunk_id for c in output.retrieved_chunks],
        "proposed_action_ids": [a.action_id for a in output.proposed_actions],
        "safety_results": [
            {"action_id": r.action_id, "approved": r.approved, "violations": r.violations}
            for r in output.safety_evaluation
        ],
    }
    with open(config.audit_log, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")


# ── Commands ───────────────────────────────────────────────────────────────────


def cmd_ingest(docs_dir: Path, chunks_file: Path) -> None:
    """Ingest documents from *docs_dir* and write chunks to *chunks_file*."""
    chunks = ingest_directory(docs_dir)
    if not chunks:
        logger.error("No chunks produced from %s. Check that docs exist.", docs_dir)
        return
    save_chunks(chunks, chunks_file)
    print(f"✓ Ingested {len(chunks)} chunks → {chunks_file}")


def cmd_index(chunks_file: Path, index_dir: Path) -> None:
    """Build the vector index from *chunks_file*."""
    chunks = load_chunks(chunks_file)
    build_index(chunks, index_dir)
    print(f"✓ Index built: {len(chunks)} vectors → {index_dir}/")


def cmd_run(
    telemetry_path: Path,
    goal: str,
    index_dir: Path,
    top_k: int | None = None,
    simulate: bool = False,
) -> FinalOutput:
    """Run the full RAG → plan → safety → control pipeline.

    Args:
        telemetry_path: Path to telemetry CSV.
        goal:           Operator goal string.
        index_dir:      Directory of the built vector index.
        top_k:          Number of chunks to retrieve (defaults to config).
        simulate:       If True, run the command plan through the toy grid model.

    Returns:
        :class:`~rag_grid.schema.FinalOutput` with all fields populated.
    """
    top_k = top_k or config.top_k

    # 1. Load telemetry.
    logger.info("Loading telemetry from %s.", telemetry_path)
    telemetry = load_telemetry(telemetry_path)

    # 2. Build retrieval query from goal + telemetry summary.
    query = (
        f"{goal}. "
        f"Frequency {telemetry.frequency_hz:.2f} Hz, "
        f"load {telemetry.total_load_mw:.0f} MW, "
        f"generation {telemetry.total_gen_mw:.0f} MW, "
        f"reserve {telemetry.spinning_reserve_mw:.0f} MW."
    )

    # 3. Retrieve relevant chunks.
    logger.info("Retrieving top-%d chunks…", top_k)
    chunks = retrieve(query, index_dir, top_k=top_k)

    if not chunks:
        logger.warning("No chunks retrieved. Insufficient information path.")
        empty_plan = CommandPlan(
            plan_id=f"PLAN-{uuid.uuid4().hex[:8].upper()}",
            created_at=datetime.now(tz=timezone.utc).isoformat(),
            goal=goal,
            steps=[],
            human_approved=False,
        )
        return FinalOutput(
            retrieved_chunks=[],
            proposed_actions=[],
            safety_evaluation=[],
            approved_command_plan=empty_plan,
            final_explanation=(
                "INSUFFICIENT INFORMATION: No relevant documents were retrieved."
                " Please ingest grid policies, equipment limits, and operator"
                " playbook documents, then rebuild the index."
            ),
        )

    # 4. Plan.
    logger.info("Planner proposing actions…")
    actions = planner.plan(goal=goal, telemetry=telemetry, retrieved_chunks=chunks)

    if not actions:
        empty_plan = CommandPlan(
            plan_id=f"PLAN-{uuid.uuid4().hex[:8].upper()}",
            created_at=datetime.now(tz=timezone.utc).isoformat(),
            goal=goal,
            steps=[],
            human_approved=False,
        )
        return FinalOutput(
            retrieved_chunks=chunks,
            proposed_actions=[],
            safety_evaluation=[],
            approved_command_plan=empty_plan,
            final_explanation=(
                "INSUFFICIENT INFORMATION: The planner could not propose any actions"
                " from the retrieved context. Please provide more specific policy"
                " documents or refine the operator goal."
            ),
        )

    # 5. Safety evaluation.
    logger.info("Safety agent evaluating %d action(s)…", len(actions))
    safety_results = safety.evaluate(actions, telemetry)

    # 6. Build command plan.
    command_plan = controller.build_command_plan(goal, actions, safety_results)

    # 7. Simulate (optional).
    sim_result: SimulationResult | None = None
    if simulate:
        logger.info("Running toy grid simulation…")
        initial_state = grid_model.telemetry_to_grid_state(telemetry)
        sim_result = grid_model.simulate(command_plan, initial_state)

    # 8. Assemble output (without explanation first, then fill in).
    output = FinalOutput(
        retrieved_chunks=chunks,
        proposed_actions=actions,
        safety_evaluation=safety_results,
        approved_command_plan=command_plan,
        simulation_result=sim_result,
        final_explanation="",  # filled below
    )

    # 9. Generate explanation.
    logger.info("Generating final explanation…")
    output.final_explanation = _build_explanation(output)

    # 10. Audit log.
    _audit_log(output)

    return output
