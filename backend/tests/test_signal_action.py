"""Validation and contract tests for canonical SignalAction schema."""

from datetime import datetime, timezone
import json
import math

import pytest
from pydantic import ValidationError

from shared.schemas.signal_action import ActionSource, SignalAction


def _make_valid_signal_action(**overrides) -> dict:
    """Helper creating valid SignalAction kwargs."""
    data = {
        "target": "I1",
        "green_duration": 30.0,
        "source": "AI",
        "timestamp": "2026-09-12T12:00:00Z",
    }
    data.update(overrides)
    return data


class TestSignalActionContract:
    """Test suite for canonical SignalAction model."""

    # 1. Valid construction
    def test_valid_signal_action_construction(self):
        """Valid SignalAction can be created with all valid fields."""
        action = SignalAction(**_make_valid_signal_action())
        assert action.target == "I1"
        assert action.green_duration == 30.0
        assert action.source == ActionSource.AI
        assert action.source == "AI"
        assert isinstance(action.timestamp, datetime)

    def test_valid_with_datetime_object(self):
        """Valid SignalAction accepts Python datetime instances."""
        dt = datetime(2026, 9, 12, 18, 30, 0, tzinfo=timezone.utc)
        action = SignalAction(**_make_valid_signal_action(timestamp=dt))
        assert action.timestamp == dt

    def test_valid_with_enum_source(self):
        """Valid SignalAction accepts ActionSource enum instance directly."""
        action = SignalAction(**_make_valid_signal_action(source=ActionSource.FALLBACK))
        assert action.source == ActionSource.FALLBACK
        assert action.source == "FALLBACK"

    def test_valid_with_integer_green_duration(self):
        """Integer green duration is accepted and represented as float."""
        action = SignalAction(**_make_valid_signal_action(green_duration=45))
        assert isinstance(action.green_duration, float)
        assert action.green_duration == 45.0

    def test_valid_with_fractional_green_duration(self):
        """Fractional green duration is accepted."""
        action = SignalAction(**_make_valid_signal_action(green_duration=22.5))
        assert action.green_duration == 22.5

    # 2. Enum / source validation
    @pytest.mark.parametrize("valid_source", ["AI", "FALLBACK", "MANUAL"])
    def test_all_canonical_sources_accepted(self, valid_source: str):
        """All three canonical sources (AI, FALLBACK, MANUAL) are accepted."""
        action = SignalAction(**_make_valid_signal_action(source=valid_source))
        assert action.source == valid_source

    @pytest.mark.parametrize(
        "invalid_source",
        [
            "AUTO",
            "EMERGENCY",
            "ai",
            "fallback",
            "manual",
            "OTHER",
            "UNKNOWN",
            "",
            "   ",
            123,
            True,
            None,
        ],
    )
    def test_invalid_sources_rejected(self, invalid_source):
        """Non-canonical sources are strictly rejected."""
        with pytest.raises(ValidationError) as exc_info:
            SignalAction(**_make_valid_signal_action(source=invalid_source))
        assert "source" in str(exc_info.value)

    def test_action_source_enum_properties(self):
        """ActionSource enum has expected members and string behavior."""
        assert ActionSource.AI == "AI"
        assert ActionSource.FALLBACK == "FALLBACK"
        assert ActionSource.MANUAL == "MANUAL"
        assert issubclass(ActionSource, str)

    # 3. Required fields
    @pytest.mark.parametrize(
        "missing_field",
        ["target", "green_duration", "source", "timestamp"],
    )
    def test_missing_required_fields_rejected(self, missing_field: str):
        """Omitting any of the required fields raises ValidationError."""
        data = _make_valid_signal_action()
        del data[missing_field]
        with pytest.raises(ValidationError) as exc_info:
            SignalAction(**data)
        assert missing_field in str(exc_info.value)

    # 4. Invalid green_duration
    @pytest.mark.parametrize(
        "zero_duration",
        [0, 0.0, -0.0],
    )
    def test_zero_green_duration_rejected(self, zero_duration):
        """Zero green duration is rejected (must be strictly positive)."""
        with pytest.raises(ValidationError) as exc_info:
            SignalAction(**_make_valid_signal_action(green_duration=zero_duration))
        assert "green_duration" in str(exc_info.value)

    @pytest.mark.parametrize(
        "negative_duration",
        [-0.01, -1.0, -10.0, -100],
    )
    def test_negative_green_duration_rejected(self, negative_duration):
        """Negative green durations are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            SignalAction(**_make_valid_signal_action(green_duration=negative_duration))
        assert "green_duration" in str(exc_info.value)

    @pytest.mark.parametrize(
        "non_numeric_duration",
        ["fast", "thirty", "", "   ", None, [30.0], {"duration": 30}],
    )
    def test_non_numeric_green_duration_rejected(self, non_numeric_duration):
        """Non-numeric values for green_duration are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            SignalAction(**_make_valid_signal_action(green_duration=non_numeric_duration))
        assert "green_duration" in str(exc_info.value)

    def test_nan_and_inf_green_duration_rejected(self):
        """NaN and infinite green durations are rejected."""
        with pytest.raises(ValidationError):
            SignalAction(**_make_valid_signal_action(green_duration=float("nan")))
        with pytest.raises(ValidationError):
            SignalAction(**_make_valid_signal_action(green_duration=float("inf")))
        with pytest.raises(ValidationError):
            SignalAction(**_make_valid_signal_action(green_duration=float("-inf")))

    def test_small_positive_green_duration_accepted(self):
        """Small positive green duration is accepted."""
        action = SignalAction(**_make_valid_signal_action(green_duration=0.1))
        assert action.green_duration == 0.1

    # 5. Target validation
    @pytest.mark.parametrize(
        "invalid_target",
        ["", "   ", "\t\n", None, 123, []],
    )
    def test_invalid_target_rejected(self, invalid_target):
        """Empty, whitespace-only, or non-string targets are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            SignalAction(**_make_valid_signal_action(target=invalid_target))
        assert "target" in str(exc_info.value)

    # 6. Timestamp validation
    @pytest.mark.parametrize(
        "invalid_ts",
        ["not-a-datetime", "2026/09/12", "yesterday", "", None, 12345.67],
    )
    def test_invalid_timestamp_rejected(self, invalid_ts):
        """Invalid datetime representations are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            SignalAction(**_make_valid_signal_action(timestamp=invalid_ts))
        assert "timestamp" in str(exc_info.value)

    # 7. Serialization
    def test_model_dump_field_names(self):
        """model_dump produces exact canonical field names."""
        action = SignalAction(**_make_valid_signal_action())
        dumped = action.model_dump()
        expected_keys = ["target", "green_duration", "source", "timestamp"]
        assert list(dumped.keys()) == expected_keys
        assert dumped["target"] == "I1"
        assert dumped["green_duration"] == 30.0

    def test_model_dump_json_mode(self):
        """model_dump(mode='json') produces JSON-native dict with string values."""
        action = SignalAction(**_make_valid_signal_action())
        json_dict = action.model_dump(mode="json")
        assert json_dict["source"] == "AI"
        assert isinstance(json_dict["timestamp"], str)
        assert json_dict["green_duration"] == 30.0

    def test_model_dump_json_roundtrip(self):
        """JSON serialization and deserialization preserves all values."""
        action = SignalAction(**_make_valid_signal_action())
        raw_json = action.model_dump_json()

        # Check raw JSON string is valid and parseable
        parsed = json.loads(raw_json)
        assert parsed["target"] == "I1"
        assert parsed["green_duration"] == 30.0
        assert parsed["source"] == "AI"
        assert "2026-09-12" in parsed["timestamp"]

        # Validate roundtrip restoration
        reconstructed = SignalAction.model_validate_json(raw_json)
        assert reconstructed == action
