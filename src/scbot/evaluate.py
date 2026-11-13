"""Evaluate an agent against the built-in AI over several games (no learning).

    python -m scbot.evaluate --agent q --model runs/q_baseline/qtable.npz \
        --difficulty VeryEasy --episodes 20 --num-envs 8

Prints one line per game and a summary with the win rate and its 95% confidence
interval. ``--out`` stores the same data as JSON.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean
from typing import Any

from scbot.cli_common import (
    add_agent_arguments,
    add_env_arguments,
    build_agent,
    env_config_from_args,
)
from scbot.env.sc2_env import SC2MacroEnv
from scbot.runner import run_episodes, wilson_interval


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    add_env_arguments(parser)
    add_agent_arguments(parser)
    parser.add_argument("--episodes", type=int, default=10, help="number of games")
    parser.add_argument(
        "--num-envs", type=int, default=1, help="games played at the same time (default: 1)"
    )
    parser.add_argument("--replay-dir", help="save every game as a replay in this directory")
    parser.add_argument("--out", help="write the results to this JSON file")
    args = parser.parse_args()
    if args.episodes < 1 or args.num_envs < 1:
        raise SystemExit("--episodes and --num-envs must be at least 1")

    config = env_config_from_args(args)
    agent = build_agent(args)
    print(
        f"evaluating agent={agent.name} on {config.map_name} vs {config.difficulty}, "
        f"{args.episodes} games",
        flush=True,
    )

    def replay_path(game: int) -> str | None:
        if not args.replay_dir:
            return None
        return str(Path(args.replay_dir) / f"game{game:03d}.SC2Replay")

    def on_episode(game: int, summary: dict[str, Any]) -> None:
        print(
            f"game {game:3d}/{args.episodes} {summary['result']:<7} "
            f"return={summary['return']:+.3f} game={summary['game_minutes']:4.1f}min "
            f"marines={summary['marines_trained']:3d} "
            f"killed={summary['final_raw']['value_killed']:.0f} "
            f"lost={summary['final_raw']['value_lost']:.0f}",
            flush=True,
        )

    envs = [SC2MacroEnv(config) for _ in range(min(args.num_envs, args.episodes))]
    try:
        games = run_episodes(
            envs,
            agent,
            args.episodes,
            explore=False,
            learn=False,
            seed=args.seed,
            replay_path=replay_path,
            on_episode=on_episode,
        )
    finally:
        for env in envs:
            env.close()

    wins = sum(game["result"] == "Victory" for game in games)
    losses = sum(game["result"] == "Defeat" for game in games)
    ties = len(games) - wins - losses
    low, high = wilson_interval(wins, len(games))
    result = {
        "agent": agent.name,
        "model": args.model,
        "env": config.to_dict(),
        "games": len(games),
        "wins": wins,
        "losses": losses,
        "ties": ties,
        "win_rate": wins / len(games),
        "win_rate_ci95": [low, high],
        "mean_return": mean(game["return"] for game in games),
        "mean_game_minutes": mean(game["game_minutes"] for game in games),
        "mean_marines_trained": mean(game["marines_trained"] for game in games),
        "mean_value_killed": mean(game["final_raw"]["value_killed"] for game in games),
        "mean_value_lost": mean(game["final_raw"]["value_lost"] for game in games),
        "episodes": games,
    }

    print()
    print(f"games:       {len(games)}")
    print(f"W / L / T:   {wins} / {losses} / {ties}")
    print(f"win rate:    {result['win_rate']:.1%}  (95% CI {low:.1%} - {high:.1%})")
    print(f"mean return: {result['mean_return']:+.3f}")
    print(f"mean game:   {result['mean_game_minutes']:.1f} min")
    print(
        f"mean killed / lost value: {result['mean_value_killed']:.0f} / "
        f"{result['mean_value_lost']:.0f}"
    )

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"saved: {out_path}")


if __name__ == "__main__":
    main()
