# StarCraftBot: notes for coding agents

University project: macro-level StarCraft II agents (tabular Q-learning, then DQN and
PPO) on one shared python-sc2 environment. Read `docs/status-projektu.md` for what is
done and `docs/architektura.md` for how the pieces fit.

## Language

- Code, comments, commit messages: English.
- `docs/`, `runbooks/`, `README.md`: Polish.

## Commands

The game runs only inside the Docker image (headless Linux SC2 4.10). Docker Desktop
must be running.

```bash
uv run pytest                                      # unit tests, no game needed
docker compose run --rm sc2 pytest -m sc2          # integration tests, real game (~40 s)
uv run ruff check . && uv run ruff format .
docker compose run --rm sc2 python -m scbot.doctor --launch
docker compose run --rm sc2 python -m scbot.play --agent scripted
docker compose run --rm sc2 python -m scbot.train_q --run-name NAME --episodes N --num-envs 12
docker compose run --rm sc2 python -m scbot.evaluate --agent q --model runs/NAME/qtable.npz --num-envs 10
```

Source is bind-mounted into the container: rebuild the image (`docker compose build sc2`)
only after changing `pyproject.toml`, `uv.lock` or `docker/`.

## Rules that are easy to break

- The observation vector (`env/observation.py: FEATURES`) and the action list
  (`env/actions.py: MacroAction`) are a contract shared by all models. Append only;
  never reorder or remove entries.
- Any change under `src/scbot/env/` must pass the integration tests.
- Anything that uses `SC2MacroEnv` needs an `if __name__ == "__main__":` guard, because
  the game runs in a spawned worker process.
- Do not pass absolute container paths as arguments in documented commands: Git Bash on
  Windows rewrites them. Add a CLI flag instead (see `doctor --list-maps`).
- `requirements.txt` is generated: run `uv run python scripts/export_requirements.py`
  after changing dependencies.
- Training and evaluation outputs go to `runs/` and `replays/` (git-ignored). A long
  training run should be started in the background and takes tens of minutes.
- Keep the runbooks truthful: when a documented command or its output changes, re-run it
  and update the runbook. `runbooks/02-klient-windows.md` is explicitly unverified.

## Layout

- `src/scbot/env/`: environment (`sc2_env.py`), game worker (`worker.py`), bot (`bot.py`),
  scripted macro layer (`macro.py`), observation, reward.
- `src/scbot/agents/`: `Agent` interface, random and scripted reference agents,
  `TabularQAgent`.
- `src/scbot/runner.py`: episode loop for one or many parallel games.
- `src/scbot/{doctor,play,train_q,evaluate}.py`: entry points.
