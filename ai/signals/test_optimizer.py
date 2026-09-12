import math

import pytest

from ai.signals.optimizer import recommended_green


def test_green_calculation():
    green = recommended_green(score=5.0, base_green=10.0, gain=2.0)
    assert green == pytest.approx(20.0)


def test_minimum_clamp():
    green = recommended_green(score=0.0, base_green=1.0, min_green=5.0, max_green=60.0)
    assert green == pytest.approx(5.0)


def test_maximum_clamp():
    green = recommended_green(score=100.0, base_green=10.0, min_green=5.0, max_green=60.0)
    assert green == pytest.approx(60.0)


def test_zero_score_returns_base_green_min_clamped():
    assert recommended_green(score=0.0, base_green=12.0) == pytest.approx(12.0)
    assert recommended_green(score=0.0, base_green=1.0) == pytest.approx(5.0)


def test_output_always_within_bounds():
    for score in (0.0, 3.0, 7.5, 2000.0):
        green = recommended_green(score=score, base_green=8.0, min_green=4.0, max_green=30.0)
        assert 4.0 <= green <= 30.0
        assert math.isfinite(green)


def test_configurable_gain_and_bounds():
    low_gain = recommended_green(score=10.0, base_green=10.0, gain=0.5)
    high_gain = recommended_green(score=10.0, base_green=10.0, gain=3.0)
    assert low_gain == pytest.approx(15.0)
    assert high_gain == pytest.approx(40.0)


def test_current_green_acts_as_floor():
    green = recommended_green(
        score=0.0, base_green=10.0, current_green=25.0, min_green=5.0, max_green=60.0
    )
    assert green == pytest.approx(25.0)


def test_current_green_still_respects_max_green():
    green = recommended_green(
        score=100.0, base_green=10.0, current_green=90.0, min_green=5.0, max_green=60.0
    )
    assert green == pytest.approx(60.0)


def test_deterministic_repeated_execution():
    kwargs = dict(score=5.5, base_green=15.0, gain=1.5, min_green=5.0, max_green=60.0)
    first = recommended_green(**kwargs)
    second = recommended_green(**kwargs)
    assert first == second


@pytest.mark.parametrize("name", ["score", "base_green", "gain", "min_green", "max_green"])
@pytest.mark.parametrize("bad", [-1.0, float("nan"), float("inf"), float("-inf"), "abc", True])
def test_invalid_parameter_values_rejected(name, bad):
    kwargs = {
        "score": 5.0,
        "base_green": 10.0,
        "gain": 1.0,
        "min_green": 5.0,
        "max_green": 60.0,
    }
    kwargs[name] = bad
    with pytest.raises(ValueError):
        recommended_green(**kwargs)


def test_invalid_current_green_rejected():
    for bad in (-1.0, float("nan"), float("inf"), "abc", True):
        with pytest.raises(ValueError):
            recommended_green(score=5.0, base_green=10.0, current_green=bad)


def test_min_greater_than_max_rejected():
    with pytest.raises(ValueError, match="min_green"):
        recommended_green(score=5.0, base_green=10.0, min_green=70.0, max_green=60.0)


def test_return_type_is_float():
    assert isinstance(recommended_green(score=5.0, base_green=10.0), float)