# Equipment Limits and Ratings

## Generator Thermal and Ramp Limits

### Generator G1 — Large Thermal Unit (Coal/Gas Steam)
- **Rated capacity**: 300 MW
- **Minimum stable generation**: 90 MW (30% of rated)
- **Maximum continuous rating (MCR)**: 300 MW
- **Short-term emergency rating**: 315 MW (5% overload, max 30 min)
- **Ramp rate (increase)**: 20 MW/minute
- **Ramp rate (decrease)**: 25 MW/minute
- **Minimum up-time**: 4 hours
- **Minimum down-time**: 6 hours
- **Reactive capability**: +150 / -80 MVAr
- **Governor droop**: 4%
- **Governor dead-band**: ±0.036 Hz

### Generator G2 — Combined Cycle Gas Turbine (CCGT)
- **Rated capacity**: 250 MW
- **Minimum stable generation**: 100 MW (40% of rated)
- **Maximum continuous rating**: 250 MW
- **Short-term emergency rating**: 262 MW (max 15 min)
- **Ramp rate (increase)**: 15 MW/minute
- **Ramp rate (decrease)**: 20 MW/minute
- **Minimum up-time**: 2 hours
- **Minimum down-time**: 2 hours
- **Reactive capability**: +120 / -60 MVAr
- **Governor droop**: 5%

### Generator G3 — Renewable Integration Unit (Wind/Solar with Storage)
- **Rated capacity**: 200 MW
- **Minimum stable generation**: 0 MW (can curtail to zero)
- **Maximum continuous rating**: 200 MW (weather-dependent)
- **Ramp rate (increase)**: 50 MW/minute (limited by converter controls)
- **Ramp rate (decrease)**: 50 MW/minute
- **Reactive capability**: +80 / -50 MVAr (inverter-based, full range available)
- **Governor/synthetic inertia**: Virtual inertia mode available; activate via SCADA if frequency < 59.8 Hz

## Transmission Line Thermal Limits

### Summer Ratings (June–September)
| Line ID | From Bus | To Bus | Voltage (kV) | Normal Rating (MVA) | Emergency Rating (MVA) |
|---------|----------|--------|--------------|---------------------|------------------------|
| L1-L2   | BUS1     | BUS2   | 345          | 800                 | 880                    |
| L2-L3   | BUS2     | BUS3   | 345          | 700                 | 770                    |
| L3-L4   | BUS3     | BUS4   | 230          | 400                 | 440                    |
| L1-L4   | BUS1     | BUS4   | 345          | 900                 | 990                    |

### Winter Ratings (October–May)
| Line ID | Normal Rating (MVA) | Emergency Rating (MVA) |
|---------|---------------------|------------------------|
| L1-L2   | 880                 | 968                    |
| L2-L3   | 770                 | 847                    |
| L3-L4   | 440                 | 484                    |
| L1-L4   | 990                 | 1089                   |

### Line Loading Alert Levels
- **Pre-alert**: > 80% of normal thermal rating — inform system operator.
- **Alert**: > 90% of normal thermal rating — operator must identify and activate remedial action.
- **Critical**: > 100% of normal thermal rating — immediate action required; redispatch or topology change within 15 minutes.
- **Emergency**: > 110% of normal thermal rating — automatic protection may trip line within minutes.

### Thermal Limit Assumptions
Ratings assume:
- Ambient temperature: 35°C (summer) / 15°C (winter)
- Solar radiation: 1000 W/m² (summer) / 200 W/m² (winter)
- Wind speed: 0.6 m/s (conservative)
- Conductor type: ACSR Drake 477 kcmil (or equivalent)

## Transformer Limits

### T1 — 345/138 kV Auto-Transformer (BUS1–BUS3)
- **MVA rating**: 500 MVA (normal) / 550 MVA (emergency, max 4 hours)
- **Tap range**: ±8 steps of ±1.25% each (±10% total)
- **LTC dead-band**: ±0.5% voltage
- **Cooling**: OFAF; emergency OFAF cooling activates at 90% load

### T2 — 138/69 kV Transformer (BUS3–BUS4)
- **MVA rating**: 200 MVA (normal) / 220 MVA (emergency)
- **Tap range**: ±4 steps of ±2.5% each
- **LTC dead-band**: ±0.625%

## Protection Relay Settings

### Under-Frequency Load Shedding (UFLS) Scheme
| Stage | Frequency Threshold | Load to Shed |
|-------|---------------------|--------------|
| 1     | 59.3 Hz             | 10% of total load |
| 2     | 59.0 Hz             | 15% of total load |
| 3     | 58.7 Hz             | 20% of total load |
| 4     | 58.4 Hz             | 20% of total load |

### Over-Frequency Protection
- Generator trip at 60.6 Hz sustained for > 0.5 seconds.
- Second generator trip at 61.0 Hz sustained for > 0.1 seconds.

### Distance Protection (Transmission Lines)
- Zone 1: 80% of line impedance, instantaneous (< 20 ms).
- Zone 2: 120% of line impedance, time-delayed 0.3 s.
- Zone 3: 150% of line impedance, time-delayed 0.6 s.

## Spinning Reserve Allocation

### Reserve Requirements
- **Primary (governor response)**: ≥ 50 MW, must respond within 10 seconds.
- **Secondary (AGC)**: ≥ 100 MW, must respond within 10 minutes.
- **Tertiary (manual dispatch)**: ≥ 150 MW, must be available within 30 minutes.

### Reserve Sources
- G1: can provide up to 20 MW spinning reserve above current output.
- G2: can provide up to 30 MW spinning reserve above current output.
- G3 (when available): can provide up to 50 MW through inverter headroom.
- Demand response: up to 40 MW available with 5-minute activation.
