# SECURITY.md — RAG Grid Operator Copilot

## Scope

This document describes security controls, operational safeguards, and known limitations of the
RAG Grid operator copilot system.

--- 

## Critical Safeguards

### 1. No Direct SCADA / Hardware Connection

**This software does NOT connect to any industrial control system, SCADA, DCS, RTU, or field  
device.** It reads only static telemetry files and outputs a human-readable "command plan" JSON.
Any integration with live systems must be performed by qualified personnel following site change-
management procedures and must include additional safety interlocks outside this software.

### 2. Human-in-the-Loop Mandatory

Every `CommandPlan` emitted by this system has `human_approved: false` by default. An authorized
grid operator must review and explicitly approve the plan before any setpoints are transmitted to
field equipment. Automated execution without human review is expressly prohibited.

### 3. Audit Trail

All runs write structured logs to `rag_grid_audit.log` (JSONL format) containing:
- ISO-8601 timestamp
- Operator goal
- Retrieved chunk IDs and sources
- Proposed actions and rationale
- Safety evaluation results (approvals and violations)
- Approved command plan

Do not delete or truncate audit logs. Retain per your site's regulatory requirements.

### 4. Logging & Confidentiality

- Do **not** log real SCADA credentials, device passwords, or grid topology secrets.
- If using a cloud LLM provider (OpenAI, etc.), be aware that prompts may include telemetry
  summaries. Ensure your data-sharing agreements permit this.
- Prefer running in `mock` mode or against a local/private LLM endpoint for sensitive topologies.

### 5. Dependency Supply-Chain

- Pin all dependency versions in production.
- Run `pip audit` or `safety check` before deploying new versions.
- FAISS and scikit-learn are the only compiled dependencies; verify their provenance.

---

## Safety Rule Summary

The built-in `SafetyAgent` enforces the following hard limits (configurable via env vars):

| Constraint | Default | Env Var |
|------------|---------|---------|
| Frequency lower bound | 59.5 Hz | `GRID_FREQ_MIN_HZ` |
| Frequency upper bound | 60.5 Hz | `GRID_FREQ_MAX_HZ` |
| Under-frequency alert | 59.7 Hz | `GRID_FREQ_ALERT_LOW_HZ` |
| Over-frequency alert | 60.3 Hz | `GRID_FREQ_ALERT_HIGH_HZ` |
| Line thermal limit | 100 % | `GRID_LINE_MAX_PCT` |
| Line pre-warning | 90 % | `GRID_LINE_WARN_PCT` |
| Generator ramp rate | 50 MW / 5-min | `GRID_RAMP_RATE_MW_PER_MIN` |
| Max load shed per interval | 100 MW | `GRID_MAX_LOAD_SHED_MW` |
| Min spinning reserve | 50 MW | `GRID_MIN_SPINNING_RESERVE_MW` |
| Min voltage (per unit) | 0.95 pu | `GRID_VOLT_MIN_PU` |
| Max voltage (per unit) | 1.05 pu | `GRID_VOLT_MAX_PU` |

These limits are checked **before** any action reaches the `CommandPlan`. Actions that violate
limits are either blocked or modified to a safe alternative.

---

## Known Limitations

1. The LLM (or mock stub) may produce plausible-sounding but incorrect power-systems advice.
   Always validate recommendations against official grid codes and operator training.
2. The toy grid model is a linearised approximation. It does not solve AC power flow.
3. Retrieval quality depends on the quality of ingested documents. Ensure your policy documents
   are up-to-date and authoritative.
4. No authentication or role-based access control is implemented in this CLI tool. Restrict
   filesystem access appropriately.

---

## Responsible Disclosure

If you discover a security vulnerability in this project, please open a GitHub Security Advisory
or contact the repository maintainer privately. Do not open a public issue for security bugs.
