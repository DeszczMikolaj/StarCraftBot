"""Agents: the common interface, reference agents and Model A (tabular Q-learning)."""

from scbot.agents.base import Agent
from scbot.agents.qlearning import QLearningConfig, StateDiscretizer, TabularQAgent
from scbot.agents.simple import RandomAgent, ScriptedAgent

__all__ = [
    "Agent",
    "QLearningConfig",
    "RandomAgent",
    "ScriptedAgent",
    "StateDiscretizer",
    "TabularQAgent",
]
