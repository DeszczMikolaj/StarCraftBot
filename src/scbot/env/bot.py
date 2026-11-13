"""python-sc2 bot that exposes the game as a sequence of macro decision points."""

from __future__ import annotations

from collections import Counter
from typing import Any

import numpy as np
from sc2.bot_ai import BotAI
from sc2.data import Result
from sc2.ids.unit_typeid import UnitTypeId
from sc2.unit import Unit

from scbot.config import EnvConfig
from scbot.env.actions import ACTION_NAMES, NUM_ACTIONS, MacroAction
from scbot.env.bridge import DecisionBridge, StepData
from scbot.env.decision_points import decision_due
from scbot.env.macro import ArmyMode, MacroExecutor
from scbot.env.observation import to_vector
from scbot.env.reward import REWARD_COMPONENTS, RewardCounters, RewardTracker


class MacroBot(BotAI):
    """Plays one game, asking ``bridge`` for a macro action at every decision point.

    At a decision point the bot reads the game state, hands the observation and the
    reward earned since the previous decision to the bridge, waits for the chosen
    action and passes it to the scripted macro layer.

    Decision points are event-driven (see ``decision_points.py``): the agent is not
    asked when NO_OP is the only available action, and choosing NO_OP means waiting
    until a new option appears or ``wait_intervals`` have passed. The time between two
    decision points therefore varies; it is reported as ``info["intervals_elapsed"]``.
    """

    def __init__(self, bridge: DecisionBridge, config: EnvConfig) -> None:
        super().__init__()
        self._bridge = bridge
        self._config = config
        self._macro: MacroExecutor | None = None
        self._rewards = RewardTracker(config.reward)
        self._units_trained: Counter[UnitTypeId] = Counter()
        self._decisions = 0
        self._action_counts = [0] * NUM_ACTIONS
        self._invalid_actions = 0
        self._last_action_executed = True
        self._last_decision_loop: int | None = None
        self._declined_mask: np.ndarray | None = None  # options on offer at the last NO_OP
        self._episode_return = 0.0
        self._reward_totals = dict.fromkeys(REWARD_COMPONENTS, 0.0)

    # ------------------------------------------------------------------ python-sc2 hooks

    async def on_start(self) -> None:
        self.client.game_step = self._config.game_step
        self._macro = MacroExecutor(self, self._config.macro)

    async def on_unit_created(self, unit: Unit) -> None:
        # python-sc2 does not report the units that exist at game start (the 12 SCVs).
        self._units_trained[unit.type_id] += 1

    async def on_step(self, iteration: int) -> None:
        macro = self._require_macro()
        if iteration % self._config.decision_interval == 0:
            mask = macro.available_actions()
            if self._decision_due(mask):
                await self._decide(macro, mask)
        await macro.housekeeping(iteration)

    async def on_end(self, game_result: Result) -> None:
        if self._macro is None:
            # The game ended before on_start finished; there is nothing to report.
            return
        result = game_result.name
        reward, components = self._rewards.finish(self._reward_counters(), result)
        self._account(reward, components)
        truncated = result == "Tie"  # only the game time limit produces a tie here
        info = self._info(components, self._macro.available_actions())
        info["result"] = result
        info["episode"] = self._episode_summary(result)
        self._bridge.finish(
            StepData(
                obs=to_vector(info["raw"]),
                reward=reward,
                terminated=not truncated,
                truncated=truncated,
                info=info,
            )
        )

    # ------------------------------------------------------------------ decision point

    def _intervals_since_decision(self) -> float | None:
        """Game time since the previous decision point, in decision intervals."""
        if self._last_decision_loop is None:
            return None
        elapsed_loops = self.state.game_loop - self._last_decision_loop
        return elapsed_loops / self._config.loops_per_interval

    def _decision_due(self, mask: np.ndarray) -> bool:
        return decision_due(
            mask,
            self._declined_mask,
            self._intervals_since_decision(),
            wait_intervals=self._config.wait_intervals,
            max_idle_intervals=self._config.max_idle_intervals,
        )

    async def _decide(self, macro: MacroExecutor, mask: np.ndarray) -> None:
        counters = self._reward_counters()
        if self._decisions == 0:
            # Baseline for the shaping terms: units present at game start earn nothing.
            self._rewards.step(counters)
            reward, components = 0.0, dict.fromkeys(REWARD_COMPONENTS, 0.0)
        else:
            reward, components = self._rewards.step(counters)
        self._account(reward, components)

        info = self._info(components, mask)
        step = StepData(
            obs=to_vector(info["raw"]),
            reward=reward,
            terminated=False,
            truncated=False,
            info=info,
        )
        action = MacroAction(self._bridge.decide(step))

        self._last_decision_loop = int(self.state.game_loop)
        self._declined_mask = mask.copy() if action is MacroAction.NO_OP else None
        self._last_action_executed = await macro.execute(action)
        self._decisions += 1
        self._action_counts[action] += 1
        if not self._last_action_executed:
            self._invalid_actions += 1

    def _account(self, reward: float, components: dict[str, float]) -> None:
        self._episode_return += reward
        for name, value in components.items():
            self._reward_totals[name] += value

    # ------------------------------------------------------------------ game readings

    def _require_macro(self) -> MacroExecutor:
        if self._macro is None:
            raise RuntimeError("on_start has not run yet")
        return self._macro

    def _read_raw(self) -> dict[str, float]:
        """Raw game readings, keyed by the feature names in ``observation.FEATURES``."""
        macro = self._require_macro()
        barracks_ready = self.structures(UnitTypeId.BARRACKS).ready
        counters = self._reward_counters()
        return {
            "minerals": float(self.minerals),
            "vespene": float(self.vespene),
            "supply_used": float(self.supply_used),
            "supply_cap": float(self.supply_cap),
            "supply_left": float(max(self.supply_left, 0)),
            "workers": float(self.workers.amount),
            "idle_workers": float(self.workers.idle.amount),
            "townhalls": float(self.townhalls.ready.amount),
            "townhalls_pending": float(macro.pending_structures(UnitTypeId.COMMANDCENTER)),
            "supply_depots": float(macro.supply_depots.ready.amount),
            "supply_depots_pending": float(macro.pending_structures(UnitTypeId.SUPPLYDEPOT)),
            "barracks": float(barracks_ready.amount),
            "barracks_pending": float(macro.pending_structures(UnitTypeId.BARRACKS)),
            "barracks_idle": float(barracks_ready.idle.amount),
            "marines": float(self.units(UnitTypeId.MARINE).amount),
            "marines_pending": float(self.already_pending(UnitTypeId.MARINE)),
            "army_supply": float(self.supply_army),
            "army_attacking": float(macro.army_mode is ArmyMode.ATTACK),
            "enemy_units_visible": float(self.enemy_units.amount),
            "enemy_structures_known": float(self.enemy_structures.amount),
            "enemy_near_base": float(macro.threats().amount),
            "value_killed": counters.value_killed,
            "value_lost": counters.value_lost,
            "game_minutes": self.time / 60.0,
        }

    def _reward_counters(self) -> RewardCounters:
        score = self.state.score
        value_killed = score.killed_value_units + score.killed_value_structures
        value_lost = (
            score.lost_minerals_army
            + score.lost_minerals_economy
            + score.lost_minerals_technology
            + score.lost_minerals_none
            + score.lost_vespene_army
            + score.lost_vespene_economy
            + score.lost_vespene_technology
            + score.lost_vespene_none
        )
        return RewardCounters(
            marines_trained=float(self._units_trained[UnitTypeId.MARINE]),
            workers_trained=float(self._units_trained[UnitTypeId.SCV]),
            value_killed=float(value_killed),
            value_lost=float(value_lost),
        )

    def _info(self, reward_components: dict[str, float], mask: np.ndarray) -> dict[str, Any]:
        return {
            "raw": self._read_raw(),
            "action_mask": mask,
            "reward_components": reward_components,
            "last_action_executed": self._last_action_executed,
            "game_loop": int(self.state.game_loop),
            "intervals_elapsed": self._intervals_since_decision() or 0.0,
            "decision": self._decisions,
        }

    def _episode_summary(self, result: str) -> dict[str, Any]:
        score = self.state.score
        return {
            "result": result,
            "return": self._episode_return,
            "reward_totals": dict(self._reward_totals),
            "decisions": self._decisions,
            "invalid_actions": self._invalid_actions,
            "game_minutes": self.time / 60.0,
            "game_loop": int(self.state.game_loop),
            "action_counts": dict(zip(ACTION_NAMES, self._action_counts, strict=True)),
            "score": float(score.score),
            "collected_minerals": float(score.collected_minerals),
            "spent_minerals": float(score.spent_minerals),
            "marines_trained": int(self._units_trained[UnitTypeId.MARINE]),
            "workers_trained": int(self._units_trained[UnitTypeId.SCV]),
        }
