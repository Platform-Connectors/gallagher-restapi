"""Test Gallagher Inputs methods."""

from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import httpx
import respx

from gallagher_restapi import Client, models

from tests import filtered_response, load_fixture


async def test_get_input(gll_client: Client, respx_mock: respx.MockRouter) -> None:
    """Test getting an input item."""
    input_fixture: dict[str, Any] = load_fixture("input.json")

    # Register mock with fixture response handler
    respx_mock.get(url__regex=r"/api/inputs(?:/(?P<item_id>\d+))?/?(?:\?.*)?$").mock(
        side_effect=filtered_response(input_fixture)
    )

    inputs = await gll_client.get_input()
    assert len(inputs) == 1
    assert inputs[0].id == "356"

    input_with_flags = await gll_client.get_input(
        id=inputs[0].id, response_fields=["statusFlags"]
    )
    assert len(input_with_flags) == 1
    assert input_with_flags[0].status_flags == ["open"]


async def test_override_input(gll_client: Client, respx_mock: respx.MockRouter) -> None:
    """Test overriding an input item."""
    respx_mock.post("/api/inputs/356/shunt").mock(return_value=httpx.Response(200))
    with patch.object(gll_client, "_async_request") as mock_request:
        await gll_client.override_input("https://localhost:8904/api/inputs/356/shunt")

        mock_request.assert_called_once_with(
            models.HTTPMethods.POST,
            "https://localhost:8904/api/inputs/356/shunt",
        )
