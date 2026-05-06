"""Test Gallagher Outputs methods."""

from typing import Any
from unittest.mock import patch

import httpx
import respx

from gallagher_restapi import Client, models

from tests import filtered_response, load_fixture


async def test_get_locker_bank(
    gll_client: Client, respx_mock: respx.MockRouter
) -> None:
    """Test getting a locker bank."""
    locker_banks_fixture: dict[str, Any] = load_fixture("locker_banks.json")
    respx_mock.get(
        url__regex=r"/api/locker_banks(?:/(?P<item_id>\d+))?/?(?:\?.*)?$"
    ).mock(side_effect=filtered_response(locker_banks_fixture["results"]))

    locker_banks = await gll_client.get_locker_bank(
        name="Locker Bank", response_fields=["lockers"]
    )
    assert len(locker_banks) == 2
    assert locker_banks[0].id == "771"
    assert locker_banks[0].lockers is not None
    assert len(locker_banks[0].lockers) == 1
    assert locker_banks[0].lockers[0].name == "Locker 1"


async def test_get_locker_bank_by_id(
    gll_client: Client, respx_mock: respx.MockRouter
) -> None:
    """Test getting a single locker bank by id."""
    locker_banks_fixture: dict[str, Any] = load_fixture("locker_banks.json")
    respx_mock.get(
        url__regex=r"/api/locker_banks(?:/(?P<item_id>\d+))?/?(?:\?.*)?$"
    ).mock(side_effect=filtered_response(locker_banks_fixture["results"]))

    locker_banks = await gll_client.get_locker_bank(id="771")
    assert len(locker_banks) == 1
    assert locker_banks[0].id == "771"
    assert locker_banks[0].name == "Locker Bank 1"


async def test_get_locker(gll_client: Client, respx_mock: respx.MockRouter) -> None:
    """Test getting a locker item by id."""
    locker_fixture: dict[str, Any] = load_fixture("locker.json")
    respx_mock.get("https://localhost:8904/api/lockers/801").mock(
        return_value=httpx.Response(200, json=locker_fixture)
    )

    locker = await gll_client.get_locker(id="801")
    assert locker is not None
    assert locker.name == "Locker 1"
    assert locker.connected_controller
    assert locker.connected_controller.name == "Office Controller"


async def test_override_locker(
    gll_client: Client, respx_mock: respx.MockRouter
) -> None:
    """Test overriding a locker item."""
    respx_mock.post("/api/lockers/801/assign").mock(return_value=httpx.Response(200))
    with patch.object(gll_client, "_async_request") as mock_request:
        await gll_client.override_locker(
            "https://gallaghercc:8904/api/lockers/801/assign"
        )
        mock_request.assert_called_once_with(
            models.HTTPMethods.POST,
            "https://gallaghercc:8904/api/lockers/801/assign",
        )
