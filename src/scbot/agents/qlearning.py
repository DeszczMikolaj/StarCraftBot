"""Model A: classic tabular Q-learning (no neural network).

The continuous observation vector is reduced to a small discrete state by putting a
handful of features into buckets. The Q-table maps each visited state to one value per
macro action and is updated with the one-step Q-learning rule

    Q(s, a) <- Q(s, a) + alpha * (r + gamma * max_a' Q(s', a') - Q(s, a))

where the maximum runs over the actions available in ``s'``.
"""

from __future__ import annotations

import json
import math
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from scbot.agents.base import Agent
from scbot.env.actions import ACTION_NAMES, NUM_ACTIONS
from scbot.env.observation import FEATURE_INDEX, FEATURE_SCALES

State = tuple[int, ...]
TABLE_FORMAT_VERSION = 1


@dataclass(frozen=True)
class BinSpec:
    """Buckets for one observation feature.

    ``edges`` are ascending thresholds in raw game units. A value ``v`` falls into
    bucket ``i`` when ``edges[i-1] <= v < edges[i]``, so ``n`` edges give ``n + 1`` buckets.
    """

    feature: str
    edges: tuple[float, ...]

    def __post_init__(self) -> None:
        if self.feature not in FEATURE_INDEX:
            raise ValueError(f"unknown observation feature: {self.feature!r}")
        if not self.edges or list(self.edges) != sorted(set(self.edges)):
            raise ValueError(f"edges of {self.feature!r} must be non-empty and strictly ascending")

    @property
    def n_buckets(self) -> int:
        return len(self.edges) + 1

    def bucket_label(self, bucket: int) -> str:
        if bucket == 0:
            return f"<{self.edges[0]:g}"
        if bucket == len(self.edges):
            return f">={self.edges[-1]:g}"
        return f"{self.edges[bucket - 1]:g}..{self.edges[bucket]:g}"


# 5 * 3 * 3 * 4 * 5 * 2 * 2 * 2 = 7200 states. Thresholds follow the costs that matter
# for the available actions (SCV/Marine 50, Supply Depot 100, Barracks 150, CC 400).
DEFAULT_BINS: tuple[BinSpec, ...] = (
    BinSpec("minerals", (50, 100, 150, 400)),
    BinSpec("supply_left", (2, 6)),
    BinSpec("workers", (14, 20)),
    BinSpec("barracks", (1, 3, 5)),
    BinSpec("marines", (1, 8, 16, 30)),
    BinSpec("army_attacking", (0.5,)),
    BinSpec("enemy_near_base", (1,)),
    BinSpec("townhalls", (2,)),
)


class StateDiscretizer:
    """Maps an observation vector to a tuple of bucket indices."""

    def __init__(self, bins: Sequence[BinSpec] = DEFAULT_BINS) -> None:
        if not bins:
            raise ValueError("at least one BinSpec is required")
        self.bins: tuple[BinSpec, ...] = tuple(bins)
        self._indices = np.array([FEATURE_INDEX[spec.feature] for spec in self.bins])
        self._scales = FEATURE_SCALES[self._indices]
        self._edges = [np.asarray(spec.edges, dtype=np.float64) for spec in self.bins]

    def __call__(self, obs: np.ndarray) -> State:
        # Undo the observation scaling. Rounding removes float32 noise, which would
        # otherwise push exact thresholds (e.g. 50 minerals) into the lower bucket.
        raw = np.round(obs[self._indices].astype(np.float64) * self._scales, 3)
        return tuple(
            int(np.searchsorted(edges, value, side="right"))
            for edges, value in zip(self._edges, raw, strict=True)
        )

    @property
    def n_states(self) -> int:
        return math.prod(spec.n_buckets for spec in self.bins)

    def describe(self, state: State) -> dict[str, str]:
        """Human-readable form of a state, e.g. ``{"minerals": "100..150", ...}``."""
        return {
            spec.feature: spec.bucket_label(bucket)
            for spec, bucket in zip(self.bins, state, strict=True)
        }

    def to_json(self) -> list[dict[str, object]]:
        return [{"feature": spec.feature, "edges": list(spec.edges)} for spec in self.bins]

    @classmethod
    def from_json(cls, data: list[dict[str, object]]) -> StateDiscretizer:
        return cls([BinSpec(str(item["feature"]), tuple(item["edges"])) for item in data])


@dataclass(frozen=True)
class QLearningConfig:
    alpha: float = 0.1  # learning rate
    gamma: float = 0.99  # discount factor per decision step
    epsilon_start: float = 1.0  # exploration rate in the first episode
    epsilon_end: float = 0.05  # exploration rate after the decay
    epsilon_decay_episodes: int = 150  # episodes over which epsilon falls linearly
    initial_q: float = 0.0  # value of state-action pairs that were never updated
    seed: int = 0


