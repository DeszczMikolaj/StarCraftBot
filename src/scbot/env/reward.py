"""Reward function: terminal win/loss signal plus small shaping terms.

The weights live in :class:`scbot.config.RewardConfig`.
"""

from __future__ import annotations

from dataclasses import dataclass, fields

from scbot.config import RewardConfig


@dataclass(frozen=True)
class RewardCounters:
    """Cumulative game counters the shaping terms are derived from.

    Every field must have a weight of the same name in ``RewardConfig``.
    """

    marines_trained: float = 0.0
    workers_trained: float = 0.0
    value_killed: float = 0.0
    value_lost: float = 0.0


# Counter name -> name of its weight in RewardConfig.
_WEIGHT_NAMES: dict[str, str] = {
    "marines_trained": "marine_trained",
    "workers_trained": "worker_trained",
    "value_killed": "value_killed",
    "value_lost": "value_lost",
}
SHAPING_COMPONENTS: tuple[str, ...] = tuple(field.name for field in fields(RewardCounters))
TERMINAL_COMPONENT = "terminal"
REWARD_COMPONENTS: tuple[str, ...] = (*SHAPING_COMPONENTS, TERMINAL_COMPONENT)


class RewardTracker:
    """Turns cumulative counters into per-step rewards (one instance per episode)."""

    def __init__(self, config: RewardConfig) -> None:
        self._config = config
        self._previous = RewardCounters()

    def step(self, counters: RewardCounters) -> tuple[float, dict[str, float]]:
        """Reward for the change in counters since the previous call."""
        components: dict[str, float] = {}
        for name in SHAPING_COMPONENTS:
            delta = getattr(counters, name) - getattr(self._previous, name)
            components[name] = getattr(self._config, _WEIGHT_NAMES[name]) * delta
        components[TERMINAL_COMPONENT] = 0.0
        self._previous = counters
        return sum(components.values()), components

    def finish(self, counters: RewardCounters, result: str) -> tuple[float, dict[str, float]]:
        """Final reward: remaining shaping terms plus the terminal win/loss/tie reward."""
        terminal = {
            "Victory": self._config.win,
            "Defeat": self._config.loss,
            "Tie": self._config.tie,
        }.get(result, 0.0)
        _, components = self.step(counters)
        components[TERMINAL_COMPONENT] = terminal
        return sum(components.values()), components
