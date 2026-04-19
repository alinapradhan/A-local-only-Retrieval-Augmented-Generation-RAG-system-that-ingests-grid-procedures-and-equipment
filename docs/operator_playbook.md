# Operator Playbook — Power Grid Emergency and Normal Procedures

## Overview

This playbook provides step-by-step procedures for common operating scenarios. All actions must
be logged in the Energy Management System (EMS). When in doubt, consult the senior system
operator or escalate to the control room supervisor.

> **SAFETY NOTICE**: This playbook is for guidance only. Field conditions may require deviation
> from standard procedures. Always prioritise personnel and equipment safety over system economics.

## Generation Dispatch Procedures

### Normal Dispatch (Economic Merit Order)
1. Review load forecast for the next dispatch interval (typically 5 minutes).
2. Check spinning reserve position against requirements in equipment_limits.md.
3. If reserve is adequate, dispatch in economic merit order: G3 (renewable, zero marginal cost) → G2 (CCGT) → G1 (thermal).
4. Submit dispatch instructions to generators via AGC or manual phone confirmation.
5. Monitor generator response for 2 minutes; if output has not moved as instructed, call the plant operator.
6. Log all dispatch changes in the EMS with timestamp, reason, and target setpoint.

### Manual Dispatch Override
Used when AGC is unavailable or security constraints require manual control:
1. Notify the supervisor that manual dispatch is active.
2. Calculate required generation change: ΔP = P_load - P_gen + Reserve_target.
3. Prioritise fast-responding units (G2, G3) for frequency control.
4. Do not exceed ramp limits listed in equipment_limits.md.
5. Restore AGC as soon as conditions permit.

## Frequency Restoration Procedures

### Procedure FR-01: Frequency Below 59.7 Hz

**Trigger**: Frequency < 59.7 Hz sustained for > 30 seconds.

**Steps**:
1. Announce on EMS intercom: "Under-frequency event — all operators stand by."
2. Identify generation deficit: ΔP = (60.0 - f) × D, where D ≈ 200 MW/Hz.
3. Dispatch available spinning reserve immediately:
   - Request G2 to increase output to maximum continuous rating.
   - Request G3 to activate synthetic inertia mode (if available).
   - Request G1 to increase output at maximum ramp rate.
4. If frequency < 59.5 Hz, prepare for UFLS activation and notify distribution operators.
5. Document event in EMS; submit Event Report within 1 hour.

### Procedure FR-02: Frequency Above 60.3 Hz

**Trigger**: Frequency > 60.3 Hz sustained for > 30 seconds.

**Steps**:
1. Identify generation surplus: ΔP = (f - 60.0) × D.
2. Curtail cheapest online generation first (economic merit order reverse):
   - Curtail G1 toward minimum stable generation (90 MW).
   - Curtail G2 if G1 curtailment is insufficient.
   - Curtail G3 as a last resort (renewable energy loss).
3. If frequency > 60.5 Hz, activate interruptible load contracts to absorb surplus.
4. If automatic over-frequency protection trips a generator, assess N-1 security.
5. Document event in EMS.

### Procedure FR-03: Large Frequency Disturbance (> 0.5 Hz deviation)

**Trigger**: Frequency falls below 59.5 Hz or rises above 60.5 Hz.

**Steps**:
1. Declare "Grid Emergency" to all operators and supervisor.
2. Execute FR-01 or FR-02 simultaneously.
3. Monitor UFLS relay status; co-ordinate with distribution operators.
4. Contact neighbouring control areas for emergency energy exchange.
5. Post-event: preserve all EMS logs and relay records; initiate formal incident investigation.

## Voltage Support Procedures

### Procedure VS-01: Low Voltage (< 0.97 pu)

**Trigger**: Any transmission bus voltage < 0.97 pu for > 1 minute.

