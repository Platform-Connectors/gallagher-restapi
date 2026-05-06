"""Tests for Gallagher REST API client."""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import httpx


@lru_cache
def load_fixture(filename: str) -> Any:
    """Load and return fixture payload from tests/fixtures once per session.

    Tests can accept a `fixtures` parameter and read entries by key, e.g.
    `payload = fixtures["features"]`.
    """
    path = Path(__file__).parent.joinpath("fixtures", filename)
    content = path.read_text(encoding="utf-8")
    return json.loads(content)


def filtered_response(fixture_data: list[dict[str, Any]] | dict[str, Any]):
    """Create a respx side_effect handler that returns either a list or single item by ID.

    Args:
        fixture_data: A list of fixture dicts or a single fixture dict.

    Returns:
        A callable that handles requests and returns filtered responses.
        - If item_id is provided in the regex group, returns the matching single item.
        - Otherwise returns all items wrapped in {"results": [...]}.
    """
    # Normalize to always work with a list
    fixtures = fixture_data if isinstance(fixture_data, list) else [fixture_data]

    def handler(_, item_id: str | None = None) -> httpx.Response:
        if item_id:
            match = next((item for item in fixtures if item.get("id") == item_id), None)
            return httpx.Response(200, json=match)
        return httpx.Response(200, json={"results": fixtures})

    return handler
