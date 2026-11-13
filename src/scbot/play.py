"""Play one game and print what the environment reads from it.

Smoke test for the whole stack (game launch, observations, macro actions, rewards):

    python -m scbot.play --agent scripted --difficulty VeryEasy
"""

from __future__ import annotations

import argparse

from scbot.cli_common import (
    add_agent_arguments,
    add_env_arguments,
    build_agent,
    env_config_from_args,
)
from scbot.env.actions import ACTION_NAMES
from scbot.env.sc2_env import SC2MacroEnv
from scbot.runner import StepRecord, run_episode

READINGS = (
    ("min", "minerals"),
    ("supply", "supply_used"),
    ("cap", "supply_cap"),
    ("scv", "workers"),
    ("cc", "townhalls"),
    ("depots", "supply_depots"),
    ("rax", "barracks"),
    ("marines", "marines"),
    ("enemy", "enemy_units_visible"),
    ("killed", "value_killed"),
    ("lost", "value_lost"),
)


def format_step(record: StepRecord) -> str:
    raw = record.info["raw"]
    minutes, seconds = divmod(int(raw["game_minutes"] * 60), 60)
    readings = " ".join(f"{label}={raw[key]:g}" for label, key in READINGS)
    available = ",".join(
        name for name, ok in zip(ACTION_NAMES, record.info["action_mask"], strict=True) if ok
    )
    return (
        f"[{minutes:02d}:{seconds:02d}] #{record.decision:<5d} {readings} | "
        f"action={ACTION_NAMES[record.action]} reward={record.reward:+.4f} | can: {available}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    add_env_arguments(parser)
    add_agent_arguments(parser)
    parser.add_argument("--replay", help="save the game as an .SC2Replay at this path")
    parser.add_argument(
        "--print-every",
        type=int,
        default=25,
        help="print the readings every N decisions (default: %(default)s)",
    )
    args = parser.parse_args()

    config = env_config_from_args(args)
    agent = build_agent(args)
    print(
        f"map={config.map_name} opponent={config.difficulty} agent={agent.name} "
        f"decision every {config.loops_per_decision} game loops "
        f"({config.seconds_per_decision:.2f} s of game time)"
    )
    print("starting StarCraft II...", flush=True)

    def on_step(record: StepRecord) -> None:
        if record.decision % args.print_every == 0:
            print(format_step(record), flush=True)

    env = SC2MacroEnv(config)
    try:
        summary = run_episode(
            env,
            agent,
            explore=False,
            learn=False,
            seed=args.seed,
            replay_path=args.replay,
            on_step=on_step,
        )
    finally:
        env.close()

    print()
    print(f"result:        {summary['result']}")
    print(f"game time:     {summary['game_minutes']:.1f} min ({summary['decisions']} decisions)")
    print(f"wall time:     {summary['wall_seconds']:.1f} s")
    print(f"return:        {summary['return']:+.3f}")
    print(f"reward parts:  {_format_dict(summary['reward_totals'])}")
    print(f"actions:       {_format_dict(summary['action_counts'])}")
    print(f"not executed:  {summary['invalid_actions']}")
    if args.replay:
        print(f"replay:        {args.replay}")


def _format_dict(values: dict[str, float]) -> str:
    return ", ".join(f"{key}={value:g}" for key, value in values.items())


if __name__ == "__main__":
    main()
