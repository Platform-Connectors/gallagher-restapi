"""Test cardholder methods."""

from datetime import datetime
from typing import Any

import httpx
import pytest
import respx

from gallagher_restapi import Client, models


@pytest.mark.asyncio
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
    gll_client: Client,
    fixtures: dict[str, Any],
    respx_mock: respx.MockRouter,
    kwargs: dict[str, Any],
) -> None:
    """Test getting cardholder with different arguments."""

    # Filter fixture based on response_fields if provided
    def filter_response(data: dict[str, Any]) -> dict[str, Any]:
        if "response_fields" not in kwargs:
            return data
        return {k: v for k, v in data.items() if k in kwargs["response_fields"]}

    cardholder_response = filter_response(fixtures["cardholder"])

    # Mock for single item retrieval (by ID)
    respx_mock.get(url__regex=r"/api/cardholders/\d+").mock(
        return_value=httpx.Response(200, json=cardholder_response)
    )
    # Mock for search/list operations
    respx_mock.get(url__regex=r"/api/cardholders$").mock(
        return_value=httpx.Response(200, json={"results": [cardholder_response]})
    )
    # Mock for search with query parameters
    respx_mock.get(url__regex=r"/api/cardholders\?.*").mock(
        return_value=httpx.Response(200, json={"results": [cardholder_response]})
    )
    respx_mock.get(url__regex=r"/api/personal_data_fields\?.*").mock(
        return_value=httpx.Response(200, json={"results": [{"id": "402"}]})
    )

    await gll_client.initialize()
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
    gll_client: Client, fixtures: dict[str, Any], respx_mock: respx.MockRouter
) -> None:
    """Test yielding cardholders with pagination."""
    cardholder = fixtures["cardholder"]

    # Mock first page with 'next' link using skip parameter
    respx_mock.get(url__regex=r"/api/cardholders\?.*top=5.*").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [cardholder] * 5,
                "next": {"href": "https://localhost:8904/api/cardholders?skip=5"},
            },
        )
    )

    # Mock second page (last page, no 'next' link)
    respx_mock.get(url__regex=r"/api/cardholders\?.*skip=5.*").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [cardholder] * 3,
                # No 'next' key to signal end of pagination
            },
        )
    )

    await gll_client.initialize()

    all_cardholders = []
    batch_count = 0

    async for cardholders in gll_client.yield_cardholders(
        top=5,
        sort=models.SortMethod.NAME_ASC,
        response_fields=["division", "personalDataFields"],
    ):
        batch_count += 1
        assert len(cardholders) <= 5
        all_cardholders.extend(cardholders)

    # Verify pagination worked correctly
    assert batch_count == 2  # 2 batches
    assert len(all_cardholders) == 8  # 5 + 3
    assert all(ch.id == "363" for ch in all_cardholders)


async def test_add_cardholder(gll_client: Client, respx_mock: respx.MockRouter) -> None:
    """Test adding a cardholder."""
    # Mock the POST request to add cardholder
    respx_mock.post("/api/cardholders").mock(
        return_value=httpx.Response(
            201,
            headers={"location": "https://localhost:8904/api/cardholders/999"},
        )
    )

    await gll_client.initialize()

    cardholder = models.FTNewCardholder(
        division=models.FTItem(href="https://localhost:8904/api/divisions/2"),
        first_name="John",
        last_name="Doe",
    )
    new_cardholder_href = await gll_client.add_cardholder(cardholder)

    assert new_cardholder_href.href == "https://localhost:8904/api/cardholders/999"


