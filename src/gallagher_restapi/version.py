"""Version compatibility helpers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from functools import wraps
from typing import TYPE_CHECKING, Concatenate, ParamSpec, TypeVar

from awesomeversion import AwesomeVersion

from .exceptions import VersionCompatibilityError

if TYPE_CHECKING:
    from .client import Client

P = ParamSpec("P")
R = TypeVar("R")


def min_api_version(
    required_version: str,
) -> Callable[
    [Callable[Concatenate[Client, P], Awaitable[R]]],
    Callable[Concatenate[Client, P], Awaitable[R]],
]:
    """Require a minimum API version for a client method."""

    def decorator(
        func: Callable[Concatenate[Client, P], Awaitable[R]],
    ) -> Callable[Concatenate[Client, P], Awaitable[R]]:
        @wraps(func)
        async def wrapper(self: Client, *args: P.args, **kwargs: P.kwargs) -> R:
            if self.version is None:
                raise VersionCompatibilityError(
                    "API version is unknown. Call initialize() before using this method."
                )

            if AwesomeVersion(str(self.version)) < AwesomeVersion(required_version):
                raise VersionCompatibilityError(
                    "Method requires API version "
                    f"{required_version} or newer, but connected system is "
                    f"{self.version}."
                )

            return await func(self, *args, **kwargs)

        return wrapper

    return decorator
