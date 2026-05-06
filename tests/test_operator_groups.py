"""Test Gallagher Operator methods."""

from typing import Any

import httpx
import respx

from gallagher_restapi import Client

from tests import filtered_response, load_fixture


async def test_get_operator_groups(
    gll_client: Client, respx_mock: respx.MockRouter
) -> None:
    """Test getting operator group items."""
    operator_groups_fixture: dict[str, Any] = load_fixture("operator_groups.json")
    respx_mock.get(
        url__regex=r"/api/operator_groups(?:/(?P<item_id>\d+))?/?(?:\?.*)?$"
    ).mock(side_effect=filtered_response(operator_groups_fixture["results"]))

    operator_groups = await gll_client.get_operator_group()
    assert len(operator_groups) == 2
    assert operator_groups[0].id == "422"
    assert operator_groups[0].name == "Admin"


async def test_get_operator_group_members(
    gll_client: Client, respx_mock: respx.MockRouter
) -> None:
    """Test getting operator group members."""
    operator_groups_fixture: dict[str, Any] = load_fixture("operator_groups.json")
    members_fixture: dict[str, Any] = load_fixture("operator_group_members.json")

    respx_mock.get(
        url__regex=r"/api/operator_groups(?:/(?P<item_id>\d+))?/?(?:\?.*)?$"
    ).mock(side_effect=filtered_response(operator_groups_fixture["results"]))
    respx_mock.get(url__regex=r"/api/operator_groups/\d+/cardholders").mock(
        return_value=httpx.Response(200, json=members_fixture)
    )

    operator_groups = await gll_client.get_operator_group(
        id="422", response_fields=["cardholders"]
    )
    assert operator_groups[0].cardholders

    operators = await gll_client.get_operator_group_members(
        href=operator_groups[0].cardholders.href, response_fields=["cardholder", "href"]
    )
    assert len(operators) == 2
    assert operators[0].cardholder.href == "https://localhost:8904/api/cardholders/363"