**Steps**:
1. Switch in available capacitor banks at or near the affected bus.
2. Increase reactive output (MVAr) from generators in the affected voltage zone.
3. If voltage does not recover to > 0.98 pu within 2 minutes, consider transformer tap adjustment.
4. If voltage < 0.94 pu, initiate controlled load shedding in the affected area.
5. Log all equipment operations with timestamps.

### Procedure VS-02: High Voltage (> 1.03 pu)

**Trigger**: Any transmission bus voltage > 1.03 pu for > 1 minute.

**Steps**:
1. Switch in available reactors at or near the affected bus.
2. Reduce reactive output from generators (absorb MVAr).
3. If voltage > 1.05 pu, check for unnecessary capacitor bank switching.
4. If voltage > 1.07 pu, reduce generation in the affected zone or open lightly loaded lines.

## Line Overload Procedures

### Procedure LO-01: Line Loading > 90% (Pre-Alert)

**Trigger**: Any line loading > 90% of thermal rating.

**Steps**:
1. Log alert in EMS.
2. Identify alternative power flow paths via generation redispatch or switching.
3. Notify generators that a redispatch instruction may be issued within 15 minutes.
4. Run N-1 security assessment to check contingency loading.

### Procedure LO-02: Line Loading > 100% (Emergency)

**Trigger**: Any line loading > 100% of thermal rating.

**Steps**:
1. Immediately redispatch generation to relieve line loading:
   - Reduce generation behind the overloaded line.
   - Increase generation in front of the overloaded line.
2. If redispatch is insufficient, open parallel paths if available.
3. If loading > 110%, prepare for possible automatic relay operation.
4. Notify line owner and document all actions in EMS.

## Load Shedding Procedures

### Procedure LS-01: Voluntary Load Reduction

**Trigger**: Spinning reserve < 50 MW or frequency < 59.7 Hz and generation at maximum.

**Steps**:
1. Activate demand response contracts (notify customers via automated system).
2. Issue Emergency Conservation Advisory via public communications system.
3. Request large industrial customers (> 5 MW) to voluntarily reduce by 10%.

### Procedure LS-02: Involuntary Emergency Load Shedding

**Trigger**: Frequency < 59.5 Hz and LS-01 has not restored frequency within 2 minutes.

**Steps**:
1. Shed Block A (non-critical residential/commercial): up to 100 MW.
2. Wait 2 minutes; assess frequency recovery.
3. If frequency < 59.3 Hz, shed Block B (additional 100 MW).
4. Continue in 2-minute intervals until frequency recovers.
5. Never shed priority loads (hospitals, emergency services) without explicit supervisor approval.
6. Document customer numbers, MW shed, and times in EMS.

### Load Restoration After Shedding
1. Frequency must be > 59.7 Hz and stable for > 2 minutes before restoration.
2. Restore in reverse shed order (Block B first, then Block A).
3. Restore no more than 50 MW per 5-minute interval.
4. Monitor frequency and line loading after each restoration step.

## Switching and Topology Changes

### Pre-Switching Checklist
Before any switching operation:
- [ ] Run security assessment with proposed topology.
- [ ] Confirm all protection relays will remain correctly configured.
- [ ] Verify no maintenance tags or safety grounds are in place.
- [ ] Obtain approval from senior operator.
- [ ] Notify affected generators and distribution operators.

### Post-Switching Verification
After switching:
- Verify expected changes in power flow and voltage using EMS SCADA displays.
- Confirm protection relay status is correct for new topology.
- Log all switching operations with timestamps and operator ID.

## Communication and Escalation

### Internal Escalation
- Operator → Senior Operator: any event requiring load shedding or emergency dispatch.
- Senior Operator → Control Room Supervisor: any grid emergency or UFLS activation.
- Control Room Supervisor → Management: any event with customer impact > 5 minutes.

### External Communication
- Neighbouring control areas: mandatory notification within 5 minutes of a grid emergency.
- Generator operators: direct phone or EMS messaging for all dispatch changes.
- Distribution operators: notification of any transmission voltage issues.
- Regulatory body: incident report within 24 hours for any UFLS activation or customer interruption.
