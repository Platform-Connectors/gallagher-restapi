"""Test getting the status of items."""

from typing import Any
from unittest.mock import patch

import httpx
import pytest
import respx

from gallagher_restapi import Client

from tests import load_fixture


def filtered_items_response_by_type(fixture_data: list[dict[str, Any]]):
    """Return a respx side effect handler that filters items by type query IDs."""
    fixtures = fixture_data

    def handler(request: httpx.Request, item_id: str | None = None) -> httpx.Response:
        if item_id:
            match = next((item for item in fixtures if item.get("id") == item_id), None)
            return httpx.Response(200, json=match)

        if type_ids_raw := request.url.params.get("type"):
            type_ids = type_ids_raw.split(",")
            filtered = [
                item for item in fixtures if item.get("type", {}).get("id") in type_ids
            ]
            return httpx.Response(200, json={"results": filtered})

        return httpx.Response(200, json={"results": fixtures})

    return handler


async def test_get_item_types(gll_client: Client, respx_mock: respx.MockRouter) -> None:
    """Test getting item types."""
    item_types_fixture: dict[str, Any] = load_fixture("item_types.json")
    respx_mock.get("/api/items/types").mock(
        return_value=httpx.Response(200, json=item_types_fixture)
    )
    item_types = await gll_client.get_item_types()
    assert len(item_types) == 5
    assert item_types["Controller 6000"] == "117"


@pytest.mark.parametrize(
    "kwargs, expected_len, expected_ids, check_type_id, check_status_flags",
    [
        # Case 1: No kwargs -> Returns all 3 items from the fixture
        ({}, 3, ["508", "526", "527"], None, None),
        # Case 2: Filter by item_types -> Returns the 2 "Controller 6000" items
        ({"item_types": ["Controller 6000"]}, 2, ["508", "526"], "117", None),
        # Case 3: Filter by single ID and specific response fields
        (
            {"id": "508", "response_fields": ["defaults", "statusFlags"]},
            1,
            ["508"],
            None,
            ["offline"],
        ),
    ],
)
@pytest.mark.asyncio
async def test_get_items(
    gll_client: Client,
    respx_mock: respx.MockRouter,
    kwargs: dict[str, Any],
    expected_len: int,
    expected_ids: list[str],
    check_type_id: str | None,
    check_status_flags: list[str] | None,
) -> None:
    """Test getting item resources with various query parameters."""
    items_fixture: list[dict[str, Any]] = load_fixture("items.json")
    respx_mock.get(url__regex=r"/api/items(?:/(?P<item_id>\d+))?/?(?:\?.*)?$").mock(
        side_effect=filtered_items_response_by_type(items_fixture)
    )

    with patch.object(
        gll_client,
        "get_item_types",
        return_value={"Controller 6000": "117", "Controller 7000": "118"},
    ) as mock_get_item_types:
        items = await gll_client.get_item(**kwargs)

    # Only assert mock call if item_types was passed
    if "item_types" in kwargs:
        mock_get_item_types.assert_called_once()

    # Verify length and exact IDs returned match the expected slice of the fixture
    assert len(items) == expected_len
    assert [item.id for item in items] == expected_ids

    # Sub-property assertions for relevant test cases
    for item in items:
        if check_type_id:
            assert item.type
            assert item.type.id == check_type_id

        if check_status_flags is not None:
            # Case 3 looks specifically for item 508's status flags
            if item.id == "508":
                assert getattr(item, "statusFlags", None) == check_status_flags


async def test_get_item_status(
    gll_client: Client, respx_mock: respx.MockRouter
) -> None:
    """Test getting the status of items from Gallagher."""
    updates: dict[str, Any] = load_fixture("item_status.json")
    respx_mock.post("/api/items/updates").mock(
        return_value=httpx.Response(200, json=updates)
    )

    controller_status, next_link = await gll_client.get_item_status(
        item_ids=["508", "526"]
    )
    assert len(controller_status) == 2
    assert controller_status[0].id == "508"
    assert controller_status[0].status_flags == ["controllerOffline"]
    assert controller_status[1].id == "526"
    assert controller_status[1].status_flags == ["disarmed"]
    assert next_link.href == updates["next"]["href"]


async def test_get_item_status_next_link(
    gll_client: Client, respx_mock: respx.MockRouter
) -> None:
    """Test that passing next_link issues a GET request to the next_link URL."""
    updates: dict[str, Any] = load_fixture("item_status.json")
    next_href = updates["next"]["href"]
    respx_mock.get(next_href).mock(return_value=httpx.Response(200, json=updates))

    with patch.object(
        gll_client, "_async_request", wraps=gll_client._async_request
    ) as mock_request:
        await gll_client.get_item_status(next_link=next_href)
        mock_request.assert_called_with("GET", next_href)


async def test_get_items_raises_for_unknown_item_type(gll_client: Client) -> None:
    """Test get_item raises ValueError for unknown item type names."""
    gll_client._item_types = {"Controller 6000": "117"}

    with pytest.raises(ValueError, match="Unknown item type: Unknown Type"):
        await gll_client.get_item(item_types=["Unknown Type"])
