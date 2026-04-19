"""Toy grid model for before/after simulation of command plans.

Assumptions (documented):
  - Linear frequency-response model: Δf = (ΔP_gen - ΔP_load) / D
    where D is a droop/damping constant (MW/Hz), typical value ~200 MW/Hz.
  - Line loading changes proportionally to generation dispatch changes;
    each MW of new dispatch reduces loading on connected lines by a fixed
    sensitivity factor.
  - Voltage is approximated linearly: ΔV ≈ ΔQ * X_pu (reactive droop).
  - This is NOT a full AC power-flow solver.
"""

from __future__ import annotations

import logging
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from rag_grid.schema import Action, CommandPlan, SimulationResult, Telemetry

logger = logging.getLogger(__name__)

# Droop constant: MW absorbed per 0.1 Hz deviation
_FREQ_DROOP_MW_PER_HZ = 200.0  # MW / Hz

# Fraction of line loading relieved per MW of new dispatch (heuristic)
_LINE_SENS = 0.005  # %/MW

# Voltage droop: pu change per MW of reactive support (approximation)
_VOLT_DROOP_PU_PER_MVAR = 0.0005


@dataclass
class BusState:
    bus_id: str
    voltage_pu: float = 1.0


@dataclass
class LineState:
    line_id: str
    loading_pct: float = 50.0


@dataclass
class GeneratorState:
    gen_id: str
    output_mw: float = 100.0
    max_mw: float = 300.0
    min_mw: float = 0.0


@dataclass
class GridState:
    """Snapshot of the toy grid."""

    frequency_hz: float = 60.0
    total_load_mw: float = 500.0
    total_gen_mw: float = 500.0
    spinning_reserve_mw: float = 100.0
    buses: dict[str, BusState] = field(default_factory=dict)
    lines: dict[str, LineState] = field(default_factory=dict)
    generators: dict[str, GeneratorState] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "frequency_hz": round(self.frequency_hz, 4),
            "total_load_mw": round(self.total_load_mw, 2),
            "total_gen_mw": round(self.total_gen_mw, 2),
            "spinning_reserve_mw": round(self.spinning_reserve_mw, 2),
            "bus_voltages": {
                bid: round(b.voltage_pu, 4) for bid, b in self.buses.items()
            },
            "line_loading_pct": {
                lid: round(l.loading_pct, 2) for lid, l in self.lines.items()
            },
            "generator_outputs_mw": {
                gid: round(g.output_mw, 2) for gid, g in self.generators.items()
            },
        }


def telemetry_to_grid_state(tel: Telemetry) -> GridState:
    """Initialise a GridState from a Telemetry snapshot."""
    from rag_grid.sim.constraints import GEN_FRACTION

    buses = {bid: BusState(bus_id=bid, voltage_pu=v) for bid, v in tel.bus_voltages.items()}
    lines = {lid: LineState(line_id=lid, loading_pct=p) for lid, p in tel.line_loading_pct.items()}
    # Infer generators from total_gen_mw using the shared fleet-fraction constants.
    gen_max = {"G1": 300.0, "G2": 250.0, "G3": 200.0}
    generators = {
        gid: GeneratorState(
            gen_id=gid,
            output_mw=tel.total_gen_mw * frac,
            max_mw=gen_max.get(gid, 300.0),
        )
        for gid, frac in GEN_FRACTION.items()
    }
    return GridState(
        frequency_hz=tel.frequency_hz,
        total_load_mw=tel.total_load_mw,
        total_gen_mw=tel.total_gen_mw,
        spinning_reserve_mw=tel.spinning_reserve_mw,
        buses=buses,
        lines=lines,
        generators=generators,
    )


def _apply_action(state: GridState, action: Action) -> None:
    """Apply a single action to *state* in-place using linearised heuristics."""
    action_type = action.action_type.lower()
    target = action.target
    setpoint = action.setpoint

    if action_type == "dispatch":
        gen = state.generators.get(target)
        if gen is None:
            gen_name = target.split("_")[-1].upper()
            gen = state.generators.get(gen_name)
        if gen:
            delta_mw = setpoint - gen.output_mw
            gen.output_mw = max(gen.min_mw, min(gen.max_mw, setpoint))
            state.total_gen_mw += delta_mw
            state.spinning_reserve_mw -= delta_mw  # more dispatch = less reserve
            _update_frequency(state)
            _update_lines(state, delta_mw)

    elif action_type == "curtailment":
        gen = state.generators.get(target)
        if gen is None:
            gen_name = target.split("_")[-1].upper()
            gen = state.generators.get(gen_name)
        if gen:
            delta_mw = setpoint - gen.output_mw  # negative for curtailment
            gen.output_mw = max(gen.min_mw, min(gen.max_mw, setpoint))
            state.total_gen_mw += delta_mw
            state.spinning_reserve_mw -= delta_mw
            _update_frequency(state)
            _update_lines(state, delta_mw)

    elif action_type == "load_shedding":
        delta_mw = setpoint  # MW to shed (positive = load reduction)
        state.total_load_mw -= delta_mw
        _update_frequency(state)

    elif action_type == "frequency_support":
        # Governor adjustment — directly nudge frequency toward target
        target_hz = setpoint
        state.frequency_hz += (target_hz - state.frequency_hz) * 0.8

    elif action_type == "voltage_support":
        # Reactive injection into a bus
        bus = state.buses.get(target)
        if bus:
            # Treat setpoint as MVAr injection
            bus.voltage_pu = min(
                1.05, bus.voltage_pu + setpoint * _VOLT_DROOP_PU_PER_MVAR
            )

    else:
        logger.warning("Unknown action type '%s'; skipping.", action_type)


def _update_frequency(state: GridState) -> None:
    """Recompute frequency from power imbalance using linear droop model."""
    imbalance = state.total_gen_mw - state.total_load_mw  # MW surplus (+) or deficit (-)
    delta_f = imbalance / _FREQ_DROOP_MW_PER_HZ
    state.frequency_hz = 60.0 + delta_f
    # Clamp to physically reasonable range
    state.frequency_hz = max(58.0, min(62.0, state.frequency_hz))


def _update_lines(state: GridState, delta_gen_mw: float) -> None:
    """Adjust line loadings proportionally to generation change (heuristic)."""
    for line in state.lines.values():
        # More generation generally relieves loading (negative feedback)
        line.loading_pct = max(
            0.0, line.loading_pct - delta_gen_mw * _LINE_SENS
        )


# ── Public API ─────────────────────────────────────────────────────────────────


def simulate(plan: CommandPlan, initial_state: GridState) -> SimulationResult:
    """Run every approved step in *plan* through the toy model.

    Returns:
        :class:`~rag_grid.schema.SimulationResult` with before/after/delta.
    """
    before = initial_state.to_dict()
    state = deepcopy(initial_state)

    for step in plan.steps:
        if not step.approved:
            logger.info("Skipping unapproved step: %s", step.action.action_id)
            continue
        logger.info("Simulating action %s on %s", step.action.action_type, step.action.target)
        _apply_action(state, step.action)

    after = state.to_dict()

    # Compute delta for scalar fields.
    delta: dict[str, Any] = {}
    for key in ("frequency_hz", "total_load_mw", "total_gen_mw", "spinning_reserve_mw"):
        delta[key] = round(after[key] - before[key], 4)

    return SimulationResult(before=before, after=after, delta=delta)
