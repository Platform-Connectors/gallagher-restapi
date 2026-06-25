"""Tests for models module."""

from typing import Any

import pytest

from gallagher_restapi import models
from gallagher_restapi.exceptions import FeatureNotFound, LicenseError

from tests import load_fixture


def test_ftapi_features_model() -> None:
    """Validate FTApiFeatures model."""
    payload: dict[str, Any] = load_fixture("api.json")

    obj = models.FTApiFeatures.model_validate(payload["features"])

    # Ensure one of the features serializes to expected href string
    assert "/api/access_groups" in obj.access_groups()
    assert "/api/events/updates" in obj.events("updates")


def test_missing_feature() -> None:
    """Test getting a feature fails if missing."""
    api_fixture: dict[str, Any] = load_fixture("api.json")["features"]
    api_fix_modified = api_fixture.copy()
    api_fix_modified.pop("events")

    api_features = models.FTApiFeatures.model_validate(api_fix_modified)

    with pytest.raises(LicenseError):
        api_features.events("eventGroups")


def test_missing_subfeature() -> None:
    """Test getting a subfeature fails if missing."""
    api_fixture: dict[str, Any] = load_fixture("api.json")["features"]
    api_fix_modified = api_fixture.copy()
    api_fix_modified["events"].pop("eventGroups")

    api_features = models.FTApiFeatures.model_validate(api_fix_modified)

    with pytest.raises(FeatureNotFound):
        api_features.events("eventGroups")


def test_ftaccess_zone_model() -> None:
    """Validate FTAccessZone model."""
    payload: dict[str, Any] = load_fixture("access_zone.json")

    # Should not raise an error
    obj = models.FTAccessZone.model_validate(payload)
    assert isinstance(obj, models.FTAccessZone)

    # Ensure one of the features serializes to expected href string
    assert len(obj.doors) == 2
    assert obj.zone_count == 5
    assert isinstance(obj.connected_controller, models.FTItem)


def test_ftalarm_zone_model() -> None:
    """Validate FTAlarmZone model."""
    payload: dict[str, Any] = load_fixture("alarm_zone.json")

    # Should not raise an error
    obj = models.FTAlarmZone.model_validate(payload)
    assert isinstance(obj, models.FTAlarmZone)

    # Ensure one of the features serializes to expected href string
    assert obj.name == "Example alarm zone"
    assert obj.commands
    assert isinstance(obj.commands.arm, models.FTItemReference)
    assert obj.commands.user2 is None


def test_ftfence_zone_model() -> None:
    """Validate FTFenceZone model."""
    payload: dict[str, Any] = load_fixture("fence_zone.json")

    # Should not raise an error
    obj = models.FTFenceZone.model_validate(payload["results"][0])
    assert isinstance(obj, models.FTFenceZone)

    # Ensure one of the features serializes to expected href string
    assert obj.name == "Example Fence Zone"
    assert obj.voltage == 7700


def test_ftinput_model() -> None:
    """Validate FTInput model."""
    payload: dict[str, Any] = load_fixture("input.json")

    # Should not raise an error
    obj = models.FTInput.model_validate(payload)
    assert isinstance(obj, models.FTInput)

    # Ensure one of the features serializes to expected href string
    assert obj.name == "Example Input"
    assert obj.commands
    assert obj.commands.shunt


def test_ftoutput_model() -> None:
    """Validate FTOutput model."""
    payload: dict[str, Any] = load_fixture("output.json")

    # Should not raise an error
    obj = models.FTOutput.model_validate(payload)
    assert isinstance(obj, models.FTOutput)

    # Ensure one of the features serializes to expected href string
    assert obj.name == "Example Output"
    assert obj.commands
    assert obj.commands.off


def test_ftaccess_group_model() -> None:
    """Validate FTAccessGroup model."""
    access_groups: dict[str, Any] = load_fixture("access_groups.json")

    # Should not raise an error
    obj = models.FTAccessGroup.model_validate(access_groups["results"][0])
    assert isinstance(obj, models.FTAccessGroup)

    # Ensure one of the features serializes to expected href string
    assert obj.name == "Example Access Group"
    assert obj.access and len(obj.access) == 1
    assert len(obj.personal_data_definitions) == 2


def test_ftcardholder_model() -> None:
    """Validate FTCardholder model."""
    payload: dict[str, Any] = load_fixture("cardholder.json")

    # Should not raise an error
    obj = models.FTCardholder.model_validate(payload["results"][0])
    assert isinstance(obj, models.FTCardholder)

    # Ensure one of the features serializes to expected href string
    assert obj.first_name == "John"
    assert obj.last_name == "Doe"
    assert len(obj.pdfs) == 5


def test_new_cardholder_missing_first_and_last_name() -> None:
    """Validate FTCardholder model."""
    with pytest.raises(ValueError):
        models.FTNewCardholder(division=models.FTItem(href="/api/divisions/1"))


def test_ftdoor_model() -> None:
    """Validate FTDoor model."""
    payload: dict[str, Any] = load_fixture("door.json")

    # Should not raise an error
    obj = models.FTDoor.model_validate(payload)
    assert isinstance(obj, models.FTDoor)

    # Ensure one of the features serializes to expected href string
    assert obj.commands
    assert obj.commands.open
    assert obj.entry_access_zone


def test_cardholder_query_access_zones_wrong_format() -> None:
    """Validate FTCardholderQueryAccessZones model."""
    with pytest.raises(ValueError):
        models.CardholderQuery(access_zones="example zone")


def test_event_query_serialization() -> None:
    """Validate FTEventQuery model."""
    query = models.EventQuery(source=["12", "34"])

    # Ensure serialization to dict is as expected
    serialized = query.model_dump()
    assert serialized["source"] == "12,34"
