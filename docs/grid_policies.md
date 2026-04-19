# Grid Operating Policies

## Frequency Control Policy

### Normal Operating Band
The system frequency must be maintained within ±0.1 Hz of the nominal 60.0 Hz (i.e., between
59.9 Hz and 60.1 Hz) during normal operations. Sustained deviations outside this band require
immediate corrective action by the system operator.

### Alert Thresholds
- **Under-frequency alert**: Frequency < 59.7 Hz — operator must increase generation or reduce load.
- **Over-frequency alert**: Frequency > 60.3 Hz — operator must curtail generation or increase load.
- **Emergency under-frequency**: Frequency < 59.5 Hz — automatic under-frequency load shedding (UFLS) may activate.
- **Emergency over-frequency**: Frequency > 60.5 Hz — automatic generation trip protection may activate.

### Automatic Governor Response
All online generators must have active governor control enabled. The governor dead-band must not
exceed ±0.036 Hz. Generator output should respond to frequency deviations at a droop of 4–5%.

### Frequency Restoration
Following a frequency excursion, AGC (Automatic Generation Control) must restore frequency to
within the normal band within 10 minutes. If AGC cannot restore frequency within 5 minutes,
operators must manually dispatch additional generation or initiate emergency load shedding.

## Voltage Control Policy

### Operating Voltage Range
All transmission buses must operate within ±5% of nominal voltage (0.95–1.05 pu) under normal
conditions and within ±10% (0.90–1.10 pu) under emergency N-1 contingency conditions.

### Reactive Power Management
- Operators must ensure sufficient reactive reserve is maintained at each voltage control area.
- Capacitor banks may be switched in when bus voltage drops below 0.97 pu.
- Reactors must be switched in when bus voltage rises above 1.03 pu.
- Generator reactive power dispatch must remain within capability curve limits at all times.

### Voltage Emergency Actions
If a transmission bus voltage falls below 0.92 pu:
1. Immediately switch in available capacitor banks.
2. Increase generator reactive output (Q-injection).
3. If voltage does not recover within 2 minutes, consider controlled load shedding.

## Generation Dispatch Policy

### Merit Order Dispatch
Generators must be dispatched in economic merit order, subject to:
- Security constraints (line thermal limits, voltage limits, stability limits).
- Generator ramp rate limitations.
- Minimum generation requirements (must-run units).
- Environmental dispatch constraints.

### Ramp Rate Limits
No generator setpoint change should exceed the unit's maximum ramp rate:
- Thermal units: 10–30 MW/minute (see equipment_limits.md for per-unit values).
- Combined cycle: 5–15 MW/minute.
- Hydro units: up to 50 MW/minute.
- A single 5-minute dispatch instruction must not request more than 50 MW change per unit
  without prior confirmation of unit flexibility.

### Spinning Reserve Requirement
At all times, online spinning reserve must be ≥ 5% of total demand (and no less than 50 MW).
If spinning reserve falls below this threshold, operators must immediately:
1. Dispatch additional fast-response generation.
2. Pre-position interruptible load contracts for activation.
3. Alert neighboring control areas for potential emergency assistance.

## Load Shedding Policy

### Voluntary Load Reduction
Before any involuntary shedding, operators must:
1. Request voluntary load reduction from large industrial customers (demand response).
2. Activate interruptible service contracts.
3. Issue emergency energy conservation advisories.

### Involuntary Load Shedding (Emergency)
Load shedding blocks must be rotated equitably. Maximum shed per 5-minute interval is 100 MW
(approximately 10% of peak demand) to avoid cascade collapse. Priority loads (hospitals, emergency
services, water treatment) are exempt from shedding unless authorized by senior management.

### Post-Shedding Restoration
Load must be restored in reverse shedding order as soon as frequency returns above 59.7 Hz and
generation capacity is confirmed stable. Restoration rate: no more than 50 MW per 5-minute interval.

## N-1 Security Criteria

### Steady-State Security
The system must remain within thermal, voltage, and stability limits following any single
contingency (N-1). Operators must run security assessment software at least every 30 minutes
and after any significant topology change.

### Line Thermal Limits
- Normal operating limit (NOL): 100% of seasonal thermal rating.
- Emergency operating limit (EOL): 110% of seasonal thermal rating for up to 30 minutes.
- Lines loaded above 90% of their thermal rating must be treated as pre-contingency alerts.

### Contingency Response Time
After an N-1 contingency, operators have:
- 30 minutes to restore to N-1 secure state.
- 10 minutes for critical 345 kV and above lines.