class TabularQAgent(Agent):
    """Epsilon-greedy agent backed by a Q-table stored as ``{state: values per action}``."""

    name = "qlearning"

    def __init__(
        self,
        config: QLearningConfig | None = None,
        discretizer: StateDiscretizer | None = None,
    ) -> None:
        self.config = config or QLearningConfig()
        self.discretizer = discretizer or StateDiscretizer()
        self.q: dict[State, np.ndarray] = {}
        self.visits: dict[State, np.ndarray] = {}
        self.episodes = 0  # finished training episodes
        self.updates = 0  # Q-learning updates applied
        self._rng = np.random.default_rng(self.config.seed)

    # ------------------------------------------------------------------ acting

    @property
    def epsilon(self) -> float:
        """Exploration rate used right now."""
        return self.epsilon_at(self.episodes)

    def epsilon_at(self, finished_episodes: int) -> float:
        """Exploration rate after the given number of finished training episodes."""
        cfg = self.config
        progress = min(finished_episodes / max(cfg.epsilon_decay_episodes, 1), 1.0)
        return cfg.epsilon_start + progress * (cfg.epsilon_end - cfg.epsilon_start)

    def act(self, obs: np.ndarray, action_mask: np.ndarray, *, explore: bool) -> int:
        valid = np.flatnonzero(action_mask)
        if valid.size == 0:
            raise ValueError("the action mask allows no action")
        if explore and self._rng.random() < self.epsilon:
            return int(self._rng.choice(valid))
        return self.greedy_action(self.discretizer(obs), valid)

    def greedy_action(self, state: State, valid: np.ndarray) -> int:
        """Best available action in ``state``; ties (and unseen states) are broken at random."""
        row = self.q.get(state)
        if row is None:
            return int(self._rng.choice(valid))
        values = row[valid]
        best = valid[np.flatnonzero(values == values.max())]
        return int(self._rng.choice(best))

    # ------------------------------------------------------------------ learning

    def observe(
        self,
        obs: np.ndarray,
        action: int,
        reward: float,
        next_obs: np.ndarray,
        next_action_mask: np.ndarray,
        terminated: bool,
    ) -> None:
        cfg = self.config
        state = self.discretizer(obs)
        row = self._row(state)

        target = reward
        if not terminated:
            next_row = self.q.get(self.discretizer(next_obs))
            next_valid = np.flatnonzero(next_action_mask)
            if next_row is None or next_valid.size == 0:
                next_value = cfg.initial_q
            else:
                next_value = float(next_row[next_valid].max())
            target += cfg.gamma * next_value

        row[action] += cfg.alpha * (target - row[action])
        self.visits[state][action] += 1
        self.updates += 1

    def end_episode(self) -> None:
        self.episodes += 1

    def _row(self, state: State) -> np.ndarray:
        row = self.q.get(state)
        if row is None:
            row = np.full(NUM_ACTIONS, self.config.initial_q, dtype=np.float64)
            self.q[state] = row
            self.visits[state] = np.zeros(NUM_ACTIONS, dtype=np.int64)
        return row

    # ------------------------------------------------------------------ persistence

    def save(self, path: str | Path) -> Path:
        """Write the table to a ``.npz`` file (plain arrays plus JSON metadata, no pickle)."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        states = sorted(self.q)
        n_dims = len(self.discretizer.bins)
        meta = {
            "format": TABLE_FORMAT_VERSION,
            "agent": self.name,
            "config": asdict(self.config),
            "bins": self.discretizer.to_json(),
            "action_names": list(ACTION_NAMES),
            "episodes": self.episodes,
            "updates": self.updates,
        }
        tmp_path = path.with_name(path.name + ".tmp")
        with tmp_path.open("wb") as file:
            np.savez_compressed(
                file,
                states=np.array(states, dtype=np.int16).reshape(len(states), n_dims),
                q=np.array([self.q[s] for s in states], dtype=np.float64).reshape(-1, NUM_ACTIONS),
                visits=np.array([self.visits[s] for s in states], dtype=np.int64).reshape(
                    -1, NUM_ACTIONS
                ),
                meta=np.array(json.dumps(meta)),
            )
        tmp_path.replace(path)  # never leave a half-written table behind
        return path

    @classmethod
    def load(cls, path: str | Path) -> TabularQAgent:
        with np.load(Path(path), allow_pickle=False) as data:
            meta = json.loads(str(data["meta"]))
            states, q, visits = data["states"], data["q"], data["visits"]
        if meta.get("format") != TABLE_FORMAT_VERSION:
            raise ValueError(f"unsupported Q-table format: {meta.get('format')!r}")
        if tuple(meta["action_names"]) != ACTION_NAMES:
            raise ValueError(
                "the Q-table was trained with a different action set: "
                f"{meta['action_names']} vs current {list(ACTION_NAMES)}"
            )
        agent = cls(QLearningConfig(**meta["config"]), StateDiscretizer.from_json(meta["bins"]))
        agent.episodes = int(meta["episodes"])
        agent.updates = int(meta["updates"])
        for state_row, q_row, visit_row in zip(states, q, visits, strict=True):
            state = tuple(int(bucket) for bucket in state_row)
            agent.q[state] = q_row.astype(np.float64)
            agent.visits[state] = visit_row.astype(np.int64)
        return agent
