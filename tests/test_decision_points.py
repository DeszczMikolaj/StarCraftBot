import numpy as np

from scbot.env.actions import NUM_ACTIONS, MacroAction
from scbot.env.decision_points import decision_due

LIMITS = {"wait_intervals": 7, "max_idle_intervals": 42}


def only(*actions: MacroAction) -> np.ndarray:
    mask = np.zeros(NUM_ACTIONS, dtype=bool)
    mask[list(actions)] = True
    return mask


NOTHING_TO_DO = only(MacroAction.NO_OP)
CAN_TRAIN = only(MacroAction.NO_OP, MacroAction.TRAIN_MARINE)
CAN_TRAIN_OR_BUILD = only(
    MacroAction.NO_OP, MacroAction.TRAIN_MARINE, MacroAction.BUILD_SUPPLY_DEPOT
)


def test_the_first_decision_of_a_game_is_always_due():
    assert decision_due(NOTHING_TO_DO, None, None, **LIMITS)


def test_no_decision_while_no_op_is_the_only_option():
    assert not decision_due(NOTHING_TO_DO, None, 1.0, **LIMITS)
    assert not decision_due(NOTHING_TO_DO, CAN_TRAIN, 20.0, **LIMITS)


def test_decision_as_soon_as_a_choice_exists_after_a_real_action():
    assert decision_due(CAN_TRAIN, None, 1.0, **LIMITS)


def test_no_op_holds_while_the_declined_options_stay_the_same():
    assert not decision_due(CAN_TRAIN, CAN_TRAIN, 1.0, **LIMITS)
    assert not decision_due(CAN_TRAIN, CAN_TRAIN, 6.0, **LIMITS)


def test_no_op_ends_after_the_wait_limit():
    assert decision_due(CAN_TRAIN, CAN_TRAIN, 7.0, **LIMITS)


def test_no_op_ends_early_when_a_new_option_appears():
    assert decision_due(CAN_TRAIN_OR_BUILD, CAN_TRAIN, 2.0, **LIMITS)


def test_losing_an_option_does_not_end_the_wait():
    assert not decision_due(CAN_TRAIN, CAN_TRAIN_OR_BUILD, 2.0, **LIMITS)


def test_a_decision_is_forced_after_a_long_idle_period():
    assert decision_due(NOTHING_TO_DO, None, 42.0, **LIMITS)
