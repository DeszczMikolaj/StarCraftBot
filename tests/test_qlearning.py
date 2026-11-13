import numpy as np
import pytest

from scbot.agents.qlearning import (
    DEFAULT_BINS,
    BinSpec,
    QLearningConfig,
    StateDiscretizer,
    TabularQAgent,
)
from scbot.env.actions import NUM_ACTIONS, MacroAction
from scbot.env.observation import FEATURE_NAMES, to_vector

ALL_ACTIONS = np.ones(NUM_ACTIONS, dtype=bool)


def observation(**overrides: float) -> np.ndarray:
    raw = dict.fromkeys(FEATURE_NAMES, 0.0)
    raw.update(overrides)
    return to_vector(raw)


def only(*actions: MacroAction) -> np.ndarray:
    mask = np.zeros(NUM_ACTIONS, dtype=bool)
    mask[list(actions)] = True
    return mask


# ---------------------------------------------------------------- discretizer


@pytest.mark.parametrize(
    ("minerals", "bucket"),
    [(0, 0), (49, 0), (50, 1), (99, 1), (100, 2), (149, 2), (150, 3), (399, 3), (400, 4), (900, 4)],
)
def test_bucket_boundaries_are_exact_despite_float32_observations(minerals, bucket):
    discretizer = StateDiscretizer([BinSpec("minerals", (50, 100, 150, 400))])

    assert discretizer(observation(minerals=minerals)) == (bucket,)


def test_state_combines_one_bucket_per_configured_feature():
    discretizer = StateDiscretizer(
        [BinSpec("minerals", (100,)), BinSpec("marines", (1, 8)), BinSpec("army_attacking", (0.5,))]
    )

    state = discretizer(observation(minerals=120, marines=8, army_attacking=1))

    assert state == (1, 2, 1)
    assert discretizer.n_states == 2 * 3 * 2
    assert discretizer.describe(state) == {
        "minerals": ">=100",
        "marines": ">=8",
        "army_attacking": ">=0.5",
    }


def test_default_state_space_stays_small_enough_for_a_table():
    assert StateDiscretizer(DEFAULT_BINS).n_states == 7200


def test_unknown_feature_and_unsorted_edges_are_rejected():
    with pytest.raises(ValueError, match="unknown observation feature"):
        BinSpec("not_a_feature", (1,))
    with pytest.raises(ValueError, match="ascending"):
        BinSpec("minerals", (100, 50))


# ---------------------------------------------------------------- learning rule


def test_update_follows_the_q_learning_rule():
    agent = TabularQAgent(QLearningConfig(alpha=0.5, gamma=0.9))
    s, s_next = observation(minerals=0), observation(minerals=400)
    agent.q[agent.discretizer(s_next)] = np.arange(NUM_ACTIONS, dtype=np.float64)

    agent.observe(s, MacroAction.TRAIN_SCV, 1.0, s_next, ALL_ACTIONS, terminated=False)

    best_next = NUM_ACTIONS - 1
    expected = 0.0 + 0.5 * (1.0 + 0.9 * best_next - 0.0)
    assert agent.q[agent.discretizer(s)][MacroAction.TRAIN_SCV] == pytest.approx(expected)
    assert agent.visits[agent.discretizer(s)][MacroAction.TRAIN_SCV] == 1
    assert agent.updates == 1


def test_bootstrap_ignores_actions_that_are_unavailable_in_the_next_state():
    agent = TabularQAgent(QLearningConfig(alpha=1.0, gamma=1.0))
    s, s_next = observation(minerals=0), observation(minerals=400)
    next_values = np.zeros(NUM_ACTIONS)
    next_values[MacroAction.ATTACK] = 10.0  # best, but masked out
    next_values[MacroAction.TRAIN_MARINE] = 2.0
    agent.q[agent.discretizer(s_next)] = next_values

    agent.observe(
        s,
        MacroAction.NO_OP,
        0.0,
        s_next,
        only(MacroAction.NO_OP, MacroAction.TRAIN_MARINE),
        terminated=False,
    )

    assert agent.q[agent.discretizer(s)][MacroAction.NO_OP] == pytest.approx(2.0)


def test_terminal_transition_does_not_bootstrap():
    agent = TabularQAgent(QLearningConfig(alpha=1.0, gamma=0.99))
    s, s_next = observation(minerals=0), observation(minerals=400)
    agent.q[agent.discretizer(s_next)] = np.full(NUM_ACTIONS, 100.0)

    agent.observe(s, MacroAction.ATTACK, 1.0, s_next, ALL_ACTIONS, terminated=True)

    assert agent.q[agent.discretizer(s)][MacroAction.ATTACK] == pytest.approx(1.0)


