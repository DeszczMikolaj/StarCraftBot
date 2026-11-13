"""Episode loop shared by training, evaluation and the single-game smoke test."""

from __future__ import annotations

import math
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from multiprocessing import connection as mp_connection
from typing import Any

import numpy as np

from scbot.agents.base import Agent
from scbot.env.sc2_env import SC2EnvError, SC2MacroEnv

WAIT_TIMEOUT_S = 0.5
MAX_CONSECUTIVE_FAILURES = 5


@dataclass(frozen=True)
class StepRecord:
    """One decision as seen by the episode loop (passed to the ``on_step`` callback)."""

    decision: int
    obs: np.ndarray
    action: int
    reward: float
    info: dict[str, Any]  # info that came with ``obs`` (before the action)
    next_info: dict[str, Any]  # info returned by the step


@dataclass
class _Slot:
    """One environment and the episode it is currently playing."""

    env: SC2MacroEnv
    active: bool = False
    awaiting_first_step: bool = False
    episode: int = 0
    decision: int = 0
    action: int = 0
    obs: np.ndarray | None = None
    info: dict[str, Any] = field(default_factory=dict)
    started: float = 0.0


def run_episodes(
    envs: Sequence[SC2MacroEnv],
    agent: Agent,
    episodes: int,
    *,
    explore: bool,
    learn: bool,
    seed: int | None = None,
    first_episode: int = 1,
    replay_path: Callable[[int], str | None] | None = None,
    on_step: Callable[[int, StepRecord], None] | None = None,
    on_episode: Callable[[int, dict[str, Any]], None] | None = None,
) -> list[dict[str, Any]]:
    """Play ``episodes`` games, spread over ``envs`` that simulate at the same time.

    Episodes are numbered ``first_episode, first_episode + 1, ...`` in the order they
    start. ``on_episode`` (and the returned list) report them in that same order, even
    when a later game finishes first. Episode ``n`` uses game seed ``seed + n``.

    All decisions and all learning happen in the calling process, one at a time, so a
    single agent can be shared by every environment. A game that crashes is restarted
    under the same episode number; ``SC2EnvError`` is raised after several crashes in
    a row.
    """
    if not envs:
        raise ValueError("at least one environment is required")
    slots = [_Slot(env) for env in envs]
    last_episode = first_episode + episodes - 1
    next_episode = first_episode
    next_to_report = first_episode
    finished: dict[int, dict[str, Any]] = {}
    reported: list[dict[str, Any]] = []
    failures = 0

    def start(slot: _Slot, episode: int) -> None:
        slot.active, slot.awaiting_first_step = True, True
        slot.episode, slot.decision = episode, 0
        slot.started = time.perf_counter()
        slot.env.reset_async(
            seed=None if seed is None else seed + episode,
            options={"replay_path": replay_path(episode) if replay_path else None},
        )

    def start_next(slot: _Slot) -> None:
        nonlocal next_episode
        if next_episode > last_episode:
            slot.active = False
            return
        start(slot, next_episode)
        next_episode += 1

    def advance(slot: _Slot) -> bool:
        """Process one answer from the slot's game. Returns True when its episode ended."""
        nonlocal next_to_report
        step = slot.env.collect()
        if slot.awaiting_first_step:
            slot.awaiting_first_step = False
        else:
            assert slot.obs is not None
            if learn:
                agent.observe(
                    slot.obs,
                    slot.action,
                    step.reward,
                    step.obs,
                    step.info["action_mask"],
                    step.terminated,
                    float(step.info.get("intervals_elapsed", 1.0)),
                )
            if on_step is not None:
                record = StepRecord(
                    slot.decision, slot.obs, slot.action, step.reward, slot.info, step.info
                )
                on_step(slot.episode, record)
            slot.decision += 1
        slot.obs, slot.info = step.obs, step.info

        if step.terminated or step.truncated:
            if learn:
                agent.end_episode()
            summary = dict(step.info["episode"])
            summary["episode"] = slot.episode
            summary["final_raw"] = step.info["raw"]
            summary["wall_seconds"] = time.perf_counter() - slot.started
            finished[slot.episode] = summary
            while next_to_report in finished:
                ordered = finished.pop(next_to_report)
                reported.append(ordered)
                if on_episode is not None:
                    on_episode(next_to_report, ordered)
                next_to_report += 1
            start_next(slot)
            return True

        slot.action = int(agent.act(slot.obs, slot.info["action_mask"], explore=explore))
        slot.env.step_async(slot.action)
        return False

    for slot in slots:
        start_next(slot)

    while True:
        active = [slot for slot in slots if slot.active]
        if not active:
            break
        ready = set(
            mp_connection.wait([slot.env.connection for slot in active], timeout=WAIT_TIMEOUT_S)
        )
        for slot in active:
            try:
                if slot.env.connection in ready:
                    if advance(slot):
                        failures = 0  # only a completed game proves the setup still works
                else:
                    slot.env.check_health()
            except SC2EnvError as error:
                failures += 1
                if failures >= MAX_CONSECUTIVE_FAILURES:
                    raise
                print(
                    f"episode {slot.episode}: game failed ({failures} in a row), "
                    f"restarting it: {error}",
                    file=sys.stderr,
                    flush=True,
                )
                start(slot, slot.episode)
    return reported


def run_episode(
    env: SC2MacroEnv,
    agent: Agent,
    *,
    explore: bool,
    learn: bool,
    seed: int | None = None,
    replay_path: str | None = None,
    on_step: Callable[[StepRecord], None] | None = None,
) -> dict[str, Any]:
    """Play one game and return its summary (``info["episode"]`` plus wall-clock time)."""
    summaries = run_episodes(
        [env],
        agent,
        1,
        explore=explore,
        learn=learn,
        seed=seed,
        first_episode=0,
        replay_path=(lambda _episode: replay_path),
        on_step=None if on_step is None else (lambda _episode, record: on_step(record)),
    )
    return summaries[0]


def wilson_interval(successes: int, trials: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a proportion (default: 95% confidence)."""
    if trials == 0:
        return 0.0, 1.0
    p = successes / trials
    denominator = 1 + z**2 / trials
    centre = (p + z**2 / (2 * trials)) / denominator
    margin = z * math.sqrt(p * (1 - p) / trials + z**2 / (4 * trials**2)) / denominator
    return max(0.0, centre - margin), min(1.0, centre + margin)
