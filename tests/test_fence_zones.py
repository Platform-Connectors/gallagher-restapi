"""Test Gallagher Fence zones methods."""

from typing import Any
from unittest.mock import patch

import httpx
import respx

from gallagher_restapi import Client, models

from tests import filtered_response, load_fixture


async def test_get_fence_zone(gll_client: Client, respx_mock: respx.MockRouter) -> None:
    """Test getting a fence zone item."""
    fence_zone_fixture: dict[str, Any] = load_fixture("fence_zone.json")
    respx_mock.get(
        url__regex=r"/api/fence_zones(?:/(?P<item_id>\d+))?/?(?:\?.*)?$"
    ).mock(side_effect=filtered_response(fence_zone_fixture["results"]))

    fence_zones = await gll_client.get_fence_zone()
    assert len(fence_zones) == 2
    assert fence_zones[0].id == "443"

    fence_zone = await gll_client.get_fence_zone(
        id=fence_zones[0].id, response_fields=["voltage"]
    )
    assert len(fence_zone) == 1
    assert fence_zone[0].voltage == 7700


async def test_override_fence_zone(
    gll_client: Client, respx_mock: respx.MockRouter
) -> None:
    """Test overriding a fence zone item."""
    respx_mock.post("/api/fence_zones/443/off").mock(return_value=httpx.Response(200))

    with patch.object(gll_client, "_async_request") as mock_request:
        await gll_client.override_fence_zone(
            "https://localhost:8904/api/fence_zones/443/off"
        )

        mock_request.assert_called_once_with(
            models.HTTPMethods.POST,
            "https://localhost:8904/api/fence_zones/443/off",
        )
