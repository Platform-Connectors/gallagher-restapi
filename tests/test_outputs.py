"""Test Gallagher Outputs methods."""

from datetime import timedelta
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import httpx
import pytest
import respx

from gallagher_restapi import Client, models

from tests import filtered_response, load_fixture


async def test_get_output(gll_client: Client, respx_mock: respx.MockRouter) -> None:
    """Test getting an output item."""
    output_fixture: dict[str, Any] = load_fixture("output.json")

    # Register mock with fixture response handler
    respx_mock.get(url__regex=r"/api/outputs(?:/(?P<item_id>\d+))?/?(?:\?.*)?$").mock(
        side_effect=filtered_response(output_fixture)
    )

    outputs = await gll_client.get_output()
    assert len(outputs) == 1
    assert outputs[0].id == "355"

    output_with_flags = await gll_client.get_output(
        id=outputs[0].id, response_fields=["statusFlags"]
    )
    assert len(output_with_flags) == 1
    assert output_with_flags[0].status_flags == ["controllerOffline"]


@pytest.mark.parametrize(
    "end_time",
    [
        timedelta(seconds=5),
        None,
    ],
)
async def test_override_output(
    gll_client: Client, respx_mock: respx.MockRouter, end_time: timedelta | None
) -> None:
    """Test overriding an output item."""
    respx_mock.post("/api/outputs/355/off").mock(return_value=httpx.Response(200))
    with patch.object(gll_client, "_async_request") as mock_request:
        await gll_client.override_output(
            "https://localhost:8904/api/outputs/355/off", end_time=end_time
        )

        mock_request.assert_called_once()
        call_args = mock_request.call_args
        assert call_args[0][0] == models.HTTPMethods.POST
        assert call_args[0][1] == "https://localhost:8904/api/outputs/355/off"
        data = call_args[1]["data"]
        assert isinstance(data, models.FTOutputCommandBody)
        if end_time is None:
            assert data.end_time is None
        else:
            assert data.end_time is not None