# ---------------------------------------------------------------- acting


def test_greedy_action_is_the_best_available_one():
    agent = TabularQAgent()
    obs = observation(minerals=200)
    values = np.zeros(NUM_ACTIONS)
    values[MacroAction.EXPAND] = 5.0  # best overall, but not available
    values[MacroAction.TRAIN_MARINE] = 3.0
    agent.q[agent.discretizer(obs)] = values

    action = agent.act(obs, only(MacroAction.NO_OP, MacroAction.TRAIN_MARINE), explore=False)

    assert action == MacroAction.TRAIN_MARINE


def test_exploration_only_picks_available_actions():
    agent = TabularQAgent(QLearningConfig(epsilon_start=1.0, epsilon_end=1.0))
    mask = only(MacroAction.NO_OP, MacroAction.BUILD_SUPPLY_DEPOT)

    chosen = {agent.act(observation(), mask, explore=True) for _ in range(200)}

    assert chosen == {MacroAction.NO_OP, MacroAction.BUILD_SUPPLY_DEPOT}


def test_epsilon_decays_linearly_per_finished_episode():
    agent = TabularQAgent(
        QLearningConfig(epsilon_start=1.0, epsilon_end=0.1, epsilon_decay_episodes=10)
    )

    assert agent.epsilon == pytest.approx(1.0)
    for _ in range(5):
        agent.end_episode()
    assert agent.epsilon == pytest.approx(0.55)
    for _ in range(20):
        agent.end_episode()
    assert agent.epsilon == pytest.approx(0.1)


def test_learns_the_better_action_on_a_two_step_task():
    """Reward arrives only after the second step, so it must propagate through the table."""
    agent = TabularQAgent(
        QLearningConfig(alpha=0.5, gamma=0.9, epsilon_start=1.0, epsilon_end=1.0, seed=1)
    )
    start, middle, end = observation(minerals=0), observation(minerals=120), observation()
    mask = only(MacroAction.NO_OP, MacroAction.TRAIN_MARINE)

    for _ in range(300):
        first = agent.act(start, mask, explore=True)
        if first == MacroAction.TRAIN_MARINE:
            agent.observe(start, first, 0.0, middle, mask, terminated=False)
            second = agent.act(middle, mask, explore=True)
            reward = 1.0 if second == MacroAction.TRAIN_MARINE else 0.0
            agent.observe(middle, second, reward, end, mask, terminated=True)
        else:
            agent.observe(start, first, 0.0, end, mask, terminated=True)
        agent.end_episode()

    assert agent.act(start, mask, explore=False) == MacroAction.TRAIN_MARINE
    assert agent.act(middle, mask, explore=False) == MacroAction.TRAIN_MARINE
    assert agent.q[agent.discretizer(start)][MacroAction.TRAIN_MARINE] == pytest.approx(
        0.9, abs=0.05
    )


# ---------------------------------------------------------------- persistence


def test_saved_table_is_restored_exactly(tmp_path):
    agent = TabularQAgent(
        QLearningConfig(alpha=0.3, gamma=0.95, epsilon_decay_episodes=40, seed=7),
        StateDiscretizer([BinSpec("minerals", (50, 150)), BinSpec("marines", (5,))]),
    )
    rng = np.random.default_rng(0)
    for _ in range(50):
        obs = observation(minerals=float(rng.integers(0, 300)), marines=float(rng.integers(0, 10)))
        nxt = observation(minerals=float(rng.integers(0, 300)), marines=float(rng.integers(0, 10)))
        agent.observe(
            obs, int(rng.integers(NUM_ACTIONS)), float(rng.normal()), nxt, ALL_ACTIONS, False
        )
    agent.end_episode()

    restored = TabularQAgent.load(agent.save(tmp_path / "table.npz"))

    assert restored.config == agent.config
    assert restored.discretizer.bins == agent.discretizer.bins
    assert restored.episodes == 1
    assert restored.updates == 50
    assert restored.q.keys() == agent.q.keys()
    for state, values in agent.q.items():
        np.testing.assert_array_equal(restored.q[state], values)
        np.testing.assert_array_equal(restored.visits[state], agent.visits[state])


def test_empty_table_can_be_saved_and_loaded(tmp_path):
    restored = TabularQAgent.load(TabularQAgent().save(tmp_path / "empty.npz"))

    assert restored.q == {}
