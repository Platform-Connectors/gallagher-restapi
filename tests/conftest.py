"""Conftest for models tests."""

from collections.abc import AsyncGenerator

import httpx
import pytest
import respx

from gallagher_restapi import Client

from tests import load_fixture


@pytest.fixture()
async def gll_client(respx_mock: respx.MockRouter) -> AsyncGenerator[Client]:
    """Return instance of Gallagher client."""
    api_fixture = load_fixture("api.json")
    respx_mock.get("/api/").mock(return_value=httpx.Response(200, json=api_fixture))
    client = Client("api_key")
    await client.initialize()
    yield client
