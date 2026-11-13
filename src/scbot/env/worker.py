"""Game worker process: runs StarCraft II games and talks to the environment over a pipe.

python-sc2 owns the event loop and installs signal handlers, so each environment runs
its games in a separate process. The protocol is a strict request/response exchange:

    parent -> worker   ("reset", {"seed": int | None, "replay_path": str | None})
    worker -> parent   ("step", StepData)        first decision point of the new game
    parent -> worker   ("action", int)
    worker -> parent   ("step", StepData)        next decision point, or the final step
    ...                                          (sent once the game has shut down)
    parent -> worker   ("close", None)

A failure inside the worker is reported as ``("error", traceback_text)``.
"""

from __future__ import annotations

import os
import random
import sys
import traceback
from multiprocessing.connection import Connection
from typing import Any

from scbot.config import EnvConfig
from scbot.env.bridge import StepData

DEBUG_ENV_VAR = "SCBOT_DEBUG"


class PipeBridge:
    """Decision bridge that forwards every decision point to the parent process."""

    def __init__(self, conn: Connection) -> None:
        self._conn = conn
        self.final_step: StepData | None = None

    def decide(self, step: StepData) -> int:
        self._conn.send(("step", step))
        kind, payload = self._conn.recv()
        if kind != "action":
            raise RuntimeError(f"expected an action from the environment, got {kind!r}")
        return int(payload)

    def finish(self, step: StepData) -> None:
        # Held back until the game has shut down, so that the replay is on disk by the
        # time the environment reports the end of the episode.
        self.final_step = step


def _configure_output(debug: bool) -> None:
    """Silence the game's console chatter unless SCBOT_DEBUG is set.

    StarCraft II inherits this process's stdout and writes its startup log there, and
    python-sc2 logs every game at INFO level. Warnings and errors still reach stderr.
    """
    import sc2.main  # noqa: F401  (installs its own INFO-level stdout sink on import)
    from loguru import logger

    logger.remove()
    logger.add(sys.stderr, level="INFO" if debug else "WARNING")
    if not debug:
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, 1)
        os.close(devnull)


def _run_episode(conn: Connection, config: EnvConfig, options: dict[str, Any]) -> None:
    # Imported here so that importing this module does not require a game installation.
    from sc2 import maps
    from sc2.data import Difficulty, Race
    from sc2.main import run_game
    from sc2.player import Bot, Computer

    from scbot.env.bot import MacroBot

    seed = options.get("seed")
    if seed is not None:
        random.seed(seed)  # building placement picks among candidate spots at random

    bridge = PipeBridge(conn)
    bot = MacroBot(bridge, config)
    run_game(
        maps.get(config.map_name),
        [
            Bot(Race.Terran, bot, name="scbot"),
            Computer(Race.Terran, Difficulty[config.difficulty]),
        ],
        realtime=config.realtime,
        save_replay_as=options.get("replay_path"),
        game_time_limit=int(config.max_game_minutes * 60),
        random_seed=seed,
    )
    if bridge.final_step is None:
        raise RuntimeError("the game ended without reporting a result")
    conn.send(("step", bridge.final_step))


def worker_main(conn: Connection, config: EnvConfig) -> None:
    """Entry point of the worker process."""
    if hasattr(os, "setsid"):
        # Own process group: the parent can then stop this worker and its game together.
        os.setsid()
    _configure_output(debug=bool(os.environ.get(DEBUG_ENV_VAR)))

    try:
        while True:
            kind, payload = conn.recv()
            if kind == "close":
                break
            if kind != "reset":
                conn.send(("error", f"unexpected message between games: {kind!r}"))
                continue
            try:
                _run_episode(conn, config, payload)
            except Exception:
                conn.send(("error", traceback.format_exc()))
    except (EOFError, BrokenPipeError, KeyboardInterrupt):
        pass  # the parent went away
    finally:
        from sc2.sc2process import KillSwitch

        KillSwitch.kill_all()
        conn.close()