async def test_update_cardholder(
    gll_client: Client, respx_mock: respx.MockRouter
) -> None:
    """Test updating a cardholder."""
    # Mock the PATCH request to update cardholder
    respx_mock.patch(url__regex=r"/api/cardholders/363").mock(
        return_value=httpx.Response(204)
    )

    await gll_client.initialize()

    # Create card update with new active_until datetime
    card_update = models.FTCardholderCard(
        type=models.FTLinkItem(href="https://localhost:8904/api/card_types/354"),
        active_until=datetime(2025, 12, 31, 23, 59, 59),
    )

    # Create new access group with href and active_from
    new_access_group = models.FTAccessGroupMembership(
        access_group=models.FTAccessGroup(
            href="https://localhost:8904/api/access_groups/349"
        ),
        active_from=datetime(2025, 1, 1, 0, 0, 0),
    )

    # Create cardholder patch
    updated_cardholder = models.FTCardholderPatch(
        cards=models.FTCardholderCardsPatch(update=[card_update]),
        access_groups=models.FTCardholderAccessGroupsPatch(add=[new_access_group]),
        pdfs={"Email": "newemail@example.com"},
    )

    await gll_client.update_cardholder(
        "https://localhost:8904/api/cardholders/363", updated_cardholder
    )


async def test_get_card_type(gll_client: Client) -> None:
    """Test getting card types."""
    card_types = await gll_client.get_card_type()
    assert len(card_types) >= 1
    card_type = await gll_client.get_card_type(
        id=card_types[0].id, response_fields=["credentialClass"]
    )
    assert len(card_type) == 1


async def test_get_personal_data_field(gll_client: Client) -> None:
    """Test getting personal data field."""
    pdf_definitions = await gll_client.get_personal_data_field(id="404")
    assert len(pdf_definitions) >= 1
    assert pdf_definitions[0].type == models.PDFType.STRENUM
    assert pdf_definitions[0].str_enum_list == ["Dubai", "Lebanon"]
    pdf_defenition = await gll_client.get_personal_data_field(id=pdf_definitions[0].id)
    assert len(pdf_defenition) == 1


async def test_get_image_from_pdf(gll_client: Client) -> None:
    """Test getting image from personal data field."""
    cardholders = await gll_client.get_cardholder(id="378")
    cardholder = cardholders[0]
    assert cardholder.personal_data_definitions
    for pdf in cardholder.personal_data_definitions:
        for pdf_info in pdf.values():
            assert pdf_info.definition
            if pdf_info.definition.type == "image":
                assert isinstance(pdf_info.value, models.FTItemReference)
                assert pdf_info.value.href
                image = await gll_client.get_image_from_pdf(pdf_info.value.href)
                assert image is not None


async def test_get_cardholder_changes(gll_client: Client) -> None:
    """Test getting cardholder changes."""
    changes_href = await gll_client.get_cardholder_changes_href(
        response_fields=["defaults"], cardholder_fields=["cards"]
    )
    assert changes_href.href
    changes, next_link = await gll_client.get_cardholder_changes(changes_href.href)
    assert len(changes) > 0
    assert next_link


async def test_get_cardholder_personal_data_definitions(
    gll_client: Client, fixtures: dict[str, Any], respx_mock: respx.MockRouter
) -> None:
    """Test get_cardholder_personal_data_definitions returns all inherited PDFs."""
    # Mock cardholder detail
    cardholder = fixtures["cardholder"]
    respx_mock.get(url__regex=r"/api/cardholders/363").mock(
        return_value=httpx.Response(200, json=cardholder)
    )
    # Mock access group 349 (child)
    ag_349 = [ag for ag in fixtures["access_groups"] if ag["id"] == "349"][0]
    respx_mock.get(url__regex=r"/api/access_groups/349").mock(
        return_value=httpx.Response(200, json=ag_349)
    )
    # Mock access group 350 (parent)
    ag_350 = [ag for ag in fixtures["access_groups"] if ag["id"] == "350"][0]
    respx_mock.get(url__regex=r"/api/access_groups/350").mock(
        return_value=httpx.Response(200, json=ag_350)
    )

    # Run method
    await gll_client.initialize()
    pdfs = await gll_client.get_cardholder_personal_data_definitions("363")
    # pdf_names = {pdf["name"] for pdf in pdfs}
    # assert pdf_names == {"Example PDF1", "Example PDF2", "Example PDF3"}
    assert len(pdfs) == 3
    assert pdfs[2] == models.FTLinkItem(
        name="Example PDF3", href="https://localhost:8904/api/personal_data_fields/988"
    )
