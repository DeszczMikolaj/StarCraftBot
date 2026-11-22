"""What the ``info`` dictionary returned by ``reset`` and ``step`` contains.

The types below are ``TypedDict``s: at run time ordinary ``dict`` objects, as Gymnasium
expects, but mypy knows every key and the type of its value, so ``info["rwa"]`` or
``info["raw"] + 1`` is reported before the code runs. (A Java analogue: a record whose
fields are read with string keys that the compiler checks.)

A key gets its own field here when the code reads it by name. Values whose keys come
from a list and are usually iterated stay plain dicts: ``raw`` (keys from
``observation.FEATURE_NAMES``), ``reward_components`` and ``reward_totals`` (from
``reward.REWARD_COMPONENTS``) and ``action_counts`` (from ``actions.ACTION_NAMES``).
"""

from __future__ import annotations

from typing import NotRequired, TypedDict

import numpy as np
from numpy.typing import NDArray

# Written with the call syntax because "return" is a Python keyword and cannot be a
# field name in a class body.
GameSummary = TypedDict(
    "GameSummary",
    {
        "result": str,  # "Victory", "Defeat" or "Tie"
        "return": float,  # sum of all rewards in the game
        "reward_totals": dict[str, float],  # per reward component
        "decisions": int,
        "invalid_actions": int,  # chosen actions the macro layer could not carry out
        "game_minutes": float,
        "game_loop": int,
        "action_counts": dict[str, int],  # how often each macro action was chosen
        "score": float,  # the game's own score
        "collected_minerals": float,
        "spent_minerals": float,
        "marines_trained": int,
        "workers_trained": int,
    },
)
"""Summary of a finished game, in ``info["game_summary"]`` of the final step."""


class StepInfo(TypedDict):
    """``info`` of one decision point."""

    raw: dict[str, float]  # unscaled game readings, keyed by feature name
    action_mask: NDArray[np.bool_]  # True for every action that can be carried out now
    reward_components: dict[str, float]  # parts of the reward of this step
    last_action_executed: bool  # whether the previous action was carried out
    game_loop: int
    intervals_elapsed: float  # decision intervals since the previous decision point
    decision: int  # number of decisions made so far in this game
    result: NotRequired[str]  # final step only, same as ``game_summary["result"]``
    # Final step only. Not called "episode": Gymnasium's RecordEpisodeStatistics wrapper
    # writes its own statistics under that key and fails if the key is already there.
    game_summary: NotRequired[GameSummary]
