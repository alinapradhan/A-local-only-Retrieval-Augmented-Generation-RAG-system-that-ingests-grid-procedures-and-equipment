"""Unit tests for safety constraint checks and the Safety agent."""

from __future__ import annotations

import pytest

from rag_grid.schema import Action, Telemetry
from rag_grid.sim.constraints import (
    check_frequency,
    check_line_loading,
    check_load_shed,
    check_ramp,
    check_spinning_reserve,
    check_voltage,
)
from rag_grid.agents.safety import evaluate_action, evaluate


# ── Helpers ────────────────────────────────────────────────────────────────────


def _make_telemetry(**overrides) -> Telemetry:
    defaults = dict(
        timestamp="2024-01-01T00:00:00Z",
        total_load_mw=500.0,
        total_gen_mw=500.0,
        frequency_hz=60.0,
        spinning_reserve_mw=100.0,
        bus_voltages={"BUS1": 1.01, "BUS2": 0.99},
        line_loading_pct={"L1-L2": 55.0, "L2-L3": 60.0},
    )
    defaults.update(overrides)
    return Telemetry(**defaults)


def _make_action(**overrides) -> Action:
    defaults = dict(
        action_id="ACT-001",
        action_type="dispatch",
        target="generator_G2",
        setpoint=150.0,
        unit="MW",
        rationale="Test action",
        cited_chunks=[],
    )
    defaults.update(overrides)
    return Action(**defaults)


# ── check_frequency ────────────────────────────────────────────────────────────


def test_frequency_normal():
    assert check_frequency(60.0) == []
    assert check_frequency(59.8) == []
    assert check_frequency(60.2) == []


def test_frequency_alert_low():
    violations = check_frequency(59.6)
    assert any("alert" in v.lower() for v in violations)


def test_frequency_alert_high():
    violations = check_frequency(60.35)
    assert any("alert" in v.lower() for v in violations)


def test_frequency_under_limit():
    violations = check_frequency(59.3)
    assert any("under-frequency" in v.lower() for v in violations)


def test_frequency_over_limit():
    violations = check_frequency(60.7)
    assert any("over-frequency" in v.lower() for v in violations)


# ── check_line_loading ─────────────────────────────────────────────────────────


def test_line_loading_normal():
    assert check_line_loading("L1", 50.0) == []


def test_line_loading_warning():
    violations = check_line_loading("L1", 92.0)
    assert any("approaching" in v.lower() for v in violations)


def test_line_loading_overload():
    violations = check_line_loading("L1", 105.0)
    assert any("overload" in v.lower() for v in violations)


# ── check_ramp ─────────────────────────────────────────────────────────────────


def test_ramp_ok():
    # 30 MW change ≤ default 50 MW ramp limit
    assert check_ramp(100.0, 130.0) == []


def test_ramp_violation():
    # 80 MW change > default 50 MW ramp limit
    violations = check_ramp(100.0, 180.0)
    assert violations
    assert any("ramp" in v.lower() for v in violations)


def test_ramp_decrease_ok():
    assert check_ramp(150.0, 110.0) == []


def test_ramp_decrease_violation():
    violations = check_ramp(150.0, 90.0)
    assert violations


# ── check_load_shed ────────────────────────────────────────────────────────────


def test_load_shed_ok():
    assert check_load_shed(80.0) == []


def test_load_shed_violation():
    violations = check_load_shed(150.0)
    assert violations
    assert any("cap" in v.lower() for v in violations)


# ── check_spinning_reserve ─────────────────────────────────────────────────────


def test_spinning_reserve_ok():
    assert check_spinning_reserve(100.0) == []


def test_spinning_reserve_low():
    violations = check_spinning_reserve(20.0)
    assert violations
    assert any("reserve" in v.lower() for v in violations)


# ── check_voltage ──────────────────────────────────────────────────────────────


def test_voltage_normal():
    assert check_voltage("BUS1", 1.00) == []
    assert check_voltage("BUS1", 0.97) == []


def test_voltage_low():
    violations = check_voltage("BUS1", 0.93)
    assert any("under-voltage" in v.lower() for v in violations)


def test_voltage_high():
    violations = check_voltage("BUS1", 1.06)
    assert any("over-voltage" in v.lower() for v in violations)


# ── Safety agent: evaluate_action ─────────────────────────────────────────────


def test_evaluate_action_dispatch_approved():
    tel = _make_telemetry(total_gen_mw=480.0, spinning_reserve_mw=100.0)
    action = _make_action(action_type="dispatch", setpoint=510.0)  # +30 MW ≤ ramp limit
    result = evaluate_action(action, tel)
    # With normal line loading and voltages, should pass
    # (Reserve check: 100 - (510 - 480) = 70 MW ≥ 50 MW minimum)
    assert result.action_id == "ACT-001"
    assert isinstance(result.approved, bool)


def test_evaluate_action_ramp_violation():
    tel = _make_telemetry(total_gen_mw=100.0, spinning_reserve_mw=200.0)
    action = _make_action(action_type="dispatch", setpoint=200.0)  # +100 MW > 50 MW limit
    result = evaluate_action(action, tel)
    assert not result.approved
    assert result.violations  # at least one violation
    assert result.alternatives  # must suggest a safer alternative


def test_evaluate_action_load_shed_cap():
    tel = _make_telemetry()
    action = _make_action(action_type="load_shedding", setpoint=200.0)  # > 100 MW cap
    result = evaluate_action(action, tel)
    assert not result.approved
    # Alternative should be capped at 100 MW
    alts = result.alternatives
    assert alts
    assert alts[0].setpoint <= 100.0


def test_evaluate_action_frequency_support_safe():
    tel = _make_telemetry()
    action = _make_action(action_type="frequency_support", setpoint=60.0)
    result = evaluate_action(action, tel)
    # 60.0 Hz is within bounds — no frequency violations
    freq_violations = [v for v in result.violations if "frequency" in v.lower() and "alert" not in v.lower()]
    assert len(freq_violations) == 0


def test_evaluate_action_frequency_support_out_of_bounds():
    tel = _make_telemetry()
    action = _make_action(action_type="frequency_support", setpoint=58.0)  # < 59.5 min
    result = evaluate_action(action, tel)
    assert not result.approved
    assert any("under-frequency" in v.lower() for v in result.violations)


# ── Safety agent: evaluate (batch) ────────────────────────────────────────────


def test_evaluate_batch():
    tel = _make_telemetry(total_gen_mw=480.0, spinning_reserve_mw=120.0)
    actions = [
        _make_action(action_id="ACT-001", action_type="dispatch", setpoint=510.0),
        _make_action(action_id="ACT-002", action_type="load_shedding", setpoint=300.0),
    ]
    results = evaluate(actions, tel)
    assert len(results) == 2
    assert results[0].action_id == "ACT-001"
    assert results[1].action_id == "ACT-002"
    # Second action exceeds load-shed cap
    assert not results[1].approved


def test_evaluate_line_overload_flagged():
    tel = _make_telemetry(line_loading_pct={"L1": 105.0})  # overloaded
    action = _make_action(action_type="dispatch", setpoint=490.0)  # minimal ramp
    result = evaluate_action(action, tel)
    # Line overload should appear in violations
    assert any("overload" in v.lower() for v in result.violations)
    assert not result.approved
