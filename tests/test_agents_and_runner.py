import multiprocessing as mp

import numpy as np
import pytest

from scbot.agents.base import Agent
from scbot.agents.simple import RandomAgent, ScriptedAgent
from scbot.env.actions import NUM_ACTIONS, MacroAction
from scbot.env.bridge import StepData
from scbot.env.observation import FEATURE_NAMES, to_vector
from scbot.env.sc2_env import SC2EnvError
from scbot.runner import run_episode, run_episodes, wilson_interval


def observation(**overrides: float) -> np.ndarray:
    raw = dict.fromkeys(FEATURE_NAMES, 0.0)
    raw.update(overrides)
    return to_vector(raw)


def only(*actions: MacroAction) -> np.ndarray:
    mask = np.zeros(NUM_ACTIONS, dtype=bool)
    mask[list(actions)] = True
    return mask


def test_random_agent_respects_the_action_mask():
    agent = RandomAgent(seed=0)
    mask = only(MacroAction.NO_OP, MacroAction.TRAIN_SCV, MacroAction.ATTACK)

    chosen = {agent.act(observation(), mask, explore=True) for _ in range(300)}

    assert chosen == {MacroAction.NO_OP, MacroAction.TRAIN_SCV, MacroAction.ATTACK}


def test_scripted_agent_builds_supply_before_it_runs_out():
    agent = ScriptedAgent()
    obs = observation(supply_left=1, workers=14, townhalls=1, minerals=120)
    mask = only(MacroAction.NO_OP, MacroAction.TRAIN_SCV, MacroAction.BUILD_SUPPLY_DEPOT)

    assert agent.act(obs, mask, explore=False) == MacroAction.BUILD_SUPPLY_DEPOT


def test_scripted_agent_attacks_once_the_army_is_large_enough():
    agent = ScriptedAgent(attack_at_marines=16)
    mask = only(MacroAction.NO_OP, MacroAction.TRAIN_MARINE, MacroAction.ATTACK)

    small = observation(marines=10, supply_left=10, workers=16, townhalls=1, barracks=4)
    large = observation(marines=16, supply_left=10, workers=16, townhalls=1, barracks=4)

    assert agent.act(small, mask, explore=False) == MacroAction.TRAIN_MARINE
    assert agent.act(large, mask, explore=False) == MacroAction.ATTACK


def test_scripted_agent_never_picks_an_unavailable_action():
    agent = ScriptedAgent()
    obs = observation(marines=40, supply_left=0, workers=5, townhalls=1)

    assert agent.act(obs, only(MacroAction.NO_OP), explore=False) == MacroAction.NO_OP


# ---------------------------------------------------------------- episode loop


class FakeEnv:
    """Scripted games with the same asynchronous contract as SC2MacroEnv.

    Every game lasts ``length`` decisions. Answers travel through a real pipe, so the
    episode loop waits on them exactly as it does with a game worker.
    """

    def __init__(self, length: int = 3, crashes: int = 0) -> None:
        self.length = length
        self.crashes_left = crashes  # how many upcoming games crash on their first step
        self.resets: list[dict] = []
        self.actions: list[int] = []
        self._crash_this_game = False
        self._decision = 0
        self.connection, self._sender = mp.Pipe(duplex=False)

    def _answer(self, reward: float) -> None:
        info = {
            "action_mask": np.ones(NUM_ACTIONS, dtype=bool),
            "raw": {"decision": self._decision},
        }
        terminated = self._decision == self.length
        if terminated:
            info["episode"] = {"result": "Victory", "return": float(self.length)}
        obs = observation(minerals=100 * self._decision)
        self._sender.send(StepData(obs, reward, terminated, False, info))

    def reset_async(self, *, seed=None, options=None) -> None:
        self.resets.append({"seed": seed, "options": options})
        self._decision = 0
        self._crash_this_game = self.crashes_left > 0
        self.crashes_left -= self._crash_this_game
        self._answer(0.0)

    def step_async(self, action: int) -> None:
        self.actions.append(action)
        if self._crash_this_game:
            self._sender.send(None)
            return
        self._decision += 1
        self._answer(1.0)

    def collect(self) -> StepData:
        answer = self.connection.recv()
        if answer is None:
            raise SC2EnvError("simulated crash")
        return answer

    def check_health(self) -> None:
        return None


