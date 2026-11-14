"""Check that this machine (or container) can run the project.

    python -m scbot.doctor            # packages, StarCraft II installation, maps
    python -m scbot.doctor --launch   # additionally start the game and play a few steps
    python -m scbot.doctor --list-maps

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

# Seen on a fresh Windows installation: the client spends its first starts downloading
# data and does not open the API port until it is done.
FIRST_START_HINT = (
    ". If the game shows a 'Preparing game data' window, it is still downloading data:"
    " run this command again (the download resumes) until the game starts."
)


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


def find_sc2_base() -> tuple[Path, str]:
    """Where python-sc2 will look for the game (same rules as ``sc2.paths``), and why."""
    from sc2 import paths

    if os.environ.get("SC2PATH"):
        base, source = os.environ["SC2PATH"], "SC2PATH"
    elif (recorded := paths.get_user_sc2_install()) is not None:
        # Windows and macOS: the game writes its own location there when it starts.
        base, source = recorded, "ExecuteInfo.txt"
    else:
        base, source = paths.BASEDIR[paths.PF], "default location"
    return Path(base).expanduser(), source


def check_game(report: Report, map_name: str) -> bool:
    base, source = find_sc2_base()
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

    maps = installed_maps(base)
    if map_name not in maps:
        report.add(
            FAIL,
            "map",
            f"{map_name}.SC2Map not found under {maps_directory(base)} "
            "(see the map installation runbook)",
        )
        return False
    report.add(OK, "map", str(maps[map_name]))
    return True


def maps_directory(base: Path) -> Path:
    return base / "maps" if (base / "maps").exists() else base / "Maps"


def installed_maps(base: Path) -> dict[str, Path]:
    """Maps python-sc2 can load by name: files in the maps folder and one level below it."""
    maps_dir = maps_directory(base)
    if not maps_dir.is_dir():
        return {}
    candidates = [*maps_dir.glob("*.SC2Map"), *maps_dir.glob("*/*.SC2Map")]
    return {path.stem: path for path in sorted(candidates, reverse=True)}


def list_maps() -> None:
    base, _ = find_sc2_base()
    maps = installed_maps(base)
    if not maps:
        raise SystemExit(f"no maps found under {maps_directory(base)}")
    for name in sorted(maps):
        print(f"{name:<32} {maps[name].parent.name}")


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
        detail = str(error)
        if os.name == "nt" and "did not answer" in detail:
            detail += FIRST_START_HINT
        report.add(FAIL, "game launch", detail)
    finally:
        env.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--launch", action="store_true", help="also start the game")
    parser.add_argument("--map", default=EnvConfig().map_name, help="map to look for")
    parser.add_argument(
        "--list-maps", action="store_true", help="print the installed maps and exit"
    )
    args = parser.parse_args()
    if args.list_maps:
        list_maps()
        return

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
