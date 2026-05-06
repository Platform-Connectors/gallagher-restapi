"""Tests for models module."""

from typing import Any

from gallagher_restapi import models

from tests import load_fixture


def test_ftapi_features_model() -> None:
    """Validate FTApiFeatures model."""
    payload: dict[str, Any] = load_fixture("api.json")

    # Should not raise an error
    obj = models.FTApiFeatures.model_validate(payload["features"])
    assert isinstance(obj, models.FTApiFeatures)

    # Ensure one of the features serializes to expected href string
    assert "/api/access_groups" in obj.access_groups()
    assert "/api/events/updates" in obj.events("updates")


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
