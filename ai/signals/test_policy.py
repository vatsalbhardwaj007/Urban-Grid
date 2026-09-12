import math

import pytest

from ai.signals.policy import (
    DEFAULT_ARRIVAL_RATE_WEIGHT,
    DEFAULT_DOWNSTREAM_PRESSURE_WEIGHT,
    DEFAULT_QUEUE_WEIGHT,
    signal_pressure_score,
)


def test_score_calculation_with_default_weights():
    score = signal_pressure_score(
        normalized_queue=0.5,
        normalized_arrival_rate=0.3,
        downstream_pressure=0.2,
    )
    assert score == pytest.approx(1.0)


def test_score_proportional_to_components():
    low = signal_pressure_score(normalized_queue=0.1, normalized_arrival_rate=0.1, downstream_pressure=0.0)
    high = signal_pressure_score(normalized_queue=0.9, normalized_arrival_rate=0.5, downstream_pressure=0.5)
    assert high > low


def test_zero_normalized_inputs():
    assert signal_pressure_score(
        normalized_queue=0.0, normalized_arrival_rate=0.0, downstream_pressure=0.0
    ) == 0.0


def test_maximum_normalized_inputs_equal_weight_sum():
    score = signal_pressure_score(
        normalized_queue=1.0, normalized_arrival_rate=1.0, downstream_pressure=1.0
    )
    assert score == pytest.approx(
        DEFAULT_QUEUE_WEIGHT + DEFAULT_ARRIVAL_RATE_WEIGHT + DEFAULT_DOWNSTREAM_PRESSURE_WEIGHT
    )


def test_configurable_weights():
    score = signal_pressure_score(
        normalized_queue=1.0,
        normalized_arrival_rate=1.0,
        downstream_pressure=1.0,
        queue_weight=2.0,
        arrival_rate_weight=3.0,
        downstream_pressure_weight=4.0,
    )
    assert score == pytest.approx(9.0)


def test_zero_weights_disable_components():
    score = signal_pressure_score(
        normalized_queue=1.0,
        normalized_arrival_rate=1.0,
        downstream_pressure=1.0,
        queue_weight=0.0,
        arrival_rate_weight=0.0,
        downstream_pressure_weight=5.0,
    )
    assert score == pytest.approx(5.0)


def test_default_weights_are_neutral_documented_defaults():
    assert DEFAULT_QUEUE_WEIGHT == 1.0
    assert DEFAULT_ARRIVAL_RATE_WEIGHT == 1.0
    assert DEFAULT_DOWNSTREAM_PRESSURE_WEIGHT == 1.0


@pytest.mark.parametrize("name", ["normalized_queue", "normalized_arrival_rate"])
@pytest.mark.parametrize("bad", [-0.1, float("nan"), float("inf"), float("-inf"), "abc", True, None])
def test_invalid_normalized_components_rejected(name, bad):
    kwargs = {"normalized_queue": 0.5, "normalized_arrival_rate": 0.5, "downstream_pressure": 0.5}
    kwargs[name] = bad
    with pytest.raises(ValueError):
        signal_pressure_score(**kwargs)


@pytest.mark.parametrize("bad", [-0.1, float("nan"), float("inf"), float("-inf"), "abc", True, None])
def test_invalid_downstream_pressure_rejected(bad):
    with pytest.raises(ValueError):
        signal_pressure_score(normalized_queue=0.5, normalized_arrival_rate=0.5, downstream_pressure=bad)


@pytest.mark.parametrize("name", ["normalized_queue", "normalized_arrival_rate"])
def test_normalized_components_have_upper_bound(name):
    kwargs = {"normalized_queue": 0.5, "normalized_arrival_rate": 0.5, "downstream_pressure": 0.5}
    kwargs[name] = 1.1
    with pytest.raises(ValueError):
        signal_pressure_score(**kwargs)


@pytest.mark.parametrize(
    "name", ["queue_weight", "arrival_rate_weight", "downstream_pressure_weight"]
)
@pytest.mark.parametrize("bad", [-1.0, float("nan"), float("inf"), float("-inf"), "abc", True])
def test_invalid_weights_rejected(name, bad):
    kwargs = {
        "normalized_queue": 0.5,
        "normalized_arrival_rate": 0.5,
        "downstream_pressure": 0.5,
    }
    kwargs[name] = bad
    with pytest.raises(ValueError):
        signal_pressure_score(**kwargs)


def test_deterministic_repeated_execution():
    kwargs = dict(
        normalized_queue=0.4,
        normalized_arrival_rate=0.6,
        downstream_pressure=0.3,
        queue_weight=1.5,
        arrival_rate_weight=0.5,
        downstream_pressure_weight=2.0,
    )
    first = signal_pressure_score(**kwargs)
    second = signal_pressure_score(**kwargs)
    assert first == second
    assert math.isfinite(first)
    assert first >= 0.0


def test_score_preserves_downstream_pressure_uncapped():
    score = signal_pressure_score(
        normalized_queue=0.0, normalized_arrival_rate=0.0, downstream_pressure=3.5
    )
    assert score == pytest.approx(3.5)