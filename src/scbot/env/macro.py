"""Scripted layer that turns macro actions into python-sc2 unit commands (Terran).

Every agent shares this layer, so differences between agents come from *which* macro
action they pick, not from how well it is carried out. The layer has three jobs:

* ``available_actions`` - which actions can be carried out right now (the action mask);
* ``execute`` - carry out one macro action (choose the worker, the building spot, ...);
* ``housekeeping`` - upkeep between decisions (idle workers, unfinished buildings,
  basic army control).
"""

from __future__ import annotations

from enum import IntEnum
from typing import TYPE_CHECKING

import numpy as np
from sc2.ids.ability_id import AbilityId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.position import Point2
from sc2.units import Units

from scbot.config import GAME_LOOPS_PER_SECOND, MacroConfig
from scbot.env.actions import NUM_ACTIONS, MacroAction

if TYPE_CHECKING:
    from sc2.bot_ai import BotAI

DEPOT_TYPES = {UnitTypeId.SUPPLYDEPOT, UnitTypeId.SUPPLYDEPOTLOWERED}
NON_ARMY_TYPES = {UnitTypeId.SCV, UnitTypeId.MULE}

# Distance from the Command Center (towards the map centre) around which buildings are placed.
DEPOT_ANCHOR_DISTANCE = 5.0
BARRACKS_ANCHOR_DISTANCE = 11.0
# Grid step of the placement search: leaves walking room between neighbouring buildings.
DEPOT_PLACEMENT_STEP = 3
BARRACKS_PLACEMENT_STEP = 5
# How close the army has to get before a location counts as checked.
TARGET_REACHED_DISTANCE = 5.0
REGROUP_DISTANCE = 6.0


class ArmyMode(IntEnum):
    DEFEND = 0  # wait at the rally point, engage enemies that come near our bases
    ATTACK = 1  # attack-move towards the enemy


