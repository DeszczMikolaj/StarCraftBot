"""Files written by a training run: per-episode CSV, sampled step readings, TensorBoard."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from scbot.env.actions import ACTION_NAMES
from scbot.env.reward import REWARD_COMPONENTS
from scbot.runner import StepRecord

EPISODE_COLUMNS: tuple[str, ...] = (
    "episode",
    "result",
    "return",
    "decisions",
    "game_minutes",
    "wall_seconds",
    "epsilon",
    "q_states",
    "invalid_actions",
    "score",
    "collected_minerals",
    "marines_trained",
    "workers_trained",
    "final_workers",
    "final_marines",
    "final_barracks",
    "final_townhalls",
    "value_killed",
    "value_lost",
    *(f"reward_{name}" for name in REWARD_COMPONENTS),
    *(f"action_{name}" for name in ACTION_NAMES),
)


def episode_row(
    episode: int, summary: dict[str, Any], epsilon: float, q_states: int
) -> dict[str, Any]:
    final = summary["final_raw"]
    row: dict[str, Any] = {
        "episode": episode,
        "result": summary["result"],
        "return": round(summary["return"], 5),
        "decisions": summary["decisions"],
        "game_minutes": round(summary["game_minutes"], 2),
        "wall_seconds": round(summary["wall_seconds"], 1),
        "epsilon": round(epsilon, 4),
        "q_states": q_states,
        "invalid_actions": summary["invalid_actions"],
        "score": summary["score"],
        "collected_minerals": summary["collected_minerals"],
        "marines_trained": summary["marines_trained"],
        "workers_trained": summary["workers_trained"],
        "final_workers": final["workers"],
        "final_marines": final["marines"],
        "final_barracks": final["barracks"],
        "final_townhalls": final["townhalls"],
        "value_killed": final["value_killed"],
        "value_lost": final["value_lost"],
    }
    for name in REWARD_COMPONENTS:
        row[f"reward_{name}"] = round(summary["reward_totals"][name], 5)
    for name in ACTION_NAMES:
        row[f"action_{name}"] = summary["action_counts"][name]
    return row


class RunLogger:
    """Appends to ``episodes.csv`` and ``steps.jsonl`` and mirrors scalars to TensorBoard."""

    def __init__(self, run_dir: Path, *, tensorboard: bool = True) -> None:
        self.run_dir = run_dir
        run_dir.mkdir(parents=True, exist_ok=True)
        self._episodes_path = run_dir / "episodes.csv"
        self._steps_path = run_dir / "steps.jsonl"
        self._writer = None
        if tensorboard:
            from torch.utils.tensorboard import SummaryWriter

            self._writer = SummaryWriter(log_dir=str(run_dir / "tb"))

    def log_step(self, episode: int, record: StepRecord) -> None:
        """Store one decision with the raw game readings it was based on."""
        entry = {
            "episode": episode,
            "decision": record.decision,
            "game_loop": record.info["game_loop"],
            "action": ACTION_NAMES[record.action],
            "reward": round(record.reward, 6),
            "available": [
                name
                for name, ok in zip(ACTION_NAMES, record.info["action_mask"], strict=True)
                if ok
            ],
            "raw": record.info["raw"],
        }
        with self._steps_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(entry) + "\n")

    def log_episode(self, row: dict[str, Any]) -> None:
        is_new = not self._episodes_path.exists()
        with self._episodes_path.open("a", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=EPISODE_COLUMNS)
            if is_new:
                writer.writeheader()
            writer.writerow(row)

        if self._writer is None:
            return
        episode = row["episode"]
        scalars = {
            "episode/return": row["return"],
            "episode/win": float(row["result"] == "Victory"),
            "episode/game_minutes": row["game_minutes"],
            "episode/decisions": row["decisions"],
            "episode/invalid_actions": row["invalid_actions"],
            "agent/epsilon": row["epsilon"],
            "agent/q_states": row["q_states"],
            "game/score": row["score"],
            "game/marines_trained": row["marines_trained"],
            "game/workers_trained": row["workers_trained"],
            "game/final_barracks": row["final_barracks"],
            "game/value_killed": row["value_killed"],
            "game/value_lost": row["value_lost"],
        }
        for name in REWARD_COMPONENTS:
            scalars[f"reward/{name}"] = row[f"reward_{name}"]
        decisions = max(row["decisions"], 1)
        for name in ACTION_NAMES:
            scalars[f"action_share/{name}"] = row[f"action_{name}"] / decisions
        for tag, value in scalars.items():
            self._writer.add_scalar(tag, value, episode)
        self._writer.flush()

    def close(self) -> None:
        if self._writer is not None:
            self._writer.close()
