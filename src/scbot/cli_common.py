"""Command-line options shared by the entry points (play, evaluate, train_q)."""

from __future__ import annotations

import argparse
from dataclasses import replace

from scbot.agents.base import Agent
from scbot.agents.qlearning import TabularQAgent
from scbot.agents.simple import RandomAgent, ScriptedAgent
from scbot.config import DIFFICULTIES, EnvConfig

AGENT_CHOICES = ("random", "scripted", "q")


def add_env_arguments(parser: argparse.ArgumentParser) -> None:
    defaults = EnvConfig()
    group = parser.add_argument_group("environment")
    group.add_argument("--map", default=defaults.map_name, help="map name (default: %(default)s)")
    group.add_argument(
        "--difficulty",
        default=defaults.difficulty,
        choices=DIFFICULTIES,
        help="built-in opponent difficulty (default: %(default)s)",
    )
    group.add_argument(
        "--game-step",
        type=int,
        default=defaults.game_step,
        help="game loops per bot step (default: %(default)s)",
    )
    group.add_argument(
        "--decision-interval",
        type=int,
        default=defaults.decision_interval,
        help="bot steps between agent decisions (default: %(default)s)",
    )
    group.add_argument(
        "--wait-intervals",
        type=int,
        default=defaults.wait_intervals,
        help="how many decision intervals a NO_OP waits, unless a new option appears "
        "(default: %(default)s)",
    )
    group.add_argument(
        "--max-game-minutes",
        type=float,
        default=defaults.max_game_minutes,
        help="game time limit; longer games count as a tie (default: %(default)s)",
    )
    group.add_argument(
        "--realtime",
        action="store_true",
        help="play at human speed (to watch the game in the Windows client)",
    )


def env_config_from_args(args: argparse.Namespace) -> EnvConfig:
    return replace(
        EnvConfig(),
        map_name=args.map,
        difficulty=args.difficulty,
        game_step=args.game_step,
        decision_interval=args.decision_interval,
        wait_intervals=args.wait_intervals,
        max_game_minutes=args.max_game_minutes,
        realtime=args.realtime,
    )


def add_agent_arguments(parser: argparse.ArgumentParser, default: str = "scripted") -> None:
    group = parser.add_argument_group("agent")
    group.add_argument(
        "--agent",
        default=default,
        choices=AGENT_CHOICES,
        help="random, scripted (hand-written build order) or q (saved Q-table); "
        "default: %(default)s",
    )
    group.add_argument("--model", help="path to a saved Q-table (.npz), required for --agent q")
    group.add_argument("--seed", type=int, default=0, help="base random seed (default: 0)")


def build_agent(args: argparse.Namespace) -> Agent:
    if args.agent == "random":
        return RandomAgent(seed=args.seed)
    if args.agent == "scripted":
        return ScriptedAgent()
    if not args.model:
        raise SystemExit("--agent q requires --model <path to qtable.npz>")
    return TabularQAgent.load(args.model)
