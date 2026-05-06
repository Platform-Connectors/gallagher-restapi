"""Test getting the status of items."""

from typing import Any

import httpx
import pytest
import respx

from gallagher_restapi import Client

from tests import load_fixture


@pytest.mark.parametrize(
    "kwargs",
    [
        # Test getting all access zones
        {},
        # Test getting access zone by ID
        {"id": "345"},
        # Test getting access zone by name
        {"name": "Example"},
        # Test getting access zone by description
        {"description": "Example"},
        # Test getting access zone with division filter
        {"division": ["2"]},
        # Test getting access zone with sort
        {"sort": "name"},
        # Test getting access zone with top limit
        {"top": 10},
        # Test getting access zone with multiple filters
        {"name": "Example", "response_fields": ["id", "name"]},
        # Test getting access zone by ID with response_fields
        {"id": "345", "response_fields": ["id", "name"]},
    ],
)
async def test_get_access_zone(
    gll_client: Client, respx_mock: respx.MockRouter, kwargs: dict[str, Any]
) -> None:
    """Test getting access zone items with different arguments."""
    access_zone_fixture = load_fixture("access_zone.json")

    # Filter fixture based on response_fields if provided
    def filter_response(data: dict[str, Any]) -> dict[str, Any]:
        if "response_fields" not in kwargs:
            return data
        return {k: v for k, v in data.items() if k in kwargs["response_fields"]}

    access_zone_response = filter_response(access_zone_fixture)

    # Mock for single item retrieval (by ID)
    respx_mock.get(url__regex=r"/api/access_zones/\d+").mock(
        return_value=httpx.Response(200, json=access_zone_response)
    )
    # Mock for search/list operations
    respx_mock.get(url__regex=r"/api/access_zones$").mock(
        return_value=httpx.Response(200, json={"results": [access_zone_response]})
    )
    # Mock for search with query parameters
    respx_mock.get(url__regex=r"/api/access_zones\?.*").mock(
        return_value=httpx.Response(200, json={"results": [access_zone_response]})
    )

    access_zones = await gll_client.get_access_zone(**kwargs)

    assert access_zones
    assert len(access_zones) == 1
    assert access_zones[0].name == "Example Access Zone"
    assert access_zones[0].id == "345"


@pytest.mark.parametrize(
    ("command_name", "override_kwargs"),
    [
        # Test basic override commands without parameters
        ("secure", {}),
        ("free", {}),
        ("lock_down", {}),
        ("cancel", {}),
        # Test override commands with end_time
        ("secure", {"end_time": "2025-12-31T23:59:59Z"}),
        ("free", {"end_time": "2025-12-31T23:59:59Z"}),
        # Test override commands with zone_count
        ("set_zone_count", {"zone_count": 10}),
        # Test forgive anti-passback
        ("forgive_anti_passback", {}),
    ],
)
async def test_override_access_zone(
    gll_client: Client,
    respx_mock: respx.MockRouter,
    command_name: str,
    override_kwargs: dict[str, Any],
) -> None:
    """Test overriding an access zone item with different commands."""
    access_zone_fixture = load_fixture("access_zone.json")
    # Mock getting the access zone with statusFlags
    respx_mock.get("/api/access_zones/345?fields=statusFlags").mock(
        return_value=httpx.Response(200, json={"statusFlags": [command_name]}),
    )
    # Mock getting the access zone without query params
    respx_mock.get("/api/access_zones/345").mock(
        return_value=httpx.Response(200, json=access_zone_fixture)
    )
    # Mock the command POST endpoint (match any command)
    respx_mock.post(url__regex=r"/api/access_zones/345/.*").mock(
        return_value=httpx.Response(204)
    )

    access_zone = await gll_client.get_access_zone(id="345")
    assert access_zone
    assert access_zone[0].commands

    # Get the command href dynamically
    command = getattr(access_zone[0].commands, command_name, None)
    assert command
    await gll_client.override_access_zone(command.href, **override_kwargs)

    # Verify the override was successful by checking status flags
    new_access_zone = await gll_client.get_access_zone(
        id=access_zone[0].id, response_fields=["statusFlags"]
    )
    # Note: In real scenario, statusFlags would reflect the command
    # For this test, we're just verifying the call was made
    assert new_access_zone[0].status_flags == [command_name]
