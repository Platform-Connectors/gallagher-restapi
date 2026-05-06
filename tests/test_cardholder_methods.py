"""Test cardholder methods."""

import base64
from typing import Any
from unittest.mock import patch

import httpx
import pytest
import respx

from gallagher_restapi import Client, models

from tests import filtered_response, load_fixture


@pytest.mark.parametrize(
    "kwargs",
    [
        # Test getting cardholder by ID
        {"id": "363"},
        # Test getting cardholder by name
        {"name": "John"},
        # Test getting cardholder by description
        {"description": "description"},
        # Test getting cardholder with division filter (from fixture)
        {"division": ["1236"]},
        # Test getting cardholder with response_fields
        {"response_fields": ["id", "firstName", "lastName"]},
        # Test getting cardholder registered in access zone
        {"access_zones": "*"},
        # Test getting cardholder by PDF value (Email from fixture)
        {"pdfs": {"Email": "john.doe@example.com"}},
        # Test getting cardholder with multiple filters
        {
            "name": "John",
            "division": ["1236"],
            "response_fields": ["division", "personalDataFields"],
        },
    ],
)
async def test_get_cardholder(
    gll_client: Client, respx_mock: respx.MockRouter, kwargs: dict[str, Any]
) -> None:
    """Test getting cardholder with different arguments."""
    cardholder_fixture = load_fixture("cardholder.json")

    # Filter fixture based on response_fields if provided
    def filter_response_fields(data: dict[str, Any]) -> dict[str, Any]:
        if "response_fields" not in kwargs:
            return data
        return {k: v for k, v in data.items() if k in kwargs["response_fields"]}

    cardholder_responses = [
        filter_response_fields(cardholder)
        for cardholder in cardholder_fixture["results"]
    ]

    respx_mock.get(
        url__regex=r"/api/cardholders(?:/(?P<item_id>\d+))?/?(?:\?.*)?$"
    ).mock(side_effect=filtered_response(cardholder_responses))
    respx_mock.get(url__regex=r"/api/personal_data_fields\?.*").mock(
        return_value=httpx.Response(200, json={"results": [{"id": "402"}]})
    )

    cardholders = await gll_client.get_cardholder(**kwargs)

    assert cardholders
    assert len(cardholders) >= 1

    # Verify specific fields based on test case
    if kwargs.get("id") == "363":
        assert cardholders[0].first_name == "John"
        assert cardholders[0].last_name == "Doe"

    if "response_fields" in kwargs:
        response_fields = kwargs["response_fields"]
        if "division" in response_fields:
            assert cardholders[0].division
            assert cardholders[0].division.id == "1236"
        if "cards" in response_fields:
            assert cardholders[0].cards is not None
        if "accessGroups" in response_fields:
            assert cardholders[0].access_groups is not None
        if "lastSuccessfulAccessZone" in response_fields:
            assert cardholders[0].last_successful_access_zone


async def test_yield_cardholders(
    gll_client: Client, respx_mock: respx.MockRouter
) -> None:
    """Test yielding cardholders with pagination."""
    cardholder = load_fixture("cardholder.json")["results"]

    # Mock first page with 'next' link using skip parameter
    respx_mock.get(url__regex=r"/api/cardholders\?.*top=2.*").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": cardholder[:2],
                "next": {"href": "https://localhost:8904/api/cardholders?skip=3"},
            },
        )
    )

    # Mock second page (last page, no 'next' link)
    respx_mock.get(url__regex=r"/api/cardholders\?.*skip=3.*").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": cardholder[2:],
                # No 'next' key to signal end of pagination
            },
        )
    )

    all_cardholders = []
    batch_count = 0

    with patch("asyncio.sleep"):
        async for cardholders in gll_client.yield_cardholders(
            top=2,
            sort=models.SortMethod.NAME_ASC,
            response_fields=["division", "personalDataFields"],
        ):
            batch_count += 1
            assert len(cardholders) <= 2
            all_cardholders.extend(cardholders)

    # Verify pagination worked correctly
    assert batch_count == 2
    assert len(all_cardholders) == 3


async def test_add_cardholder(gll_client: Client, respx_mock: respx.MockRouter) -> None:
    """Test adding a cardholder."""
    # Mock the POST request to add cardholder
    respx_mock.post("/api/cardholders").mock(
        return_value=httpx.Response(
            201,
            headers={"location": "https://localhost:8904/api/cardholders/999"},
        )
    )

    cardholder = models.FTNewCardholder(
        division=models.FTItem(href="https://localhost:8904/api/divisions/2"),
        first_name="John",
        last_name="Doe",
    )
    new_cardholder_href = await gll_client.add_cardholder(cardholder)

    assert new_cardholder_href.href == "https://localhost:8904/api/cardholders/999"


async def test_update_cardholder(gll_client: Client) -> None:
    """Test updating a cardholder."""
    updated_cardholder = models.FTCardholderPatch(first_name="Tom")

    with patch.object(gll_client, "_async_request") as mock_request:
        await gll_client.update_cardholder(
            "https://localhost:8904/api/cardholders/363", updated_cardholder
        )

        # 3. Assert on the spy
        mock_request.assert_called_once_with(
            models.HTTPMethods.PATCH,
            "https://localhost:8904/api/cardholders/363",
            data=updated_cardholder,
        )


