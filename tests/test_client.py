"""Test getting the status of items."""

from copy import deepcopy
from ssl import SSLError

import httpx
import pytest
import respx
from pydantic import BaseModel

import gallagher_restapi.models as models
from gallagher_restapi import Client, CloudGateway
from gallagher_restapi.exceptions import (
    ConnectError,
    LicenseError,
    RequestError,
    UnauthorizedError,
)

from . import load_fixture


async def test_client_constructs_with_defaults() -> None:
    """Test that Client initializes with default localhost configuration."""
    client = Client("test-key")
    assert client.server_url == "https://localhost:8904"
    assert client.httpx_client.headers["Authorization"] == "GGL-API-KEY test-key"
    assert client.httpx_client.headers["Content-Type"] == "application/json"
    assert "IntegrationLicense" not in client.httpx_client.headers
    assert client.httpx_client.timeout.read == 60


async def test_client_constructs_with_custom_host_port() -> None:
    """Test client with custom host and port."""
    client = Client("test-key", host="custom-host", port=9000)
    assert client.server_url == "https://custom-host:9000"
    assert client.httpx_client.headers["Authorization"] == "GGL-API-KEY test-key"


@pytest.mark.parametrize(
    "gateway,expected_url",
    [
        (
            CloudGateway.AU_GATEWAY,
            "https://commandcentre-api-au.security.gallagher.cloud:443",
        ),
        (
            CloudGateway.US_GATEWAY,
            "https://commandcentre-api-us.security.gallagher.cloud:443",
        ),
    ],
)
async def test_client_uses_cloud_gateway_endpoint(
    gateway: CloudGateway, expected_url: str
) -> None:
    """Test client with cloud gateway endpoints."""
    client = Client("test-key", cloud_gateway=gateway)
    assert client.server_url == expected_url
    assert client.httpx_client.headers["Authorization"] == "GGL-API-KEY test-key"


async def test_cloud_gateway_overrides_host_and_port() -> None:
    """Ensure cloud_gateway takes precedence over host/port parameters."""
    client = Client(
        "test-key",
        host="ignored-host",
        port=1234,
        cloud_gateway=CloudGateway.AU_GATEWAY,
    )
    assert (
        client.server_url == "https://commandcentre-api-au.security.gallagher.cloud:443"
    )


async def test_client_adds_integration_license_header() -> None:
    """Test that integration license token is added to headers when provided."""
    client = Client("test-key", token="token-value")
    assert client.httpx_client.headers["IntegrationLicense"] == "token-value"


async def test_client_uses_supplied_httpx_client() -> None:
    """Test that a custom httpx AsyncClient can be provided and is properly configured."""
    custom_client = httpx.AsyncClient()
    client = Client("test-key", httpx_client=custom_client)
    assert client.httpx_client is custom_client
    assert client.httpx_client.headers["Authorization"] == "GGL-API-KEY test-key"
    assert client.httpx_client.timeout.read == 60


async def test_conn_successful(gll_client: Client) -> None:
    """Test successful connection to server."""
    await gll_client.initialize()
    assert gll_client.api_features
    assert gll_client.version == "9.30.1874.0"
    assert gll_client.api_features.doors()


async def test_wrong_api_key(gll_client: Client, respx_mock: respx.MockRouter) -> None:
    """Test using wrong api key."""

    respx_mock.get("/api/").mock(return_value=httpx.Response(401))
    with pytest.raises(
        UnauthorizedError, match="Unauthorized request. Ensure api key is correct"
    ):
        await gll_client.initialize()


async def test_feature_not_licensed(respx_mock: respx.MockRouter) -> None:
    """Test requsting a feature that is not licensed."""
    api_fixture = load_fixture("api.json")
    modified_api_fixture = deepcopy(api_fixture)
    modified_api_fixture["features"].pop("doors", None)
    respx_mock.get("/api/").mock(
        return_value=httpx.Response(200, json=modified_api_fixture)
    )
    gll_client = Client("test-key")
    await gll_client.initialize()
    with pytest.raises(LicenseError):
        await gll_client.get_door(name="Example Door")


@pytest.mark.parametrize(
    "error_class,error_message",
    [
        (httpx.RequestError, "Connection failed"),
        (SSLError, "SSL handshake failed"),
    ],
)
async def test_async_request_raises_connect_error(
    gll_client: Client,
    respx_mock: respx.MockRouter,
    error_class: type[Exception],
    error_message: str,
) -> None:
    """Test that RequestError and SSLError are converted to ConnectError."""
    endpoint = f"{gll_client.server_url}/error"

    if error_class == httpx.RequestError:
        request = httpx.Request("GET", endpoint)
        respx_mock.get("/error").mock(
            side_effect=httpx.RequestError(error_message, request=request)
        )
    else:
        respx_mock.get("/error").mock(side_effect=error_class(error_message))

    with pytest.raises(ConnectError, match=error_message):
        await gll_client._async_request(models.HTTPMethods.GET, endpoint)


