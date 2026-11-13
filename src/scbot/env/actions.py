"""Discrete macro action space shared by every agent (Terran vs Terran)."""

from __future__ import annotations

from enum import IntEnum


class MacroAction(IntEnum):
    """One high-level decision. The scripted layer in ``macro.py`` carries it out.

    The integer values are part of the agent interface (Q-table columns, network
    outputs). Append new actions at the end; never renumber existing ones.
    """

    NO_OP = 0
    TRAIN_SCV = 1
    BUILD_SUPPLY_DEPOT = 2
    BUILD_BARRACKS = 3
    TRAIN_MARINE = 4
    EXPAND = 5
    ATTACK = 6
    RETREAT = 7


NUM_ACTIONS: int = len(MacroAction)
ACTION_NAMES: tuple[str, ...] = tuple(action.name for action in MacroAction)
