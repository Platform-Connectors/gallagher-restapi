"""Tests for API version compatibility helpers."""

import pytest

from gallagher_restapi.exceptions import VersionCompatibilityError
from gallagher_restapi.version import min_api_version


class _DummyClient:
    def __init__(self, version: str | None) -> None:
        self.version = version

    @min_api_version("9.30")
    async def guarded(self) -> str:
        """Test method that requires an api version."""
        return "ok"


async def test_min_api_version_raises_when_client_not_initialized() -> None:
    """Decorator should fail if client version is unknown."""
    client = _DummyClient(None)

    with pytest.raises(VersionCompatibilityError, match=r"Call initialize\(\)"):
        await client.guarded()


async def test_min_api_version_raises_when_major_minor_is_lower() -> None:
    """Decorator compares major.minor when required version is major.minor."""
    client = _DummyClient("9.20.0.0")

    with pytest.raises(VersionCompatibilityError, match="requires API version 9.30"):
        await client.guarded()


async def test_min_api_version_allows_when_major_minor_meets_requirement() -> None:
    """Decorator allows execution when major.minor is equal or newer."""
    client = _DummyClient("9.30.1.2")

    assert await client.guarded() == "ok"
