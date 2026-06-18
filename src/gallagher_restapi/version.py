"""Version compatibility helpers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from functools import wraps
from typing import TYPE_CHECKING, ParamSpec, TypeVar, cast

from awesomeversion import AwesomeVersion

from .exceptions import VersionCompatibilityError

if TYPE_CHECKING:
    from .client import Client

P = ParamSpec("P")
R = TypeVar("R")


def min_api_version(
    required_version: str,
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """Require a minimum API version for a client method."""

    def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            client = cast("Client", args[0])
            if client.version is None:
                raise VersionCompatibilityError(
                    "API version is unknown. Call initialize() before using this method."
                )

            if AwesomeVersion(str(client.version)) < AwesomeVersion(required_version):
                raise VersionCompatibilityError(
                    "Method requires API version "
                    f"{required_version} or newer, but connected system is "
                    f"{client.version}."
                )

            return await func(*args, **kwargs)

        return cast(Callable[P, Awaitable[R]], wrapper)

    return decorator
