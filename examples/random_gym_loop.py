"""Smallest possible use of the environment: random valid actions through the Gymnasium API.

docker compose run --rm sc2 python examples/random_gym_loop.py
"""

import numpy as np

from scbot.config import EnvConfig
from scbot.env import SC2MacroEnv


def main() -> None:
    rng = np.random.default_rng(0)
    env = SC2MacroEnv(EnvConfig(difficulty="VeryEasy", max_game_minutes=5))
    try:
        obs, info = env.reset(seed=0)
        finished = False
        while not finished:
            action = rng.choice(np.flatnonzero(info["action_mask"]))
            obs, reward, terminated, truncated, info = env.step(action)
            finished = terminated or truncated
        print(info["episode"]["result"])
    finally:
        env.close()


if __name__ == "__main__":  # required: the game runs in a separate process
    main()
