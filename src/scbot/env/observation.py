"""Observation vector shared by every agent.

The environment returns a fixed-length ``float32`` vector. Each entry is a raw game
quantity divided by a per-feature scale, so typical values fall in ``[0, 1]``; the
result is clipped to ``[0, OBS_CLIP]``.

``FEATURES`` is the single source of truth: its order defines the vector layout.
Append new features at the end so existing agents keep working.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Feature:
    name: str
    scale: float
    description: str


FEATURES: tuple[Feature, ...] = (
    Feature("minerals", 1000.0, "Unspent minerals"),
    Feature("vespene", 1000.0, "Unspent vespene gas"),
    Feature("supply_used", 200.0, "Supply in use"),
    Feature("supply_cap", 200.0, "Supply limit"),
    Feature("supply_left", 20.0, "Free supply (cap - used)"),
    Feature("workers", 50.0, "SCVs alive"),
    Feature("idle_workers", 10.0, "SCVs without orders"),
    Feature("townhalls", 4.0, "Finished Command Centers"),
    Feature("townhalls_pending", 2.0, "Command Centers ordered or under construction"),
    Feature("supply_depots", 20.0, "Finished Supply Depots"),
    Feature("supply_depots_pending", 4.0, "Supply Depots ordered or under construction"),
    Feature("barracks", 8.0, "Finished Barracks"),
    Feature("barracks_pending", 4.0, "Barracks ordered or under construction"),
    Feature("barracks_idle", 8.0, "Finished Barracks with an empty queue"),
    Feature("marines", 100.0, "Marines alive"),
    Feature("marines_pending", 16.0, "Marines in production"),
    Feature("army_supply", 100.0, "Supply used by the army"),
    Feature("army_attacking", 1.0, "1 when the army is in attack mode, 0 when defending"),
    Feature("enemy_units_visible", 50.0, "Enemy units currently visible"),
    Feature("enemy_structures_known", 20.0, "Enemy structures visible or remembered"),
    Feature("enemy_near_base", 20.0, "Enemy units close to one of our structures"),
    Feature("value_killed", 5000.0, "Resources' worth of enemy units and structures destroyed"),
    Feature("value_lost", 5000.0, "Resources' worth of own units and structures lost"),
    Feature("game_minutes", 20.0, "Elapsed game time in minutes"),
)

FEATURE_NAMES: tuple[str, ...] = tuple(feature.name for feature in FEATURES)
FEATURE_INDEX: dict[str, int] = {name: index for index, name in enumerate(FEATURE_NAMES)}
FEATURE_SCALES: np.ndarray = np.array([feature.scale for feature in FEATURES], dtype=np.float64)
OBS_DIM: int = len(FEATURES)
OBS_CLIP: float = 2.0


def to_vector(raw: Mapping[str, float]) -> np.ndarray:
    """Turn raw game readings (keyed by feature name) into the observation vector."""
    missing = [name for name in FEATURE_NAMES if name not in raw]
    if missing:
        raise KeyError(f"missing observation features: {missing}")
    values = np.array([raw[name] for name in FEATURE_NAMES], dtype=np.float64)
    return np.clip(values / FEATURE_SCALES, 0.0, OBS_CLIP).astype(np.float32)


def to_raw(obs: np.ndarray) -> dict[str, float]:
    """Invert :func:`to_vector` (exact unless a value was clipped)."""
    if obs.shape != (OBS_DIM,):
        raise ValueError(f"expected observation of shape ({OBS_DIM},), got {obs.shape}")
    # float32 round trip leaves errors around 1e-4 on the largest scales; readings are
    # integers or coarse fractions, so rounding restores them exactly.
    values = np.round(obs.astype(np.float64) * FEATURE_SCALES, 3)
    return dict(zip(FEATURE_NAMES, values.tolist(), strict=True))
