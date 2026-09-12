"""Validation and contract tests for canonical RouteAction schema."""

from datetime import datetime, timezone
import json

import pytest
from pydantic import ValidationError

from shared.schemas.route_action import ActionSource, RouteAction


def _make_valid_route_action(**overrides) -> dict:
    """Helper creating valid RouteAction kwargs."""
    data = {
        "target": "veh_0",
        "route": ["E_W1_I1", "E_I1_I2", "E_I2_E1"],
        "source": "AI",
        "timestamp": "2026-09-12T12:00:00Z",
    }
    data.update(overrides)
    return data


class TestRouteActionContract:
    """Test suite for canonical RouteAction model."""

    # 1. Valid construction
    def test_valid_route_action_construction(self):
        """Valid RouteAction can be created with all valid fields."""
        action = RouteAction(**_make_valid_route_action())
        assert action.target == "veh_0"
        assert action.route == ["E_W1_I1", "E_I1_I2", "E_I2_E1"]
        assert action.source == ActionSource.AI
        assert action.source == "AI"
        assert isinstance(action.timestamp, datetime)

    def test_valid_with_single_edge_route(self):
        """A route with a single valid edge is accepted."""
        action = RouteAction(**_make_valid_route_action(route=["E_W1_I1"]))
        assert action.route == ["E_W1_I1"]

    def test_route_ordering_preserved(self):
        """Ordered sequence of edges in the route is preserved identically."""
        edges = ["edge_a", "edge_b", "edge_c", "edge_d"]
        action = RouteAction(**_make_valid_route_action(route=edges))
        assert action.route == edges
        assert action.route[0] == "edge_a"
        assert action.route[-1] == "edge_d"

    def test_valid_with_datetime_object(self):
        """Valid RouteAction accepts Python datetime instances."""
        dt = datetime(2026, 9, 12, 14, 15, 0, tzinfo=timezone.utc)
        action = RouteAction(**_make_valid_route_action(timestamp=dt))
        assert action.timestamp == dt

    def test_valid_with_enum_source(self):
        """Valid RouteAction accepts ActionSource enum instance directly."""
        action = RouteAction(**_make_valid_route_action(source=ActionSource.MANUAL))
        assert action.source == ActionSource.MANUAL
        assert action.source == "MANUAL"

    # 2. Enum / source validation
    @pytest.mark.parametrize("valid_source", ["AI", "FALLBACK", "MANUAL"])
    def test_all_canonical_sources_accepted(self, valid_source: str):
        """All three canonical sources (AI, FALLBACK, MANUAL) are accepted."""
        action = RouteAction(**_make_valid_route_action(source=valid_source))
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
            RouteAction(**_make_valid_route_action(source=invalid_source))
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
        ["target", "route", "source", "timestamp"],
    )
    def test_missing_required_fields_rejected(self, missing_field: str):
        """Omitting any of the required fields raises ValidationError."""
        data = _make_valid_route_action()
        del data[missing_field]
        with pytest.raises(ValidationError) as exc_info:
            RouteAction(**data)
        assert missing_field in str(exc_info.value)

    # 4. Invalid / empty route validation
    def test_empty_route_list_rejected(self):
        """Empty route list is strictly rejected."""
        with pytest.raises(ValidationError) as exc_info:
            RouteAction(**_make_valid_route_action(route=[]))
        assert "route" in str(exc_info.value)

    @pytest.mark.parametrize(
        "invalid_edges",
        [
            [""],
            ["   "],
            ["\t"],
            ["E_W1_I1", ""],
            ["E_W1_I1", "   ", "E_I1_I2"],
        ],
    )
    def test_route_with_empty_or_whitespace_edges_rejected(self, invalid_edges):
        """Route containing empty or whitespace-only edge strings is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            RouteAction(**_make_valid_route_action(route=invalid_edges))
        assert "route" in str(exc_info.value)

    @pytest.mark.parametrize(
        "non_list_route",
        [
            "E_W1_I1",
            123,
            None,
            {"edge": "E1"},
        ],
    )
    def test_non_list_route_rejected(self, non_list_route):
        """Non-list values for route are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            RouteAction(**_make_valid_route_action(route=non_list_route))
        assert "route" in str(exc_info.value)

    @pytest.mark.parametrize(
        "non_string_edge_list",
        [
            [123],
            [None],
            ["E1", 456],
            [["nested_edge"]],
        ],
    )
    def test_route_containing_non_strings_rejected(self, non_string_edge_list):
        """Route containing non-string items is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            RouteAction(**_make_valid_route_action(route=non_string_edge_list))
        assert "route" in str(exc_info.value)

    # 5. Target validation
    @pytest.mark.parametrize(
        "invalid_target",
        ["", "   ", "\t\n", None, 123, []],
    )
    def test_invalid_target_rejected(self, invalid_target):
        """Empty, whitespace-only, or non-string targets are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            RouteAction(**_make_valid_route_action(target=invalid_target))
        assert "target" in str(exc_info.value)

    # 6. Timestamp validation
    @pytest.mark.parametrize(
        "invalid_ts",
        ["not-a-datetime", "2026/09/12", "yesterday", "", None, 12345.67],
    )
    def test_invalid_timestamp_rejected(self, invalid_ts):
        """Invalid datetime representations are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            RouteAction(**_make_valid_route_action(timestamp=invalid_ts))
        assert "timestamp" in str(exc_info.value)

    # 7. Serialization
    def test_model_dump_field_names(self):
        """model_dump produces exact canonical field names."""
        action = RouteAction(**_make_valid_route_action())
        dumped = action.model_dump()
        expected_keys = ["target", "route", "source", "timestamp"]
        assert list(dumped.keys()) == expected_keys
        assert dumped["target"] == "veh_0"
        assert dumped["route"] == ["E_W1_I1", "E_I1_I2", "E_I2_E1"]

    def test_model_dump_json_mode(self):
        """model_dump(mode='json') produces JSON-native dict with string values."""
        action = RouteAction(**_make_valid_route_action())
        json_dict = action.model_dump(mode="json")
        assert json_dict["source"] == "AI"
        assert isinstance(json_dict["timestamp"], str)
        assert json_dict["route"] == ["E_W1_I1", "E_I1_I2", "E_I2_E1"]

    def test_model_dump_json_roundtrip(self):
        """JSON serialization and deserialization preserves all values."""
        action = RouteAction(**_make_valid_route_action())
        raw_json = action.model_dump_json()

        # Check raw JSON string is valid and parseable
        parsed = json.loads(raw_json)
        assert parsed["target"] == "veh_0"
        assert parsed["route"] == ["E_W1_I1", "E_I1_I2", "E_I2_E1"]
        assert parsed["source"] == "AI"
        assert "2026-09-12" in parsed["timestamp"]

        # Validate roundtrip restoration
        reconstructed = RouteAction.model_validate_json(raw_json)
        assert reconstructed == action