class MacroExecutor:
    """Executes macro actions for one bot during one game."""

    def __init__(self, bot: BotAI, config: MacroConfig) -> None:
        self.bot = bot
        self.config = config
        self.army_mode = ArmyMode.DEFEND
        self._mode_changed = False
        self._mode_changed_loop: int | None = None
        self._search_targets: list[Point2] = []
        self._search_index = 0
        self._searching = False

    # ------------------------------------------------------------------ queries

    @property
    def army(self) -> Units:
        return self.bot.units.exclude_type(NON_ARMY_TYPES)

    @property
    def supply_depots(self) -> Units:
        return self.bot.structures.of_type(DEPOT_TYPES)

    def pending_structures(self, unit_type: UnitTypeId) -> int:
        """Structures of this type under construction plus SCVs on their way to start one."""
        under_construction = self.bot.structures(unit_type).not_ready.amount
        return under_construction + int(self.bot.worker_en_route_to_build(unit_type))

    def threats(self) -> Units:
        """Enemy units close to one of our structures."""
        bot = self.bot
        structures = bot.structures
        if not structures or not bot.enemy_units:
            return Units([], bot)
        radius = self.config.defend_radius
        return bot.enemy_units.filter(lambda enemy: structures.closest_distance_to(enemy) < radius)

    def army_mode_locked(self) -> bool:
        """True while the last ATTACK/RETREAT order is too recent to be reversed."""
        if self._mode_changed_loop is None:
            return False
        elapsed_loops = self.bot.state.game_loop - self._mode_changed_loop
        return elapsed_loops < self.config.army_mode_commit_seconds * GAME_LOOPS_PER_SECOND

    def rally_point(self) -> Point2:
        """Where the army waits: in front of the base closest to the enemy."""
        bot = self.bot
        enemy_start = bot.enemy_start_locations[0]
        if bot.townhalls:
            anchor = bot.townhalls.closest_to(enemy_start).position
        else:
            anchor = bot.start_location
        return anchor.towards(bot.game_info.map_center, self.config.rally_distance)

    def available_actions(self) -> np.ndarray:
        """Boolean mask over ``MacroAction``: True where the action can be carried out now."""
        bot, cfg = self.bot, self.config
        mask = np.zeros(NUM_ACTIONS, dtype=bool)
        mask[MacroAction.NO_OP] = True

        ready_townhalls = bot.townhalls.ready
        worker_count = bot.workers.amount

        if ready_townhalls.idle and bot.can_afford(UnitTypeId.SCV):
            worker_limit = min(
                cfg.max_workers, cfg.max_workers_per_townhall * ready_townhalls.amount
            )
            planned_workers = worker_count + bot.already_pending(UnitTypeId.SCV)
            mask[MacroAction.TRAIN_SCV] = planned_workers < worker_limit

        if worker_count and bot.townhalls:
            mask[MacroAction.BUILD_SUPPLY_DEPOT] = (
                bot.supply_cap < 200
                and bot.can_afford(UnitTypeId.SUPPLYDEPOT)
                and self.pending_structures(UnitTypeId.SUPPLYDEPOT) < cfg.max_pending_supply_depots
            )

            barracks_pending = self.pending_structures(UnitTypeId.BARRACKS)
            barracks_total = bot.structures(UnitTypeId.BARRACKS).ready.amount + barracks_pending
            mask[MacroAction.BUILD_BARRACKS] = (
                barracks_total < cfg.max_barracks
                and barracks_pending < cfg.max_pending_barracks
                and bool(self.supply_depots.ready)  # tech requirement
                and bot.can_afford(UnitTypeId.BARRACKS)
            )

            mask[MacroAction.EXPAND] = (
                bot.townhalls.amount < cfg.max_townhalls
                and self.pending_structures(UnitTypeId.COMMANDCENTER) == 0
                and bot.can_afford(UnitTypeId.COMMANDCENTER)
            )

        mask[MacroAction.TRAIN_MARINE] = bool(
            bot.structures(UnitTypeId.BARRACKS).ready.idle
        ) and bot.can_afford(UnitTypeId.MARINE)

        if not self.army_mode_locked():
            if self.army_mode is ArmyMode.DEFEND:
                mask[MacroAction.ATTACK] = bool(self.army)
            else:
                mask[MacroAction.RETREAT] = True
        return mask

    # ------------------------------------------------------------------ actions

    async def execute(self, action: MacroAction) -> bool:
        """Carry out one macro action. Returns False when nothing was done."""
        if not self.available_actions()[action]:
            return False
        if action is MacroAction.NO_OP:
            return True
        if action is MacroAction.TRAIN_SCV:
            idle_townhalls = self.bot.townhalls.ready.idle.amount
            return self.bot.train(UnitTypeId.SCV, amount=idle_townhalls) > 0
        if action is MacroAction.TRAIN_MARINE:
            idle_barracks = self.bot.structures(UnitTypeId.BARRACKS).ready.idle.amount
            return self.bot.train(UnitTypeId.MARINE, amount=idle_barracks) > 0
        if action is MacroAction.BUILD_SUPPLY_DEPOT:
            return await self.bot.build(
                UnitTypeId.SUPPLYDEPOT,
                near=self._build_anchor(DEPOT_ANCHOR_DISTANCE),
                placement_step=DEPOT_PLACEMENT_STEP,
            )
        if action is MacroAction.BUILD_BARRACKS:
            return await self.bot.build(
                UnitTypeId.BARRACKS,
                near=self._build_anchor(BARRACKS_ANCHOR_DISTANCE),
                placement_step=BARRACKS_PLACEMENT_STEP,
            )
        if action is MacroAction.EXPAND:
            return await self._expand()
        if action is MacroAction.ATTACK:
            self._set_army_mode(ArmyMode.ATTACK)
            return True
        if action is MacroAction.RETREAT:
            self._set_army_mode(ArmyMode.DEFEND)
            return True
        raise ValueError(f"unhandled macro action: {action!r}")

    def _build_anchor(self, distance: float) -> Point2:
        """Point near the main base around which new buildings are placed."""
        bot = self.bot
        townhalls = bot.townhalls.ready or bot.townhalls
        if townhalls:
            base = townhalls.closest_to(bot.start_location).position
        else:
            base = bot.start_location
        return base.towards(bot.game_info.map_center, distance)

    async def _expand(self) -> bool:
        location = await self.bot.get_next_expansion()
        if location is None:
            return False
        return await self.bot.build(
            UnitTypeId.COMMANDCENTER,
            near=location,
            max_distance=10,
            random_alternative=False,
            placement_step=1,
        )

    def _set_army_mode(self, mode: ArmyMode) -> None:
        self.army_mode = mode
        self._mode_changed = True
        self._mode_changed_loop = int(self.bot.state.game_loop)
        self._searching = False

    # ------------------------------------------------------------------ upkeep

    async def housekeeping(self, iteration: int) -> None:
        """Run on every bot step, after the agent's action (if any) was executed."""
        if iteration % self.config.housekeeping_interval == 0:
            await self.bot.distribute_workers()
            self._resume_abandoned_constructions()
            self._lower_supply_depots()
        self._control_army(iteration)

    def _resume_abandoned_constructions(self) -> None:
        """Send an SCV to buildings whose builder was killed or pulled away."""
        bot = self.bot
        for structure in bot.structures_without_construction_SCVs:
            worker = bot.select_build_worker(structure.position)
            if worker is not None:
                worker.smart(structure)

    def _lower_supply_depots(self) -> None:
        """Raised depots block movement inside the base."""
        for depot in self.bot.structures(UnitTypeId.SUPPLYDEPOT).ready:
            depot(AbilityId.MORPH_SUPPLYDEPOT_LOWER)

    def _control_army(self, iteration: int) -> None:
        army = self.army
        mode_changed, self._mode_changed = self._mode_changed, False
        if not army:
            return
        refresh = mode_changed or iteration % self.config.retarget_interval == 0

        if self.army_mode is ArmyMode.ATTACK:
            target = self._attack_target(army)
            for unit in army:
                if refresh or unit.is_idle:
                    unit.attack(target)
            return

        rally = self.rally_point()
        if mode_changed:  # retreat: walk home without stopping to fight
            for unit in army:
                unit.move(rally)
            return

        threats = self.threats()
        if threats:
            for unit in army:
                if refresh or unit.is_idle or unit.is_moving:
                    unit.attack(threats.closest_to(unit).position)
            return

        for unit in army.idle:
            if unit.distance_to(rally) > REGROUP_DISTANCE:
                unit.move(rally)

    def _attack_target(self, army: Units) -> Point2:
        """Nearest known enemy structure, else the enemy start, else sweep the expansions."""
        bot = self.bot
        enemy_structures = bot.enemy_structures
        if enemy_structures:
            self._searching = False
            return enemy_structures.closest_to(army.center).position

        enemy_start = bot.enemy_start_locations[0]
        if not self._searching:
            if army.closest_distance_to(enemy_start) > TARGET_REACHED_DISTANCE:
                return enemy_start
            # The enemy main is empty: look for hidden buildings at the expansions.
            self._search_targets = sorted(
                bot.expansion_locations_list, key=lambda p: p.distance_to(enemy_start)
            )
            self._search_index = 0
            self._searching = True

        if not self._search_targets:
            return enemy_start
        target = self._search_targets[self._search_index]
        if army.closest_distance_to(target) < TARGET_REACHED_DISTANCE:
            self._search_index = (self._search_index + 1) % len(self._search_targets)
            target = self._search_targets[self._search_index]
        return target
