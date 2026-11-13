"""Shared environment: observation vector, macro actions, reward, Gymnasium wrapper."""

from scbot.env.actions import ACTION_NAMES, NUM_ACTIONS, MacroAction
from scbot.env.observation import FEATURE_NAMES, FEATURES, OBS_DIM
from scbot.env.sc2_env import SC2EnvError, SC2MacroEnv

__all__ = [
    "ACTION_NAMES",
    "FEATURES",
    "FEATURE_NAMES",
    "NUM_ACTIONS",
    "OBS_DIM",
    "MacroAction",
    "SC2EnvError",
    "SC2MacroEnv",
]
