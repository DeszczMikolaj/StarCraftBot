"""Gymnasium environment: one StarCraft II game = one episode of macro decisions."""

from __future__ import annotations

import multiprocessing as mp
import os
import signal
import subprocess
import time
from multiprocessing.connection import Connection
from pathlib import Path
from typing import Any

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from scbot.config import EnvConfig
from scbot.env.actions import NUM_ACTIONS
from scbot.env.bridge import StepData
from scbot.env.observation import OBS_CLIP, OBS_DIM
from scbot.env.worker import worker_main

POLL_INTERVAL_S = 0.5
CLOSE_TIMEOUT_S = 20.0


class SC2EnvError(RuntimeError):
    """The game process failed, stopped answering, or the environment was misused."""


class SC2MacroEnv(gym.Env):
    """Terran vs built-in Terran AI, controlled with discrete macro actions.

    * observation: ``float32`` vector of length ``OBS_DIM`` (see ``observation.FEATURES``);
    * action: index of a ``MacroAction``;
    * one ``step`` advances the game to the next decision point: at least one decision
      interval (``config.loops_per_interval`` game loops), longer when there was nothing
      to decide or the agent chose to wait (see ``info["intervals_elapsed"]``);
    * ``info["action_mask"]`` marks the actions that can be carried out right now,
      ``info["raw"]`` holds the unscaled game readings.

    The game runs in a separate worker process that is started on the first ``reset``
    and reused for the following episodes. Call ``close`` when done.

    ``reset`` and ``step`` each send a request to the game and wait for the answer. The
    two halves are also available separately (``reset_async`` / ``step_async`` followed
    by ``collect``) so that several environments can simulate at the same time.
    """

    metadata = {"render_modes": []}

    def __init__(self, config: EnvConfig | None = None) -> None:
        self.config = config or EnvConfig()
        self.observation_space = spaces.Box(0.0, OBS_CLIP, shape=(OBS_DIM,), dtype=np.float32)
        self.action_space = spaces.Discrete(NUM_ACTIONS)
        self._context = mp.get_context("spawn")
        self._process: mp.process.BaseProcess | None = None
        self._conn: Connection | None = None
        self._in_episode = False
        self._pending: str | None = None  # "reset" or "step" while an answer is outstanding
        self._deadline = 0.0
        self._action_mask = np.ones(NUM_ACTIONS, dtype=bool)

    # ------------------------------------------------------------------ Gymnasium API

    def reset(
        self, *, seed: int | None = None, options: dict[str, Any] | None = None
    ) -> tuple[np.ndarray, dict[str, Any]]:
        """Start a new game.

        ``options["replay_path"]``: when given, the game is saved there as an .SC2Replay.
        """
        self.reset_async(seed=seed, options=options)
        step = self.collect()
        return step.obs, step.info

    def step(self, action: int) -> tuple[np.ndarray, float, bool, bool, dict[str, Any]]:
        self.step_async(action)
        step = self.collect()
        return step.obs, step.reward, step.terminated, step.truncated, step.info

    def action_masks(self) -> np.ndarray:
        """Mask of currently valid actions (the convention used by sb3-contrib)."""
        return self._action_mask

    def close(self) -> None:
        if self._process is None:
            return
        idle = not self._in_episode and self._pending is None
        if idle and self._process.is_alive() and self._conn is not None:
            try:
                self._conn.send(("close", None))
                self._process.join(CLOSE_TIMEOUT_S)
            except (BrokenPipeError, OSError):
                pass
        self._stop_worker()

    # ------------------------------------------------------------------ asynchronous API

    def reset_async(
        self, *, seed: int | None = None, options: dict[str, Any] | None = None
    ) -> None:
        """Ask for a new game; ``collect`` returns its first decision point."""
        super().reset(seed=seed)
        if self._in_episode or self._pending is not None:
            self._stop_worker()  # abandon the game in progress
        self._ensure_worker()

        replay_path = (options or {}).get("replay_path")
        if replay_path is not None:
            replay_path = str(Path(replay_path).resolve())
            Path(replay_path).parent.mkdir(parents=True, exist_ok=True)

        self._send(("reset", {"seed": seed, "replay_path": replay_path}))
        self._pending = "reset"
        self._deadline = time.monotonic() + self.config.start_timeout_s

    def step_async(self, action: int) -> None:
        """Send an action; ``collect`` returns the next decision point."""
        if self._pending is not None:
            raise SC2EnvError("the previous request has not been collected yet")
        if not self._in_episode:
            raise SC2EnvError("no game in progress: call reset() first")
        if not self.action_space.contains(int(action)):
            raise ValueError(f"invalid action {action!r}; expected 0..{NUM_ACTIONS - 1}")
        self._send(("action", int(action)))
        self._pending = "step"
        self._deadline = time.monotonic() + self.config.step_timeout_s

    @property
    def connection(self) -> Connection:
        """Readable when the answer to the pending request has arrived.

        Pass the connections of several environments to
        ``multiprocessing.connection.wait`` to find out which one to ``collect`` next.
        """
        if self._conn is None:
            raise SC2EnvError("the environment has no game worker; call reset() first")
        return self._conn

    def collect(self) -> StepData:
        """Wait for the answer to the last ``reset_async`` / ``step_async``."""
        if self._pending is None:
            raise SC2EnvError("nothing to collect: no request is pending")
        step = self._receive()
        pending, self._pending = self._pending, None
        finished = step.terminated or step.truncated
        if pending == "reset":
            if finished:
                self._stop_worker()
                raise SC2EnvError("the game ended before the first decision point")
            self._in_episode = True
        elif finished:
            self._in_episode = False
        self._action_mask = step.info["action_mask"]
        return step

    def check_health(self) -> None:
        """Raise ``SC2EnvError`` if the pending request can no longer be answered."""
        if self._pending is None or self._process is None:
            return
        if not self._process.is_alive():
            exit_code = self._process.exitcode
            self._stop_worker()
            raise SC2EnvError(f"the game worker exited unexpectedly (exit code {exit_code})")
        if time.monotonic() > self._deadline:
            timeout_s = (
                self.config.start_timeout_s
                if self._pending == "reset"
                else self.config.step_timeout_s
            )
            self._stop_worker()
            raise SC2EnvError(f"the game did not answer within {timeout_s:.0f} s")

    # ------------------------------------------------------------------ worker management

    def _ensure_worker(self) -> None:
        if self._process is not None and self._process.is_alive():
            return
        self._stop_worker()
        parent_conn, child_conn = self._context.Pipe()
        process = self._context.Process(
            target=worker_main, args=(child_conn, self.config), name="scbot-game-worker"
        )
        process.start()
        child_conn.close()
        self._process, self._conn = process, parent_conn

    def _send(self, message: tuple[str, Any]) -> None:
        assert self._conn is not None
        try:
            self._conn.send(message)
        except (BrokenPipeError, OSError) as error:
            self._stop_worker()
            raise SC2EnvError("the game worker is gone") from error

    def _receive(self) -> StepData:
        assert self._conn is not None
        while True:
            try:
                if self._conn.poll(POLL_INTERVAL_S):
                    kind, payload = self._conn.recv()
                    if kind == "step":
                        return payload
                    self._stop_worker()
                    raise SC2EnvError(f"the game worker failed:\n{payload}")
            except (EOFError, OSError) as error:
                self._stop_worker()
                raise SC2EnvError("the game worker closed the connection") from error
            self.check_health()

    def _stop_worker(self) -> None:
        """Stop the worker process together with the StarCraft II process it started."""
        process, conn = self._process, self._conn
        self._process, self._conn = None, None
        self._in_episode, self._pending = False, None
        if process is not None:
            _kill_process_tree(process)
        if conn is not None:
            conn.close()


def _kill_process_tree(process: mp.process.BaseProcess) -> None:
    pid = process.pid
    if pid is None:
        return
    if process.is_alive():
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True, check=False
            )
        else:
            try:
                os.killpg(pid, signal.SIGKILL)  # the worker leads its own process group
            except (ProcessLookupError, PermissionError):
                process.kill()
    process.join(CLOSE_TIMEOUT_S)
