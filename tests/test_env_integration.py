"""Tests that start a real StarCraft II game. Run them where the game is installed:

docker compose run --rm sc2 pytest -m sc2
"""

from dataclasses import replace

import numpy as np
import pytest
from sc2.main import get_replay_version

from scbot.agents.simple import RandomAgent
from scbot.config import EnvConfig
from scbot.env.actions import NUM_ACTIONS, MacroAction
from scbot.env.observation import FEATURE_NAMES, OBS_DIM
from scbot.env.reward import REWARD_COMPONENTS
from scbot.env.sc2_env import SC2EnvError, SC2MacroEnv
from scbot.runner import run_episode

pytestmark = pytest.mark.sc2


@pytest.fixture
def env():
    environment = SC2MacroEnv(replace(EnvConfig(), max_game_minutes=2.0))
    yield environment
    environment.close()


def test_reset_returns_the_opening_position(env):
    obs, info = env.reset(seed=1)

    assert obs.shape == (OBS_DIM,)
    assert env.observation_space.contains(obs)
    assert set(info["raw"]) == set(FEATURE_NAMES)
    assert info["raw"]["minerals"] == 50
    assert info["raw"]["workers"] == 12
    assert info["raw"]["supply_cap"] == 15
    assert info["raw"]["townhalls"] == 1
    # 50 minerals and an idle Command Center: only an SCV can be afforded.
    mask = info["action_mask"]
    assert mask.shape == (NUM_ACTIONS,)
    assert mask[MacroAction.NO_OP] and mask[MacroAction.TRAIN_SCV]
    assert not mask[MacroAction.BUILD_BARRACKS] and not mask[MacroAction.ATTACK]


def test_actions_change_the_game_and_time_advances_by_the_decision_interval(env):
    _, info = env.reset(seed=1)
    first_loop = info["game_loop"]

    _, reward, terminated, truncated, info = env.step(MacroAction.TRAIN_SCV)
    assert not terminated and not truncated
    assert info["game_loop"] - first_loop == env.config.loops_per_decision
    assert info["last_action_executed"]
    assert info["raw"]["minerals"] < 50  # the SCV was paid for
    assert set(info["reward_components"]) == set(REWARD_COMPONENTS)

    # Barracks are not available yet: the action is ignored and reported as such.
    _, _, _, _, info = env.step(MacroAction.BUILD_BARRACKS)
    assert not info["last_action_executed"]

    for _ in range(40):
        _, _, _, _, info = env.step(MacroAction.NO_OP)
    assert info["raw"]["workers"] == 13


def test_game_is_truncated_at_the_time_limit_and_the_worker_is_reused(env):
    agent = RandomAgent(seed=0)

    first = run_episode(env, agent, explore=True, learn=False, seed=3)
    second = run_episode(env, agent, explore=True, learn=False, seed=4)

    for summary in (first, second):
        assert summary["result"] == "Tie"
        assert summary["game_minutes"] == pytest.approx(2.0, abs=0.1)
        assert sum(summary["action_counts"].values()) == summary["decisions"]
        assert np.isfinite(summary["return"])


def test_step_before_reset_is_rejected(env):
    with pytest.raises(SC2EnvError, match="reset"):
        env.step(MacroAction.NO_OP)


def test_replay_is_written_when_requested(env, tmp_path):
    replay = tmp_path / "game.SC2Replay"
    agent = RandomAgent(seed=0)

    run_episode(env, agent, explore=True, learn=False, seed=5, replay_path=str(replay))

    # The file must already be complete when the episode is reported as finished.
    base_build, data_version = get_replay_version(replay)
    assert base_build.startswith("Base")
    assert data_version
