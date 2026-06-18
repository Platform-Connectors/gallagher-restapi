"""Tests for access groups API calls."""

from typing import Any
from unittest.mock import patch

import respx

from gallagher_restapi import Client, models

from . import filtered_response, load_fixture


async def test_get_access_group(
    gll_client: Client, respx_mock: respx.MockRouter
) -> None:
    """Test getting access group items."""
    access_groups_fixture: dict[str, Any] = load_fixture("access_groups.json")

    respx_mock.get(
        url__regex=r"/api/access_groups(?:/(?P<item_id>\d+))?/?(?:\?.*)?$"
    ).mock(side_effect=filtered_response(access_groups_fixture["results"]))

    access_groups = await gll_client.get_access_group()
    assert len(access_groups) == 2
    ag1 = access_groups[0]
    ag2 = access_groups[1]

    assert ag1.children
    assert ag1.children[0].href == ag2.href
    assert ag1.children[0].name == ag2.name
    assert ag2.parent
    assert ag2.parent.href == ag1.href
    assert ag2.parent.name == ag1.name

    access_group_with_children = await gll_client.get_access_group(
        id="349", response_fields=["children"]
    )
    assert len(access_group_with_children) == 1
    assert access_group_with_children[0].children[0].name == "Example Child Group"


async def test_get_access_group_members(gll_client: Client) -> None:
    """Test getting access group members."""
    members_href = "https://localhost:8904/api/access_groups/349/cardholders"

    with patch.object(gll_client, "_async_request") as mock_request:
        mock_request.return_value = {"cardholders": []}
        await gll_client.get_access_group_members(href=members_href)

        mock_request.assert_called_once_with("GET", members_href)


async def test_create_access_group(gll_client: Client) -> None:
    """Test creating an access group."""
    new_group = models.FTAccessGroup(
        name="New Access Group",
        description="This is a new access group",
        division=models.FTItem(href="/api/items/123"),
    )

    with patch.object(gll_client, "_async_request") as mock_request:
        mock_request.return_value = {
            "location": "https://localhost:8904/api/access_groups/999"
        }

        result = await gll_client.create_access_group(new_group)

        mock_request.assert_called_once_with(
            models.HTTPMethods.POST,
            gll_client.api_features.access_groups(),
            data=new_group,
        )
        assert result.href == "https://localhost:8904/api/access_groups/999"
