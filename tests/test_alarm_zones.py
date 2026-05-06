"""Test alarm zone items."""

from datetime import datetime
from typing import Any

import httpx
import pytest
import respx

from gallagher_restapi import Client

from tests.test_access_zones import load_fixture


@pytest.mark.parametrize(
    "kwargs",
    [
        # Test getting all alarm zones
        {},
        # Test getting alarm zone by ID
        {"id": "352"},
        # Test getting alarm zone by name
        {"name": "Example"},
        # Test getting alarm zone by description
        {"description": "Example"},
        # Test getting alarm zone with division filter
        {"division": ["2"]},
        # Test getting alarm zone with sort
        {"sort": "name"},
        # Test getting alarm zone with top limit
        {"top": 10},
        # Test getting alarm zone with multiple filters
        {"name": "Example", "response_fields": ["id", "name"]},
        # Test getting alarm zone by ID with response_fields
        {"id": "352", "response_fields": ["id", "name", "commands"]},
    ],
)
async def test_get_alarm_zone(
    gll_client: Client, respx_mock: respx.MockRouter, kwargs: dict[str, Any]
) -> None:
    """Test getting alarm zone items with different arguments."""
    alarm_zone_fixture = load_fixture("alarm_zone.json")

    # Filter fixture based on response_fields if provided
    def filter_response(data: dict[str, Any]) -> dict[str, Any]:
        if "response_fields" not in kwargs:
            return data
        return {k: v for k, v in data.items() if k in kwargs["response_fields"]}

    alarm_zone_response = filter_response(alarm_zone_fixture)

    # Mock for single item retrieval (by ID)
    respx_mock.get(url__regex=r"/api/alarm_zones/\d+").mock(
        return_value=httpx.Response(200, json=alarm_zone_response)
    )
    # Mock for search/list operations
    respx_mock.get(url__regex=r"/api/alarm_zones$").mock(
        return_value=httpx.Response(200, json={"results": [alarm_zone_response]})
    )
    # Mock for search with query parameters
    respx_mock.get(url__regex=r"/api/alarm_zones\?.*").mock(
        return_value=httpx.Response(200, json={"results": [alarm_zone_response]})
    )

    alarm_zones = await gll_client.get_alarm_zone(**kwargs)

    assert alarm_zones
    assert len(alarm_zones) == 1
    assert alarm_zones[0].name == "Example alarm zone"
    assert alarm_zones[0].id == "352"


@pytest.mark.parametrize(
    ("command_name", "end_time"),
    [
        # Test basic override commands without parameters
        ("arm", None),
        ("disarm", None),
        ("user1", None),
        # Test override commands with end_time
        ("arm", "2025-12-31T23:59:59"),
        ("disarm", "2025-12-31T23:59:59"),
    ],
)
async def test_override_alarm_zone(
    gll_client: Client,
    respx_mock: respx.MockRouter,
    command_name: str,
    end_time: str | None,
) -> None:
    """Test overriding an alarm zone item with different commands."""
    alarm_zone_fixture = load_fixture("alarm_zone.json")
    # Mock the command POST endpoint (match any command)
    respx_mock.post(url__regex=r"/api/alarm_zones/352/.*").mock(
        return_value=httpx.Response(204)
    )
    # Mock getting the alarm zone with statusFlags
    respx_mock.get(url__regex=r"/api/alarm_zones/352\?.*").mock(
        return_value=httpx.Response(
            200, json={**alarm_zone_fixture, "statusFlags": [command_name]}
        ),
    )
    # Mock getting the alarm zone without query params
    respx_mock.get("/api/alarm_zones/352").mock(
        return_value=httpx.Response(200, json=alarm_zone_fixture)
    )

    alarm_zone = await gll_client.get_alarm_zone(id="352")
    assert alarm_zone
    assert alarm_zone[0].commands

    # Get the command href dynamically
    if command := getattr(alarm_zone[0].commands, command_name, None):
        await gll_client.override_alarm_zone(
            command.href,
            end_time=datetime.fromisoformat(end_time) if end_time else None,
        )

        # Verify the override was successful by checking status flags
        new_alarm_zone = await gll_client.get_alarm_zone(
            id=alarm_zone[0].id, response_fields=["statusFlags"]
        )
        # Note: In real scenario, statusFlags would reflect the command
        # For this test, we're just verifying the call was made
        assert new_alarm_zone[0].status_flags == [command_name]
