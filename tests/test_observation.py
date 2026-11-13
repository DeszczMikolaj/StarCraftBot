import numpy as np
import pytest

from scbot.env.observation import (
    FEATURE_INDEX,
    FEATURE_NAMES,
    OBS_CLIP,
    OBS_DIM,
    to_raw,
    to_vector,
)


def raw_reading(**overrides: float) -> dict[str, float]:
    raw = dict.fromkeys(FEATURE_NAMES, 0.0)
    raw.update(overrides)
    return raw


def test_vector_has_one_scaled_entry_per_feature():
    obs = to_vector(raw_reading(minerals=250, supply_used=100, army_attacking=1))

    assert obs.shape == (OBS_DIM,)
    assert obs.dtype == np.float32
    assert obs[FEATURE_INDEX["minerals"]] == pytest.approx(0.25)
    assert obs[FEATURE_INDEX["supply_used"]] == pytest.approx(0.5)
    assert obs[FEATURE_INDEX["army_attacking"]] == pytest.approx(1.0)


def test_values_are_clipped_to_the_observation_range():
    obs = to_vector(raw_reading(minerals=10_000, supply_left=-3))

    assert obs[FEATURE_INDEX["minerals"]] == pytest.approx(OBS_CLIP)
    assert obs[FEATURE_INDEX["supply_left"]] == 0.0


def test_missing_feature_is_an_error():
    raw = raw_reading()
    del raw["workers"]

    with pytest.raises(KeyError, match="workers"):
        to_vector(raw)


@pytest.mark.parametrize("minerals", [0, 49, 50, 99, 100, 149, 150, 399, 400, 1337])
def test_raw_readings_survive_the_float32_round_trip(minerals):
    raw = raw_reading(minerals=minerals, workers=17, game_minutes=3.5, value_killed=4250)

    restored = to_raw(to_vector(raw))

    assert restored["minerals"] == minerals
    assert restored["workers"] == 17
    assert restored["game_minutes"] == pytest.approx(3.5)
    assert restored["value_killed"] == 4250
