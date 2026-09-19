"""Test Gallagher REST item methods."""

from unittest.mock import patch

import httpx
import pytest
import respx

from gallagher_restapi import Client, models


@pytest.mark.parametrize(
    "fault, message",
    [
        (True, "Client is in fault state"),
        (False, "Client is functioning correctly"),
    ],
)
async def test_set_rest_item_status(
    gll_client: Client, respx_mock: respx.MockRouter, fault: bool, message: str
) -> None:
    """Test setting the status of a REST item."""

    respx_mock.patch("/api/items/1626").mock(return_value=httpx.Response(204))

    with patch.object(gll_client, "_async_request") as mock_request:
        await gll_client.set_rest_item_status(has_fault=fault, status_msg=message)

        mock_request.assert_called_once_with(
            models.HTTPMethods.PATCH,
            "https://localhost:8904/api/items/1626",
            data=models.FTClientStatus(has_fault=fault, custom_status_text=message),
        )
