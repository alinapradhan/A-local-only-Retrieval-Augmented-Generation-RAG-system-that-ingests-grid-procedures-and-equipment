"""Safety agent: applies hard rule checks and suggests safer alternatives."""

from __future__ import annotations

import logging

from rag_grid.config import config
from rag_grid.schema import Action, SafetyResult, Telemetry
from rag_grid.sim.constraints import (
    check_frequency,
    check_line_loading,
    check_load_shed,
    check_ramp,
    check_spinning_reserve,
    check_voltage,
    gen_current_output_mw,
)

logger = logging.getLogger(__name__)


def _safe_dispatch_setpoint(requested_mw: float, current_gen_mw: float) -> float:
    """Clip dispatch to respect ramp-rate limit."""
    limit = config.ramp_rate_mw_per_5min
    if requested_mw > current_gen_mw:
        return min(requested_mw, current_gen_mw + limit)
    return max(requested_mw, current_gen_mw - limit)


def _build_alternative(action: Action, safe_setpoint: float) -> Action:
    """Return a copy of *action* with the setpoint clamped to *safe_setpoint*."""
    return Action(
        action_id=action.action_id + "-ALT",
        action_type=action.action_type,
        target=action.target,
        setpoint=safe_setpoint,
        unit=action.unit,
        rationale=(
            f"Safety-adjusted alternative: setpoint reduced from"
            f" {action.setpoint} {action.unit} to {safe_setpoint:.1f} {action.unit}"
            " to comply with ramp-rate/thermal/reserve limits."
        ),
        cited_chunks=action.cited_chunks,
    )


def evaluate_action(action: Action, telemetry: Telemetry) -> SafetyResult:
    """Evaluate a single *action* against all hard safety rules.

    Args:
        action:    The proposed action.
        telemetry: Current telemetry snapshot (used to derive baseline values).

    Returns:
        :class:`~rag_grid.schema.SafetyResult` with ``approved``, ``violations``,
        and optional ``alternatives``.
    """
    violations: list[str] = []
    alternatives: list[Action] = []

    action_type = action.action_type.lower()
    setpoint = action.setpoint

    # ── Frequency set-point validation ────────────────────────────────────────
    if action_type == "frequency_support":
        violations.extend(check_frequency(setpoint))

    # ── Dispatch / curtailment ramp-rate check ────────────────────────────────
    if action_type in ("dispatch", "curtailment"):
        current_gen = gen_current_output_mw(action.target, telemetry.total_gen_mw)
        violations.extend(check_ramp(current_gen, setpoint))
        if violations:
            safe_sp = _safe_dispatch_setpoint(setpoint, current_gen)
            if safe_sp != setpoint:
                alternatives.append(_build_alternative(action, safe_sp))

    # ── Load-shed cap ─────────────────────────────────────────────────────────
    if action_type == "load_shedding":
        violations.extend(check_load_shed(setpoint))
        if violations:
            safe_sp = min(setpoint, config.max_load_shed_mw)
            alternatives.append(_build_alternative(action, safe_sp))

    # ── Spinning reserve check (post-dispatch estimate) ───────────────────────
    if action_type == "dispatch":
        current_gen_est = gen_current_output_mw(action.target, telemetry.total_gen_mw)
        delta_gen = setpoint - current_gen_est
        new_reserve = telemetry.spinning_reserve_mw - delta_gen
        violations.extend(check_spinning_reserve(new_reserve))

    # ── Line loading ───────────────────────────────────────────────────────────
    for line_id, loading_pct in telemetry.line_loading_pct.items():
        violations.extend(check_line_loading(line_id, loading_pct))

    # ── Bus voltages ──────────────────────────────────────────────────────────
    for bus_id, voltage_pu in telemetry.bus_voltages.items():
        violations.extend(check_voltage(bus_id, voltage_pu))

    # Separate hard violations (blocking) from warnings (non-blocking).
    # Warnings: "frequency alert …" and "line … approaching limit …"
    hard_violations = [
        v for v in violations
        if not (
            v.lower().startswith("frequency alert")
            or ("approaching" in v.lower() and "line" in v.lower())
        )
    ]
    approved = len(hard_violations) == 0

    if not approved and not alternatives:
        # Generic capped alternative if no specific one was generated.
        capped = max(0.0, setpoint * 0.8)
        alternatives.append(_build_alternative(action, capped))

    result = SafetyResult(
        action_id=action.action_id,
        approved=approved,
        violations=violations,
        alternatives=alternatives if not approved else [],
    )

    status = "APPROVED" if approved else "BLOCKED"
    logger.info("Safety[%s]: %s — %d violation(s).", status, action.action_id, len(violations))
    return result


def evaluate(actions: list[Action], telemetry: Telemetry) -> list[SafetyResult]:
    """Evaluate all *actions* and return a result for each.

    Args:
        actions:   List of proposed actions from the Planner.
        telemetry: Current telemetry snapshot.

    Returns:
        One :class:`~rag_grid.schema.SafetyResult` per action, in the same order.
    """
    return [evaluate_action(a, telemetry) for a in actions]
