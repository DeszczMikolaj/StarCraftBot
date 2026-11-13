"""Reference agents without learning: uniform random and a hand-written build order.

They exist to validate the environment. The random agent exercises every action; the
scripted agent shows that the macro action set is enough to beat the built-in AI.
"""

from __future__ import annotations

import numpy as np

from scbot.agents.base import Agent
from scbot.env.actions import MacroAction
from scbot.env.observation import to_raw


class RandomAgent(Agent):
    """Picks uniformly among the actions that are currently available."""

    name = "random"

    def __init__(self, seed: int | None = None) -> None:
        self._rng = np.random.default_rng(seed)

    def act(self, obs: np.ndarray, action_mask: np.ndarray, *, explore: bool) -> int:
        return int(self._rng.choice(np.flatnonzero(action_mask)))


class ScriptedAgent(Agent):
    """Marine rush written by hand: economy first, then barracks, then attack in a group."""

    name = "scripted"

    def __init__(
        self,
        target_workers_per_base: int = 16,
        target_barracks: int = 4,
        attack_at_marines: int = 16,
        retreat_below_marines: int = 5,
    ) -> None:
        self.target_workers_per_base = target_workers_per_base
        self.target_barracks = target_barracks
        self.attack_at_marines = attack_at_marines
        self.retreat_below_marines = retreat_below_marines

    def act(self, obs: np.ndarray, action_mask: np.ndarray, *, explore: bool) -> int:
        raw = to_raw(obs)
        attacking = raw["army_attacking"] > 0.5
        barracks_total = raw["barracks"] + raw["barracks_pending"]
        depots_pending = raw["supply_depots_pending"]

        def wants(action: MacroAction, condition: bool) -> bool:
            return bool(condition) and bool(action_mask[action])

        if wants(MacroAction.ATTACK, raw["marines"] >= self.attack_at_marines):
            return MacroAction.ATTACK
        if wants(
            MacroAction.RETREAT,
            attacking and raw["marines"] < self.retreat_below_marines,
        ):
            return MacroAction.RETREAT

        # Keep supply ahead of production: the more barracks, the bigger the buffer.
        supply_buffer = 2 + 2 * raw["barracks"]
        if wants(
            MacroAction.BUILD_SUPPLY_DEPOT,
            raw["supply_left"] <= supply_buffer and depots_pending == 0,
        ):
            return MacroAction.BUILD_SUPPLY_DEPOT

        worker_target = self.target_workers_per_base * max(raw["townhalls"], 1)
        if wants(MacroAction.TRAIN_SCV, raw["workers"] < worker_target):
            return MacroAction.TRAIN_SCV
        if wants(MacroAction.BUILD_BARRACKS, barracks_total < self.target_barracks):
            return MacroAction.BUILD_BARRACKS
        if wants(MacroAction.TRAIN_MARINE, True):
            return MacroAction.TRAIN_MARINE
        if wants(
            MacroAction.EXPAND,
            barracks_total >= self.target_barracks and raw["townhalls"] < 2,
        ):
            return MacroAction.EXPAND
        return MacroAction.NO_OP
