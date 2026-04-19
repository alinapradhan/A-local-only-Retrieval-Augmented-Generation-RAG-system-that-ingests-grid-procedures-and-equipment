"""Pydantic models for all data structures in the RAG Grid system."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class Chunk(BaseModel):
    """A document chunk with provenance metadata."""

    chunk_id: str
    source: str  # filename
    section: str  # heading under which the chunk lives
    text: str


class Telemetry(BaseModel):
    """A single telemetry snapshot from the grid."""

    timestamp: str
    total_load_mw: float
    total_gen_mw: float
    frequency_hz: float
    bus_voltages: dict[str, float] = Field(default_factory=dict)
    line_loading_pct: dict[str, float] = Field(default_factory=dict)
    spinning_reserve_mw: float


class Action(BaseModel):
    """A candidate control action proposed by the Planner agent."""

    action_id: str
    action_type: str  # dispatch | curtailment | load_shedding | voltage_support | frequency_support
    target: str  # generator/bus/line identifier
    setpoint: float
    unit: str  # MW | Hz | pu | %
    rationale: str
    cited_chunks: list[str] = Field(default_factory=list)  # chunk_ids


class SafetyResult(BaseModel):
    """Outcome of the Safety agent's evaluation of a single action."""

    action_id: str
    approved: bool
    violations: list[str] = Field(default_factory=list)
    alternatives: list[Action] = Field(default_factory=list)


class CommandStep(BaseModel):
    """One step in an approved command plan."""

    timestamp: str
    action: Action
    approved: bool
    requires_human_approval: bool = True


class CommandPlan(BaseModel):
    """The structured command plan ready for human review."""

    plan_id: str
    created_at: str
    goal: str
    steps: list[CommandStep] = Field(default_factory=list)
    human_approved: bool = False


class SimulationResult(BaseModel):
    """Before/after metrics from the toy grid simulation."""

    before: dict[str, Any] = Field(default_factory=dict)
    after: dict[str, Any] = Field(default_factory=dict)
    delta: dict[str, Any] = Field(default_factory=dict)


class FinalOutput(BaseModel):
    """Complete output object written to stdout / file."""

    retrieved_chunks: list[Chunk] = Field(default_factory=list)
    proposed_actions: list[Action] = Field(default_factory=list)
    safety_evaluation: list[SafetyResult] = Field(default_factory=list)
    approved_command_plan: CommandPlan
    simulation_result: SimulationResult | None = None
    final_explanation: str
