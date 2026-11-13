"""Interface every agent implements, whatever it learns with."""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np


class Agent(ABC):
    """Picks one macro action per decision point.

    ``act`` is the only method an agent must implement. Learning agents also override
    ``observe`` (called with every transition during training) and ``end_episode``.
    """

    name: str = "agent"

    @abstractmethod
    def act(self, obs: np.ndarray, action_mask: np.ndarray, *, explore: bool) -> int:
        """Choose an action.

        ``action_mask[a]`` is True when action ``a`` can be carried out right now.
        ``explore`` is True during training and False during evaluation.
        """

    def observe(
        self,
        obs: np.ndarray,
        action: int,
        reward: float,
        next_obs: np.ndarray,
        next_action_mask: np.ndarray,
        terminated: bool,
        intervals_elapsed: float = 1.0,
    ) -> None:
        """Learn from one transition.

        ``terminated`` is False when a game was only truncated by the time limit.
        ``intervals_elapsed`` is the game time between ``obs`` and ``next_obs`` in
        decision intervals. It varies from step to step, so discount the value of the
        next state with ``gamma ** intervals_elapsed``.
        """
        return None

    def end_episode(self) -> None:
        """Called after every training episode (e.g. to decay the exploration rate)."""
        return None
