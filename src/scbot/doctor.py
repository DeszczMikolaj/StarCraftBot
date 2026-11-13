"""Check that this machine (or container) can run the project.

    python -m scbot.doctor            # packages, StarCraft II installation, maps
    python -m scbot.doctor --launch   # additionally start the game and play a few steps

Exits with status 1 when a required check fails.
"""

from __future__ import annotations

import argparse
import importlib
import importlib.metadata
import os
import platform
import sys
from dataclasses import replace
from pathlib import Path

from scbot.config import EnvConfig

OK, WARN, FAIL = "ok", "warn", "FAIL"


class Report:
    def __init__(self) -> None:
        self.failed = False

    def add(self, status: str, name: str, detail: str) -> None:
        if status == FAIL:
            self.failed = True
        print(f"[{status:>4}] {name:<18} {detail}")


def check_python(report: Report) -> None:
    version = platform.python_version()
    supported = sys.version_info[:2] == (3, 12)
    report.add(
        OK if supported else WARN,
        "python",
        f"{version} on {platform.system()}"
        + ("" if supported else " (the project is developed and locked for 3.12)"),
    )


def check_packages(report: Report) -> None:
    for distribution, module in (
        ("burnysc2", "sc2"),
        ("gymnasium", "gymnasium"),
        ("numpy", "numpy"),
        ("tensorboard", "tensorboard"),
    ):
        try:
            importlib.import_module(module)
            report.add(OK, distribution, importlib.metadata.version(distribution))
        except Exception as error:  # an import can fail in many ways; report all of them
            report.add(FAIL, distribution, f"cannot import: {error}")

    try:
        import torch

        if torch.cuda.is_available():
            device = f"CUDA available ({torch.cuda.get_device_name(0)})"
        else:
            device = "CPU only"
        report.add(OK, "torch", f"{torch.__version__}, {device}")
    except Exception as error:
        report.add(FAIL, "torch", f"cannot import: {error}")


def find_sc2_base() -> Path:
    """Where python-sc2 will look for the game (same rules as ``sc2.paths``)."""
    from sc2 import paths

    base = os.environ.get("SC2PATH") or paths.get_user_sc2_install() or paths.BASEDIR[paths.PF]
    return Path(base).expanduser()


def check_game(report: Report, map_name: str) -> bool:
    base = find_sc2_base()
    source = "SC2PATH" if os.environ.get("SC2PATH") else "default location"
    versions = base / "Versions"
    if not versions.is_dir():
        report.add(
            FAIL,
            "StarCraft II",
            f"not found at {base} ({source}). Install the game or set SC2PATH.",
        )
        return False
    builds = sorted(p.name for p in versions.iterdir() if p.name.startswith("Base"))
    report.add(OK, "StarCraft II", f"{base} ({source}), builds: {', '.join(builds)}")

    maps_dir = base / "maps" if (base / "maps").exists() else base / "Maps"
    found = sorted(maps_dir.glob(f"**/{map_name}.SC2Map")) if maps_dir.is_dir() else []
    if not found:
        report.add(
            FAIL,
            "map",
            f"{map_name}.SC2Map not found under {maps_dir} (see the map installation runbook)",
        )
        return False
    report.add(OK, "map", str(found[0]))
    return True


def check_launch(report: Report, map_name: str) -> None:
    """Start a real game and play 20 decisions with random actions."""
    from scbot.agents.simple import RandomAgent
    from scbot.env.observation import OBS_DIM
    from scbot.env.sc2_env import SC2MacroEnv

    env = SC2MacroEnv(replace(EnvConfig(), map_name=map_name))
    agent = RandomAgent(seed=0)
    try:
        obs, info = env.reset(seed=0)
        for _ in range(20):
            action = agent.act(obs, info["action_mask"], explore=True)
            obs, _, terminated, truncated, info = env.step(action)
            if terminated or truncated:
                break
        raw = info["raw"]
        report.add(
            OK,
            "game launch",
            f"observation of length {OBS_DIM}, game loop {info['game_loop']}, "
            f"minerals={raw['minerals']:g}, workers={raw['workers']:g}",
        )
    except Exception as error:
        report.add(FAIL, "game launch", str(error))
    finally:
        env.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--launch", action="store_true", help="also start the game")
    parser.add_argument("--map", default=EnvConfig().map_name, help="map to look for")
    args = parser.parse_args()

    report = Report()
    check_python(report)
    check_packages(report)
    game_ready = check_game(report, args.map)
    if args.launch:
        if game_ready:
            check_launch(report, args.map)
        else:
            report.add(FAIL, "game launch", "skipped: the game or the map is missing")

    print()
    print("Environment is NOT ready." if report.failed else "Environment is ready.")
    raise SystemExit(1 if report.failed else 0)


if __name__ == "__main__":
    main()
