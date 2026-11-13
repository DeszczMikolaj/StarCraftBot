"""Train Model A (tabular Q-learning) against the built-in AI.

    python -m scbot.train_q --run-name q_baseline --episodes 200 --num-envs 8

Everything a run produces goes to ``runs/<run-name>/``: the Q-table (``qtable.npz``),
periodic checkpoints, ``episodes.csv``, sampled game readings (``steps.jsonl``),
TensorBoard logs and a few replays. ``--resume`` continues an existing run.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import deque
from dataclasses import asdict
from pathlib import Path
from typing import Any

from scbot.agents.qlearning import QLearningConfig, TabularQAgent
from scbot.cli_common import add_env_arguments, env_config_from_args
from scbot.env.sc2_env import SC2MacroEnv
from scbot.run_logging import RunLogger, episode_row
from scbot.runner import StepRecord, run_episodes

WINRATE_WINDOW = 20


def parse_args() -> argparse.Namespace:
    defaults = QLearningConfig()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run-name", default="q_baseline", help="directory name under runs/")
    parser.add_argument("--runs-dir", default="runs", help="parent directory of all runs")
    parser.add_argument(
        "--episodes", type=int, default=200, help="total number of training games for the run"
    )
    parser.add_argument(
        "--num-envs",
        type=int,
        default=1,
        help="games played at the same time, all updating one Q-table (default: %(default)s)",
    )
    parser.add_argument("--resume", action="store_true", help="continue an existing run")
    parser.add_argument("--seed", type=int, default=defaults.seed)

    agent = parser.add_argument_group("Q-learning")
    agent.add_argument("--alpha", type=float, default=defaults.alpha, help="learning rate")
    agent.add_argument("--gamma", type=float, default=defaults.gamma, help="discount factor")
    agent.add_argument("--epsilon-start", type=float, default=defaults.epsilon_start)
    agent.add_argument("--epsilon-end", type=float, default=defaults.epsilon_end)
    agent.add_argument(
        "--epsilon-decay-episodes",
        type=int,
        default=defaults.epsilon_decay_episodes,
        help="episodes over which epsilon falls linearly from start to end",
    )
    agent.add_argument("--initial-q", type=float, default=defaults.initial_q)

    output = parser.add_argument_group("output")
    output.add_argument(
        "--checkpoint-every", type=int, default=25, help="episodes between numbered checkpoints"
    )
    output.add_argument(
        "--replay-every", type=int, default=50, help="save a replay every N episodes (0: never)"
    )
    output.add_argument(
        "--log-steps-every",
        type=int,
        default=10,
        help="store the raw game readings of every N-th decision in steps.jsonl (0: never)",
    )
    output.add_argument("--no-tensorboard", action="store_true")
    add_env_arguments(parser)
    return parser.parse_args()


def last_logged_episode(run_dir: Path) -> int:
    """Number of the last episode in ``episodes.csv`` (0 when the file does not exist)."""
    path = run_dir / "episodes.csv"
    if not path.exists():
        return 0
    with path.open(newline="", encoding="utf-8") as file:
        return max((int(row["episode"]) for row in csv.DictReader(file)), default=0)


def main() -> None:
    args = parse_args()
    if args.num_envs < 1:
        raise SystemExit("--num-envs must be at least 1")
    env_config = env_config_from_args(args)
    run_dir = Path(args.runs_dir) / args.run_name
    table_path = run_dir / "qtable.npz"

    if args.resume:
        if not table_path.exists():
            raise SystemExit(f"nothing to resume: {table_path} does not exist")
        agent = TabularQAgent.load(table_path)
        print(f"resumed {table_path}: {agent.episodes} episodes, {len(agent.q)} states")
    else:
        if table_path.exists():
            raise SystemExit(
                f"{table_path} already exists. Use --resume to continue it "
                "or pick another --run-name."
            )
        agent = TabularQAgent(
            QLearningConfig(
                alpha=args.alpha,
                gamma=args.gamma,
                epsilon_start=args.epsilon_start,
                epsilon_end=args.epsilon_end,
                epsilon_decay_episodes=args.epsilon_decay_episodes,
                initial_q=args.initial_q,
                seed=args.seed,
            )
        )

    first_episode = last_logged_episode(run_dir) + 1
    remaining = args.episodes - first_episode + 1
    if remaining <= 0:
        raise SystemExit(f"the run already has {first_episode - 1} episodes; raise --episodes")

    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "config.json").write_text(
        json.dumps(
            {
                "env": env_config.to_dict(),
                "agent": asdict(agent.config),
                "bins": agent.discretizer.to_json(),
                "state_space_size": agent.discretizer.n_states,
                "num_envs": args.num_envs,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(
        f"run: {run_dir} | map={env_config.map_name} opponent={env_config.difficulty} | "
        f"state space: {agent.discretizer.n_states} states | "
        f"decision interval {env_config.seconds_per_interval:.2f} s of game time | "
        f"{args.num_envs} game(s) in parallel",
        flush=True,
    )

    logger = RunLogger(run_dir, tensorboard=not args.no_tensorboard)
    recent_wins: deque[bool] = deque(maxlen=WINRATE_WINDOW)

    def replay_path(episode: int) -> str | None:
        if args.replay_every and episode % args.replay_every == 0:
            return str(run_dir / "replays" / f"ep{episode:05d}.SC2Replay")
        return None

    def on_step(episode: int, record: StepRecord) -> None:
        if args.log_steps_every and record.decision % args.log_steps_every == 0:
            logger.log_step(episode, record)

    def on_episode(episode: int, summary: dict[str, Any]) -> None:
        epsilon = agent.epsilon_at(episode - 1)
        logger.log_episode(episode_row(episode, summary, epsilon, len(agent.q)))
        recent_wins.append(summary["result"] == "Victory")
        print(
            f"ep {episode:4d}/{args.episodes} {summary['result']:<7} "
            f"return={summary['return']:+.3f} eps={epsilon:.2f} "
            f"game={summary['game_minutes']:4.1f}min wall={summary['wall_seconds']:4.0f}s "
            f"marines={summary['marines_trained']:3d} states={len(agent.q):4d} "
            f"win{len(recent_wins)}={sum(recent_wins) / len(recent_wins):.0%}",
            flush=True,
        )
        agent.save(table_path)
        if args.checkpoint_every and episode % args.checkpoint_every == 0:
            agent.save(run_dir / "checkpoints" / f"qtable_ep{episode:05d}.npz")

    envs = [SC2MacroEnv(env_config) for _ in range(min(args.num_envs, remaining))]
    try:
        run_episodes(
            envs,
            agent,
            remaining,
            explore=True,
            learn=True,
            seed=args.seed,
            first_episode=first_episode,
            replay_path=replay_path,
            on_step=on_step,
            on_episode=on_episode,
        )
    except KeyboardInterrupt:
        agent.save(table_path)
        print("\ninterrupted: the Q-table was saved, continue with --resume")
    finally:
        for env in envs:
            env.close()
        logger.close()

    print(
        f"done: {agent.episodes} episodes finished, {len(agent.q)} states visited, "
        f"table: {table_path}"
    )


if __name__ == "__main__":
    main()
