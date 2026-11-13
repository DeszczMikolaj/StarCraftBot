"""Configuration shared by the environment, the scripted macro layer and the CLIs."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

GAME_LOOPS_PER_SECOND = 22.4  # game speed "Faster", used by ladder games and the API

DIFFICULTIES: tuple[str, ...] = (
    "VeryEasy",
    "Easy",
    "Medium",
    "MediumHard",
    "Hard",
    "Harder",
    "VeryHard",
)


@dataclass(frozen=True)
class RewardConfig:
    """Weights of the reward components.

    Terminal rewards are paid once, at the end of the game. Shaping rewards are paid
    at every decision step for what happened since the previous one.
    """

    win: float = 1.0
    loss: float = -1.0
    tie: float = 0.0  # the game time limit was reached
    marine_trained: float = 0.002  # per Marine that finished training
    worker_trained: float = 0.001  # per SCV that finished training
    value_killed: float = 1e-4  # per resource point of enemy units/structures destroyed
    value_lost: float = -5e-5  # per resource point of own units/structures lost


@dataclass(frozen=True)
class MacroConfig:
    """Limits and distances used by the scripted layer that executes macro actions."""

    max_workers: int = 44
    max_workers_per_townhall: int = 20
    max_townhalls: int = 3
    max_barracks: int = 6
    max_pending_barracks: int = 2
    max_pending_supply_depots: int = 2
    defend_radius: float = 15.0  # enemies this close to one of our structures trigger the defence
    rally_distance: float = 8.0  # how far in front of the forward base the army waits
    # After ATTACK or RETREAT the opposite order is unavailable for this long (game seconds),
    # so an order lasts long enough to have an effect (crossing Simple64 takes about 20 s).
    army_mode_commit_seconds: float = 30.0
    housekeeping_interval: int = 8  # bot steps between worker/construction upkeep passes
    retarget_interval: int = 12  # bot steps between attack target refreshes


@dataclass(frozen=True)
class EnvConfig:
    """Everything that defines one environment instance."""

    map_name: str = "Simple64"
    difficulty: str = "VeryEasy"  # built-in opponent, one of DIFFICULTIES
    game_step: int = 8  # game loops simulated per bot step
    decision_interval: int = 4  # bot steps between agent decisions (4 * 8 loops = 1.43 s)
    max_game_minutes: float = 20.0  # longer games are truncated and count as a tie
    realtime: bool = False  # True: play at human speed (to watch with the Windows client)
    start_timeout_s: float = 240.0  # time allowed for SC2 to launch and reach the first decision
    step_timeout_s: float = 120.0  # time allowed for the game to answer one step
    macro: MacroConfig = field(default_factory=MacroConfig)
    reward: RewardConfig = field(default_factory=RewardConfig)

    def __post_init__(self) -> None:
        if self.difficulty not in DIFFICULTIES:
            raise ValueError(f"difficulty must be one of {DIFFICULTIES}, got {self.difficulty!r}")
        if self.game_step < 1 or self.decision_interval < 1:
            raise ValueError("game_step and decision_interval must be positive")

    @property
    def loops_per_decision(self) -> int:
        return self.game_step * self.decision_interval

    @property
    def seconds_per_decision(self) -> float:
        return self.loops_per_decision / GAME_LOOPS_PER_SECOND

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EnvConfig:
        data = dict(data)
        macro = MacroConfig(**data.pop("macro", {}))
        reward = RewardConfig(**data.pop("reward", {}))
        return cls(**data, macro=macro, reward=reward)