async def test_remove_cardholder(gll_client: Client) -> None:
    """Test removing a cardholder."""

    with patch.object(gll_client, "_async_request") as mock_request:
        await gll_client.remove_cardholder("https://localhost:8904/api/cardholders/363")

        # 3. Assert on the spy
        mock_request.assert_called_once_with(
            models.HTTPMethods.DELETE, "https://localhost:8904/api/cardholders/363"
        )


async def test_get_card_type(gll_client: Client, respx_mock: respx.MockRouter) -> None:
    """Test getting card types."""
    card_type_fixture: list[dict[str, Any]] = load_fixture("card_type.json")

    # Register the mock with fixture response handler
    respx_mock.get(
        url__regex=r"/api/card_types(?:/assign|/(?P<item_id>\d+))?/?(?:\?.*)?$"
    ).mock(side_effect=filtered_response(card_type_fixture))
    card_types = await gll_client.get_card_type()
    assert len(card_types) == 2

    with patch.object(
        gll_client, "_async_request", wraps=gll_client._async_request
    ) as mock_request:
        card_type = await gll_client.get_card_type(
            id="983", response_fields=["credentialClass"]
        )
        # 3. Assert on the spy
        mock_request.assert_called_once_with(
            models.HTTPMethods.GET,
            "https://localhost:8904/api/card_types/983",
            params=models.QueryBase(response_fields=["credentialClass"]),
        )
        assert len(card_type) == 1
        assert card_type[0].credential_class == "card"


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

        mock_request.assert_called_once_with(models.HTTPMethods.GET, members_href)


async def test_get_personal_data_field(
    gll_client: Client, respx_mock: respx.MockRouter
) -> None:
    """Test getting personal data field."""
    pdf_fixture: list[dict[str, Any]] = load_fixture("personal_data_fields.json")

    respx_mock.get(
        url__regex=r"/api/personal_data_fields(?:/(?P<item_id>\d+))?/?(?:\?.*)?$"
    ).mock(side_effect=filtered_response(pdf_fixture))

    pdf_definitions = await gll_client.get_personal_data_field()
    assert len(pdf_definitions) == 2

    pdf_404 = await gll_client.get_personal_data_field(id="404")
    assert len(pdf_404) == 1
    assert pdf_404[0].type == models.PDFType.STRENUM
    assert pdf_404[0].str_enum_list == ["Dubai", "Lebanon"]


@pytest.mark.parametrize("b64", [True, False])
async def test_get_image_from_pdf(
    gll_client: Client, b64: bool, respx_mock: respx.MockRouter
) -> None:
    """Test getting image from personal data field."""
    photo_href = "/api/cardholders/363/personal_data/123456"
    respx_mock.get(photo_href).mock(
        return_value=httpx.Response(
            200,
            content=b"image-bytes",
            headers={"Content-Type": "image/jpeg"},
        )
    )
    photo = await gll_client.get_image_pdf(f"http://localhost{photo_href}", b64=b64)
    if b64:
        assert photo == base64.b64encode(b"image-bytes").decode("utf-8")
    else:
        assert photo == b"image-bytes"


async def test_get_cardholder_changes(
    gll_client: Client,
    respx_mock: respx.MockRouter,
) -> None:
    """Test getting cardholder changes."""
    cardholder_changes_fixture = load_fixture("cardholder_changes.json")
    respx_mock.get("/api/cardholders/changes").mock(
        return_value=httpx.Response(200, json=cardholder_changes_fixture)
    )
    changes_href = await gll_client.get_cardholder_changes_href(
        response_fields=["defaults"], cardholder_fields=["cards"]
    )
    assert changes_href == cardholder_changes_fixture["next"]["href"]
    changes, next_link = await gll_client.get_cardholder_changes(changes_href)
    assert len(changes) == 4
    assert next_link == changes_href


async def test_get_cardholder_personal_data_definitions(
    gll_client: Client, respx_mock: respx.MockRouter
) -> None:
    """Test get_cardholder_personal_data_definitions returns all inherited PDFs."""
    # Mock cardholder detail
    access_groups_fixture: dict[str, Any] = load_fixture("access_groups.json")
    cardholder = load_fixture("cardholder.json")
    respx_mock.get(url__regex=r"/api/cardholders/(?P<item_id>\d+)").mock(
        side_effect=filtered_response(cardholder["results"])
    )
    # Mock access group 349 (child)
    ag_349 = [ag for ag in access_groups_fixture["results"] if ag["id"] == "349"][0]
    respx_mock.get(url__regex=r"/api/access_groups/349").mock(
        return_value=httpx.Response(200, json=ag_349)
    )
    # Mock access group 350 (parent)
    ag_350 = [ag for ag in access_groups_fixture["results"] if ag["id"] == "350"][0]
    respx_mock.get(url__regex=r"/api/access_groups/350").mock(
        return_value=httpx.Response(200, json=ag_350)
    )

    # Run method

    pdfs = await gll_client.get_cardholder_personal_data_definitions("364")
    assert len(pdfs) == 3
    assert pdfs[2] == models.FTLinkItem(
        name="Example PDF2", href="https://localhost:8904/api/personal_data_fields/1890"
    )
