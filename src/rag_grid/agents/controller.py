"""Controller agent: formats approved actions into a structured CommandPlan."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from rag_grid.schema import Action, CommandPlan, CommandStep, SafetyResult

logger = logging.getLogger(__name__)


def build_command_plan(
    goal: str,
    actions: list[Action],
    safety_results: list[SafetyResult],
) -> CommandPlan:
    """Assemble a :class:`~rag_grid.schema.CommandPlan` from evaluated actions.

    Approved actions become steps in the plan.  Blocked actions whose safety
    result includes alternatives will have the first alternative substituted.

    Args:
        goal:           The operator's goal statement.
        actions:        Proposed actions from the Planner.
        safety_results: Per-action safety evaluations.

    Returns:
        A ``CommandPlan`` with ``human_approved=False``; an operator must set
        this to ``True`` before any setpoint is transmitted to field equipment.
    """
    now = datetime.now(tz=timezone.utc).isoformat()
    plan_id = f"PLAN-{uuid.uuid4().hex[:8].upper()}"

    # Build a map for fast lookup.
    result_map: dict[str, SafetyResult] = {r.action_id: r for r in safety_results}

    steps: list[CommandStep] = []
    for action in actions:
        result = result_map.get(action.action_id)

        if result is None:
            # No safety evaluation — skip (should not happen in normal flow).
            logger.warning("No safety result for %s; skipping.", action.action_id)
            continue

        if result.approved:
            step_action = action
            approved = True
        elif result.alternatives:
            # Use the first (most conservative) safe alternative.
            step_action = result.alternatives[0]
            approved = True
            logger.info(
                "Substituting safe alternative for %s.", action.action_id
            )
        else:
            # Completely blocked — include in plan as unapproved for audit trail.
            step_action = action
            approved = False
            logger.warning("Action %s is blocked with no alternative.", action.action_id)

        steps.append(
            CommandStep(
                timestamp=now,
                action=step_action,
                approved=approved,
                requires_human_approval=True,
            )
        )

    plan = CommandPlan(
        plan_id=plan_id,
        created_at=now,
        goal=goal,
        steps=steps,
        human_approved=False,  # Always False — operator must approve.
    )
    logger.info(
        "CommandPlan %s: %d steps (%d approved).",
        plan_id,
        len(steps),
        sum(1 for s in steps if s.approved),
    )
    return plan
