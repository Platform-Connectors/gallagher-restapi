"""Tests for API version compatibility helpers."""

import pytest

from gallagher_restapi import Client
from gallagher_restapi.exceptions import VersionCompatibilityError
from gallagher_restapi.version import min_api_version


async def test_min_api_version_raises_when_client_not_initialized(
    gll_client: Client,
) -> None:
    """Decorator should fail if client version is unknown."""

    gll_client.version = None

    @min_api_version("9.30")
    async def guarded(self: Client) -> str:
        """Test method that requires an api version."""
        return "ok"

    with pytest.raises(VersionCompatibilityError, match=r"Call initialize\(\)"):
        await guarded(gll_client)


async def test_min_api_version_raises_when_major_minor_is_lower(
    gll_client: Client,
) -> None:
    """Decorator compares major.minor when required version is major.minor."""
    gll_client.version = "9.20.0.0"

    @min_api_version("9.30")
    async def guarded(self: Client) -> str:
        """Test method that requires an api version."""
        return "ok"

    with pytest.raises(VersionCompatibilityError, match="requires API version 9.30"):
        await guarded(gll_client)


async def test_min_api_version_allows_when_major_minor_meets_requirement(
    gll_client: Client,
) -> None:
    """Decorator allows execution when major.minor is equal or newer."""
    gll_client.version = "9.30.1.2"

    @min_api_version("9.30")
    async def guarded(self: Client) -> str:
        """Test method that requires an api version."""
        return "ok"

    assert await guarded(gll_client) == "ok"
