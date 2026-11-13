"""Summarise a training run as a table: results per block of games.

    python -m scbot.report runs/q_baseline --block 50

Reads ``episodes.csv`` only, so it works without the game (and while training runs).
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any


def load_episodes(run_dir: Path) -> list[dict[str, str]]:
    path = run_dir / "episodes.csv"
    if not path.exists():
        raise SystemExit(f"{path} does not exist")
    with path.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def summarise_blocks(rows: list[dict[str, str]], block: int) -> list[dict[str, Any]]:
    """One summary per ``block`` consecutive episodes (the last block may be shorter)."""
    summaries = []
    for start in range(0, len(rows), block):
        chunk = rows[start : start + block]
        games = len(chunk)
        wins = sum(row["result"] == "Victory" for row in chunk)
        losses = sum(row["result"] == "Defeat" for row in chunk)
        decisions = sum(int(row["decisions"]) for row in chunk)
        summaries.append(
            {
                "first": int(chunk[0]["episode"]),
                "last": int(chunk[-1]["episode"]),
                "games": games,
                "wins": wins,
                "losses": losses,
                "ties": games - wins - losses,
                "win_rate": wins / games,
                "mean_return": sum(float(row["return"]) for row in chunk) / games,
                "mean_game_minutes": sum(float(row["game_minutes"]) for row in chunk) / games,
                "mean_decisions": decisions / games,
                "no_op_share": sum(int(row["action_NO_OP"]) for row in chunk) / max(decisions, 1),
                "mean_marines": sum(int(row["marines_trained"]) for row in chunk) / games,
                "epsilon": float(chunk[-1]["epsilon"]),
            }
        )
    return summaries


def format_table(summaries: list[dict[str, Any]]) -> str:
    header = (
        f"{'episodes':>11} {'W':>3} {'L':>3} {'T':>3} {'win%':>5} {'return':>7} "
        f"{'game min':>8} {'decisions':>9} {'NO_OP%':>6} {'marines':>7} {'epsilon':>7}"
    )
    lines = [header]
    for s in summaries:
        lines.append(
            f"{s['first']:>5}-{s['last']:<5} {s['wins']:>3} {s['losses']:>3} {s['ties']:>3} "
            f"{s['win_rate']:>5.0%} {s['mean_return']:>+7.3f} {s['mean_game_minutes']:>8.1f} "
            f"{s['mean_decisions']:>9.0f} {s['no_op_share']:>6.0%} {s['mean_marines']:>7.0f} "
            f"{s['epsilon']:>7.2f}"
        )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("run_dir", type=Path, help="run directory, e.g. runs/q_baseline")
    parser.add_argument("--block", type=int, default=50, help="games per row (default: 50)")
    args = parser.parse_args()
    if args.block < 1:
        raise SystemExit("--block must be at least 1")

    rows = load_episodes(args.run_dir)
    if not rows:
        raise SystemExit("the run has no finished episodes yet")
    print(f"{args.run_dir}: {len(rows)} episodes")
    print(format_table(summarise_blocks(rows, args.block)))


if __name__ == "__main__":
    main()
