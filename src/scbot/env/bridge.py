"""Data exchanged between the in-game bot and whoever makes the decisions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import numpy as np


@dataclass
class StepData:
    """One decision point as seen by the agent (the Gymnasium ``step`` tuple)."""

    obs: np.ndarray
    reward: float
    terminated: bool
    truncated: bool
    info: dict[str, Any]


class DecisionBridge(Protocol):
    """How the bot hands a decision point over and gets the chosen action back."""

    def decide(self, step: StepData) -> int:
        """Called at every decision point; returns the index of the chosen macro action."""
        ...

    def finish(self, step: StepData) -> None:
        """Called once when the game is over, with the final observation and reward."""
        ...
