"""Tests for models module."""

from gallagher_restapi import models


def test_ftapi_features_model(fixtures) -> None:
    """Validate FTApiFeatures model."""
    payload = fixtures.get("features")
    assert payload is not None, "Fixture must contain 'FTApiFeatures' key"

    # Should not raise an error
    obj = models.FTApiFeatures.model_validate(payload)
    assert isinstance(obj, models.FTApiFeatures)

    # Ensure one of the features serializes to expected href string
    assert "/api/access_groups" in obj.access_groups()
    assert "/api/events/updates" in obj.events("updates")


def test_ftaccess_zone_model(fixtures) -> None:
    """Validate FTAccessZone model."""
    payload = fixtures.get("access_zone")
    assert payload is not None, "Fixture must contain 'access_zone' key"

    # Should not raise an error
    obj = models.FTAccessZone.model_validate(payload)
    assert isinstance(obj, models.FTAccessZone)

    # Ensure one of the features serializes to expected href string
    assert len(obj.doors) == 2
    assert obj.zone_count == 5
    assert isinstance(obj.connected_controller, models.FTItem)


def test_ftalarm_zone_model(fixtures) -> None:
    """Validate FTAlarmZone model."""
    payload = fixtures.get("alarm_zone")
    assert payload is not None, "Fixture must contain 'alarm_zone' key"

    # Should not raise an error
    obj = models.FTAlarmZone.model_validate(payload)
    assert isinstance(obj, models.FTAlarmZone)

    # Ensure one of the features serializes to expected href string
    assert obj.name == "Example alarm zone"
    assert obj.commands
    assert isinstance(obj.commands.arm, models.FTItemReference)
    assert obj.commands.user2 is None


def test_ftfence_zone_model(fixtures) -> None:
    """Validate FTFenceZone model."""
    payload = fixtures.get("fence_zone")
    assert payload is not None, "Fixture must contain 'fence_zone' key"

    # Should not raise an error
    obj = models.FTFenceZone.model_validate(payload)
    assert isinstance(obj, models.FTFenceZone)

    # Ensure one of the features serializes to expected href string
    assert obj.name == "Example Fence Zone"
    assert obj.voltage == 7700


def test_ftinput_model(fixtures) -> None:
    """Validate FTInput model."""
    payload = fixtures.get("input")
    assert payload is not None, "Fixture must contain 'input' key"

    # Should not raise an error
    obj = models.FTInput.model_validate(payload)
    assert isinstance(obj, models.FTInput)

    # Ensure one of the features serializes to expected href string
    assert obj.name == "Example Input"
    assert obj.commands
    assert obj.commands.shunt


def test_ftoutput_model(fixtures) -> None:
    """Validate FTOutput model."""
    payload = fixtures.get("output")
    assert payload is not None, "Fixture must contain 'output' key"

    # Should not raise an error
    obj = models.FTOutput.model_validate(payload)
    assert isinstance(obj, models.FTOutput)

    # Ensure one of the features serializes to expected href string
    assert obj.name == "Example Output"
    assert obj.commands
    assert obj.commands.off


def test_ftaccess_group_model(fixtures) -> None:
    """Validate FTAccessGroup model."""
    access_groups = fixtures.get("access_groups")
    assert access_groups is not None, "Fixture must contain 'access_groups' key"

    # Should not raise an error
    obj = models.FTAccessGroup.model_validate(access_groups[0])
    assert isinstance(obj, models.FTAccessGroup)

    # Ensure one of the features serializes to expected href string
    assert obj.name == "Example Access Group"
    assert obj.access and len(obj.access) == 1
    assert len(obj.personal_data_definitions) == 2


def test_ftcardholder_model(fixtures) -> None:
    """Validate FTCardholder model."""
    payload = fixtures.get("cardholder")
    assert payload is not None, "Fixture must contain 'cardholder' key"

    # Should not raise an error
    obj = models.FTCardholder.model_validate(payload)
    assert isinstance(obj, models.FTCardholder)

    # Ensure one of the features serializes to expected href string
    assert obj.first_name == "John"
    assert obj.last_name == "Doe"
    assert len(obj.pdfs) == 5


def test_ftdoor_model(fixtures) -> None:
    """Validate FTDoor model."""
    payload = fixtures.get("door")
    assert payload is not None, "Fixture must contain 'door' key"

    # Should not raise an error
    obj = models.FTDoor.model_validate(payload)
    assert isinstance(obj, models.FTDoor)

    # Ensure one of the features serializes to expected href string
    assert obj.commands
    assert obj.commands.open
    assert obj.entry_access_zone
