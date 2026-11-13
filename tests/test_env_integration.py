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


def test_an_unavailable_action_is_ignored_and_reported(env):
    _, info = env.reset(seed=1)
    assert info["intervals_elapsed"] == 0

    # Barracks need a Supply Depot and 150 minerals; neither is there at the start.
    _, reward, terminated, truncated, info = env.step(MacroAction.BUILD_BARRACKS)

    assert not terminated and not truncated
    assert not info["last_action_executed"]
    assert info["raw"]["minerals"] >= 50  # nothing was spent
    assert info["intervals_elapsed"] == 1  # the SCV is still on offer: asked again at once
    assert info["game_loop"] == env.config.loops_per_interval
    assert set(info["reward_components"]) == set(REWARD_COMPONENTS)


def test_the_agent_is_not_asked_while_there_is_nothing_to_decide(env):
    _, info = env.reset(seed=1)

    # The SCV takes all 50 minerals, so NO_OP is the only option until more are mined.
    _, _, _, _, info = env.step(MacroAction.TRAIN_SCV)

    assert info["last_action_executed"]
    assert info["action_mask"].sum() > 1  # the next decision point offers a real choice
    assert info["intervals_elapsed"] > 1  # the idle intervals were skipped
    assert info["game_loop"] == info["intervals_elapsed"] * env.config.loops_per_interval


def test_no_op_waits_for_a_new_option_or_the_wait_limit(env):
    limit = env.config.wait_intervals
    _, info = env.reset(seed=1)
    _, _, _, _, info = env.step(MacroAction.TRAIN_SCV)

    waits = []
    while info["raw"]["game_minutes"] < 1.0:
        declined = info["action_mask"].copy()
        _, _, _, _, info = env.step(MacroAction.NO_OP)
        new_option = bool(np.any(info["action_mask"] & ~declined))
        waits.append((info["intervals_elapsed"], new_option))

    assert all(
        elapsed == limit or (new_option and elapsed < limit) for elapsed, new_option in waits
    )
    assert any(elapsed == limit for elapsed, _ in waits)  # nothing new: the full wait
    assert info["raw"]["workers"] == 13  # the SCV ordered at the start has finished


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
