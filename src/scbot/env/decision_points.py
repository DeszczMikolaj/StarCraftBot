"""When the agent is asked for an action.

The game is checked once per decision interval, but asking the agent every time would
fill an episode with non-decisions: in about half of the intervals NO_OP is the only
available action, and "wait one interval" is almost indistinguishable from "act now",
which makes the two impossible to tell apart by their learned values.

So decision points are event-driven:

* no decision point while NO_OP is the only available action;
* NO_OP means "wait": the next decision point comes when an action the agent has not
  just declined becomes available, or after ``wait_intervals``;
* a decision point is forced after ``max_idle_intervals`` without one.
"""

from __future__ import annotations

import numpy as np


def decision_due(
    mask: np.ndarray,
    declined: np.ndarray | None,
    idle_intervals: float | None,
    *,
    wait_intervals: int,
    max_idle_intervals: int,
) -> bool:
    """Whether the agent should be asked for an action now.

    ``mask``: actions available now. ``declined``: the mask at the moment the agent last
    chose NO_OP, or None if its last action was something else. ``idle_intervals``:
    decision intervals since the previous decision point, None before the first one.
    """
    if idle_intervals is None:
        return True  # first decision of the game
    if idle_intervals >= max_idle_intervals:
        return True
    if mask.sum() <= 1:
        return False  # NO_OP is the only option: nothing to decide
    if declined is None:
        return True  # the previous action was not a wait
    if np.any(mask & ~declined):
        return True  # an option the agent has not yet declined became available
    return idle_intervals >= wait_intervals
