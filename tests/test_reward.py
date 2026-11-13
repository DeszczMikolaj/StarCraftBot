import pytest

from scbot.config import RewardConfig
from scbot.env.reward import RewardCounters, RewardTracker

CONFIG = RewardConfig(
    win=1.0,
    loss=-1.0,
    tie=0.0,
    marine_trained=0.01,
    worker_trained=0.001,
    value_killed=1e-4,
    value_lost=-5e-5,
)


def test_step_rewards_only_the_change_since_the_previous_step():
    tracker = RewardTracker(CONFIG)
    tracker.step(RewardCounters(marines_trained=2, workers_trained=12))

    reward, components = tracker.step(
        RewardCounters(marines_trained=5, workers_trained=13, value_killed=1000, value_lost=200)
    )

    assert components["marines_trained"] == pytest.approx(0.03)
    assert components["workers_trained"] == pytest.approx(0.001)
    assert components["value_killed"] == pytest.approx(0.1)
    assert components["value_lost"] == pytest.approx(-0.01)
    assert components["terminal"] == 0.0
    assert reward == pytest.approx(0.03 + 0.001 + 0.1 - 0.01)


def test_unchanged_counters_give_zero_reward():
    tracker = RewardTracker(CONFIG)
    counters = RewardCounters(marines_trained=4, value_killed=500)
    tracker.step(counters)

    reward, _ = tracker.step(counters)

    assert reward == 0.0


@pytest.mark.parametrize(
    ("result", "terminal"), [("Victory", 1.0), ("Defeat", -1.0), ("Tie", 0.0), ("Undecided", 0.0)]
)
def test_finish_adds_the_terminal_reward(result, terminal):
    tracker = RewardTracker(CONFIG)
    tracker.step(RewardCounters())

    reward, components = tracker.finish(RewardCounters(value_killed=2000), result)

    assert components["terminal"] == terminal
    assert reward == pytest.approx(terminal + 0.2)
