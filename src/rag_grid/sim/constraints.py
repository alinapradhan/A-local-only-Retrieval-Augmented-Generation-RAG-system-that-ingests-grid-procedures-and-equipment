"""Safety constraints: thresholds and rule-check helpers."""

from __future__ import annotations

from rag_grid.config import config


# ── Frequency ──────────────────────────────────────────────────────────────────

def check_frequency(freq_hz: float) -> list[str]:
    """Return a list of violation messages for *freq_hz*.

    An empty list means no violation.
    """
    violations: list[str] = []
    if freq_hz < config.freq_min_hz:
        violations.append(
            f"Under-frequency: {freq_hz:.3f} Hz < minimum {config.freq_min_hz} Hz."
        )
    elif freq_hz < config.freq_alert_low_hz:
        violations.append(
            f"Frequency alert (low): {freq_hz:.3f} Hz < alert threshold"
            f" {config.freq_alert_low_hz} Hz."
        )
    if freq_hz > config.freq_max_hz:
        violations.append(
            f"Over-frequency: {freq_hz:.3f} Hz > maximum {config.freq_max_hz} Hz."
        )
    elif freq_hz > config.freq_alert_high_hz:
        violations.append(
            f"Frequency alert (high): {freq_hz:.3f} Hz > alert threshold"
            f" {config.freq_alert_high_hz} Hz."
        )
    return violations


# ── Line loading ───────────────────────────────────────────────────────────────

def check_line_loading(line_id: str, loading_pct: float) -> list[str]:
    """Return violation messages for a single line."""
    violations: list[str] = []
    if loading_pct > config.line_max_pct:
        violations.append(
            f"Line {line_id} overloaded: {loading_pct:.1f}%"
            f" > thermal limit {config.line_max_pct}%."
        )
    elif loading_pct > config.line_warn_pct:
        violations.append(
            f"Line {line_id} approaching limit: {loading_pct:.1f}%"
            f" > warning threshold {config.line_warn_pct}%."
        )
    return violations


# ── Generator ramp ─────────────────────────────────────────────────────────────

def check_ramp(current_mw: float, requested_mw: float) -> list[str]:
    """Return violation messages if the ramp from *current_mw* to *requested_mw*
    exceeds the configured ramp-rate limit (MW per 5-minute interval).
    """
    delta = abs(requested_mw - current_mw)
    limit = config.ramp_rate_mw_per_5min
    if delta > limit:
        return [
            f"Ramp violation: requested change of {delta:.1f} MW exceeds"
            f" ramp-rate limit of {limit:.1f} MW/5-min."
        ]
    return []


# ── Load shedding cap ──────────────────────────────────────────────────────────

def check_load_shed(amount_mw: float) -> list[str]:
    """Return violation messages if load-shed amount exceeds the per-interval cap."""
    limit = config.max_load_shed_mw
    if amount_mw > limit:
        return [
            f"Load-shed amount {amount_mw:.1f} MW exceeds per-interval cap"
            f" of {limit:.1f} MW."
        ]
    return []


# ── Spinning reserve ───────────────────────────────────────────────────────────

def check_spinning_reserve(reserve_mw: float) -> list[str]:
    """Return violation messages if spinning reserve falls below minimum."""
    minimum = config.min_spinning_reserve_mw
    if reserve_mw < minimum:
        return [
            f"Spinning reserve {reserve_mw:.1f} MW below minimum {minimum:.1f} MW."
        ]
    return []


# ── Voltage ────────────────────────────────────────────────────────────────────

def check_voltage(bus_id: str, voltage_pu: float) -> list[str]:
    """Return violation messages for a per-unit bus voltage."""
    violations: list[str] = []
    if voltage_pu < config.volt_min_pu:
        violations.append(
            f"Bus {bus_id} under-voltage: {voltage_pu:.3f} pu"
            f" < {config.volt_min_pu} pu."
        )
    if voltage_pu > config.volt_max_pu:
        violations.append(
            f"Bus {bus_id} over-voltage: {voltage_pu:.3f} pu"
            f" > {config.volt_max_pu} pu."
        )
    return violations
