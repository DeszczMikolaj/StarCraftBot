"""python-sc2 bot that exposes the game as a sequence of macro decision points."""

from __future__ import annotations

from collections import Counter
from typing import Any

from sc2.bot_ai import BotAI
from sc2.data import Result
from sc2.ids.unit_typeid import UnitTypeId
from sc2.unit import Unit

from scbot.config import EnvConfig
from scbot.env.actions import ACTION_NAMES, NUM_ACTIONS, MacroAction
from scbot.env.bridge import DecisionBridge, StepData
from scbot.env.macro import ArmyMode, MacroExecutor
from scbot.env.observation import to_vector
from scbot.env.reward import REWARD_COMPONENTS, RewardCounters, RewardTracker


class MacroBot(BotAI):
    """Plays one game, asking ``bridge`` for a macro action every few game loops.

    At each decision point the bot reads the game state, hands the observation and the
    reward earned since the previous decision to the bridge, waits for the chosen
    action and passes it to the scripted macro layer.
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
        self._episode_return = 0.0
        self._reward_totals = dict.fromkeys(REWARD_COMPONENTS, 0.0)

    # ------------------------------------------------------------------ python-sc2 hooks

    async def on_start(self) -> None:
        self.client.game_step = self._config.game_step
        self._macro = MacroExecutor(self, self._config.macro)

    async def on_unit_created(self, unit: Unit) -> None:
        # Also fires once for every unit that exists at game start (the first 12 SCVs).
        self._units_trained[unit.type_id] += 1

    async def on_step(self, iteration: int) -> None:
        macro = self._require_macro()
        if iteration % self._config.decision_interval == 0:
            await self._decide(macro)
        await macro.housekeeping(iteration)

    async def on_end(self, game_result: Result) -> None:
        if self._macro is None:
            # The game ended before on_start finished; there is nothing to report.
            return
        result = game_result.name
        reward, components = self._rewards.finish(self._reward_counters(), result)
        self._account(reward, components)
        truncated = result == "Tie"  # only the game time limit produces a tie here
        info = self._info(components)
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

    async def _decide(self, macro: MacroExecutor) -> None:
        counters = self._reward_counters()
        if self._decisions == 0:
            # Baseline for the shaping terms: units present at game start earn nothing.
            self._rewards.step(counters)
            reward, components = 0.0, dict.fromkeys(REWARD_COMPONENTS, 0.0)
        else:
            reward, components = self._rewards.step(counters)
        self._account(reward, components)

        info = self._info(components)
        step = StepData(
            obs=to_vector(info["raw"]),
            reward=reward,
            terminated=False,
            truncated=False,
            info=info,
        )
        action = MacroAction(self._bridge.decide(step))

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

    def _info(self, reward_components: dict[str, float]) -> dict[str, Any]:
        macro = self._require_macro()
        return {
            "raw": self._read_raw(),
            "action_mask": macro.available_actions(),
            "reward_components": reward_components,
            "last_action_executed": self._last_action_executed,
            "game_loop": int(self.state.game_loop),
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