class RecordingAgent(Agent):
    def __init__(self) -> None:
        self.transitions: list[tuple] = []
        self.episodes_ended = 0

    def act(self, obs, action_mask, *, explore):
        return MacroAction.TRAIN_SCV

    def observe(self, obs, action, reward, next_obs, next_action_mask, terminated):
        self.transitions.append((action, reward, terminated))

    def end_episode(self):
        self.episodes_ended += 1


def test_run_episode_feeds_every_transition_to_a_learning_agent():
    env, agent = FakeEnv(), RecordingAgent()
    steps = []

    summary = run_episode(
        env,
        agent,
        explore=True,
        learn=True,
        seed=42,
        replay_path="x.SC2Replay",
        on_step=steps.append,
    )

    assert env.resets == [{"seed": 42, "options": {"replay_path": "x.SC2Replay"}}]
    assert env.actions == [MacroAction.TRAIN_SCV] * 3
    assert agent.transitions == [
        (MacroAction.TRAIN_SCV, 1.0, False),
        (MacroAction.TRAIN_SCV, 1.0, False),
        (MacroAction.TRAIN_SCV, 1.0, True),
    ]
    assert agent.episodes_ended == 1
    assert [step.decision for step in steps] == [0, 1, 2]
    assert [step.info["raw"]["decision"] for step in steps] == [0, 1, 2]
    assert summary["result"] == "Victory"
    assert summary["final_raw"] == {"decision": 3}
    assert summary["wall_seconds"] >= 0


def test_run_episode_without_learning_leaves_the_agent_untouched():
    agent = RecordingAgent()

    run_episode(FakeEnv(), agent, explore=False, learn=False)

    assert agent.transitions == []
    assert agent.episodes_ended == 0


def test_parallel_episodes_are_reported_in_start_order():
    # The second environment plays much shorter games, so its episodes finish first.
    slow, fast = FakeEnv(length=9), FakeEnv(length=2)
    agent = RecordingAgent()
    reported = []

    summaries = run_episodes(
        [slow, fast],
        agent,
        5,
        explore=True,
        learn=True,
        seed=100,
        first_episode=11,
        on_episode=lambda episode, summary: reported.append(episode),
    )

    assert reported == [11, 12, 13, 14, 15]
    assert [summary["episode"] for summary in summaries] == [11, 12, 13, 14, 15]
    seeds = sorted(reset["seed"] for reset in slow.resets + fast.resets)
    assert seeds == [111, 112, 113, 114, 115]
    assert agent.episodes_ended == 5
    assert len(agent.transitions) == len(slow.actions) + len(fast.actions)


def test_a_crashed_game_is_replayed_under_the_same_episode_number():
    env, agent = FakeEnv(length=2, crashes=1), RecordingAgent()
    steps = []

    summaries = run_episodes(
        [env],
        agent,
        2,
        explore=True,
        learn=True,
        seed=0,
        on_step=lambda episode, record: steps.append(episode),
    )

    assert [summary["episode"] for summary in summaries] == [1, 2]
    assert [reset["seed"] for reset in env.resets] == [1, 1, 2]
    assert steps == [1, 1, 2, 2]
    assert agent.episodes_ended == 2


def test_repeated_crashes_stop_the_run():
    env = FakeEnv(crashes=100)

    with pytest.raises(SC2EnvError, match="simulated crash"):
        run_episodes([env], RecordingAgent(), 1, explore=True, learn=True)


# ---------------------------------------------------------------- statistics


def test_wilson_interval_matches_reference_values():
    low, high = wilson_interval(8, 10)

    assert low == pytest.approx(0.4902, abs=1e-3)
    assert high == pytest.approx(0.9433, abs=1e-3)


def test_wilson_interval_stays_inside_zero_one_at_the_extremes():
    assert wilson_interval(0, 20)[0] == 0.0
    assert wilson_interval(20, 20)[1] == 1.0
    assert wilson_interval(0, 0) == (0.0, 1.0)