@pytest.mark.parametrize(
    "status_code,expected_message",
    [
        (404, "Requested item does not exist"),
        (503, "Service Unavailable"),
    ],
)
async def test_async_request_handles_error_status_codes(
    gll_client: Client,
    respx_mock: respx.MockRouter,
    status_code: int,
    expected_message: str,
) -> None:
    """Test handling of various HTTP error status codes."""
    endpoint = f"{gll_client.server_url}/error"
    respx_mock.get("/error").mock(return_value=httpx.Response(status_code))

    with pytest.raises(RequestError, match=expected_message):
        await gll_client._async_request(models.HTTPMethods.GET, endpoint)


async def test_async_request_returns_location_for_created(
    gll_client: Client, respx_mock: respx.MockRouter
) -> None:
    """Test that 201 Created responses with location header return the location."""
    endpoint = f"{gll_client.server_url}/create"
    respx_mock.post("/create").mock(
        return_value=httpx.Response(
            201, headers={"location": "https://localhost:8904/api/items/1"}
        )
    )

    response = await gll_client._async_request(models.HTTPMethods.POST, endpoint)
    assert response == {"location": "https://localhost:8904/api/items/1"}


async def test_async_request_returns_empty_dict_for_no_content(
    gll_client: Client, respx_mock: respx.MockRouter
) -> None:
    """Test that 204 No Content responses return an empty dictionary."""
    endpoint = f"{gll_client.server_url}/delete"
    respx_mock.delete("/delete").mock(return_value=httpx.Response(204))

    response = await gll_client._async_request(models.HTTPMethods.DELETE, endpoint)
    assert response == {}


async def test_async_request_returns_json_body(
    gll_client: Client, respx_mock: respx.MockRouter
) -> None:
    """Test that 200 OK responses with JSON content-type return parsed JSON."""
    endpoint = f"{gll_client.server_url}/items"
    respx_mock.get("/items").mock(
        return_value=httpx.Response(
            200,
            json={"results": ["item"]},
            headers={"content-type": "application/json"},
        )
    )

    response = await gll_client._async_request(models.HTTPMethods.GET, endpoint)
    assert response == {"results": ["item"]}


async def test_async_request_returns_raw_content_when_not_json(
    gll_client: Client, respx_mock: respx.MockRouter
) -> None:
    """Test that non-JSON responses return raw content wrapped in results dict."""
    endpoint = f"{gll_client.server_url}/binary"
    respx_mock.get("/binary").mock(
        return_value=httpx.Response(
            200,
            content=b"payload",
            headers={"content-type": "application/octet-stream"},
        )
    )

    response = await gll_client._async_request(models.HTTPMethods.GET, endpoint)
    assert response == {"results": b"payload"}


async def test_async_request_with_query_params(
    gll_client: Client, respx_mock: respx.MockRouter
) -> None:
    """Test that query parameters are properly serialized and sent."""
    endpoint = f"{gll_client.server_url}/api/items"

    params = models.QueryBase(top=10, name="test")

    # Mock will verify the query parameters are in the request
    route = respx_mock.get("/api/items?name=test&top=10").mock(
        return_value=httpx.Response(200, json={"results": []})
    )

    await gll_client._async_request(models.HTTPMethods.GET, endpoint, params=params)
    assert route.called


async def test_async_request_with_body_data(
    gll_client: Client, respx_mock: respx.MockRouter
) -> None:
    """Test that request body data is properly serialized and sent."""
    endpoint = f"{gll_client.server_url}/items"

    class TestData(models.FTModel):
        """Test request data model."""

        name: str
        value: int

    data = TestData(name="test", value=42)

    # Mock will verify the body is JSON
    route = respx_mock.post("/items").mock(
        return_value=httpx.Response(
            201, headers={"location": "https://localhost:8904/api/items/1"}
        )
    )

    await gll_client._async_request(models.HTTPMethods.POST, endpoint, data=data)
    assert route.called
    # Verify the request had JSON content
    assert route.calls.last.request.content == b'{"name":"test","value":42}'


@pytest.mark.parametrize(
    "response_body,expected_message",
    [
        ('{"message": "Custom error from server"}', "Custom error from server"),
        ('{"message": null}', "None"),
        ("not valid json", "Unknown error"),
    ],
)
async def test_async_request_extracts_message_from_error_body(
    gll_client: Client,
    respx_mock: respx.MockRouter,
    response_body: str,
    expected_message: str,
) -> None:
    """Test that error responses extract message from JSON body or fall back to unknown."""
    endpoint = f"{gll_client.server_url}/error"
    respx_mock.get("/error").mock(
        return_value=httpx.Response(
            400,
            content=response_body.encode(),
            headers={"content-type": "application/json"},
        )
    )

    with pytest.raises(RequestError, match=expected_message):
        await gll_client._async_request(models.HTTPMethods.GET, endpoint)
