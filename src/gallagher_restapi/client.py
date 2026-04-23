"""Gallagher REST api python library."""

import asyncio
import base64
import logging
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from json import JSONDecodeError
from ssl import SSLError
from typing import Any, cast

import httpx

from . import models
from .exceptions import ConnectError, GllApiError, RequestError, UnauthorizedError

_LOGGER = logging.getLogger(__name__)


class CloudGateway(StrEnum):
    """Cloud Gateways."""

    AU_GATEWAY = "commandcentre-api-au.security.gallagher.cloud"
    US_GATEWAY = "commandcentre-api-us.security.gallagher.cloud"


# TODO: Add wraper that checks the version and raises error if the method is not supported
class Client:
    """Gallagher REST api base client."""

    def __init__(
        self,
        api_key: str,
        *,
        host: str = "localhost",
        port: int = 8904,
        cloud_gateway: CloudGateway | None = None,
        token: str | None = None,
        httpx_client: httpx.AsyncClient | None = None,
    ) -> None:
        """Initialize REST api client.

        Args:
            api_key: Gallagher API key.
            host: Gallagher server host.
            port: Gallagher server port.
            cloud_gateway: Use cloud gateway instead of direct host/port connection.
            token: Integration license token.
            httpx_client: Custom httpx AsyncClient instance.
        """
        if cloud_gateway is not None:
            host = cloud_gateway.value
            port = 443
        self.server_url = f"https://{host}:{port}"
        self.httpx_client: httpx.AsyncClient = httpx_client or httpx.AsyncClient(
            verify=False
        )
        self.httpx_client.headers = httpx.Headers(
            {
                "Authorization": f"GGL-API-KEY {api_key}",
                "Content-Type": "application/json",
            }
        )
        if token:
            self.httpx_client.headers["IntegrationLicense"] = token
        self.httpx_client.timeout.read = 60
        self.api_features: models.FTApiFeatures = None  # type: ignore[assignment]
        self._item_types: dict[str, str] = {}
        self.event_groups: dict[str, models.FTEventGroup] = {}
        self.event_types: dict[str, models.FTEventType] = {}
        self.version: str | None = None

    async def _async_request(
        self,
        method: models.HTTPMethods,
        endpoint: str,
        *,
        params: models.QueryBase | None = None,
        data: models.FTModel | None = None,
    ) -> dict[str, Any]:
        """Send a http request and return the response.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: Full URL of the endpoint.
            params: Query parameters as a Pydantic model.
            data: Request body as a Pydantic model.

        Returns:
            The response as a dictionary.
        """
        _LOGGER.debug(
            "Sending %s request to endpoint: %s, data: %s, params: %s",
            method,
            endpoint,
            data.model_dump() if data else None,
            params.model_dump() if params else None,
        )
        try:
            response = await self.httpx_client.request(
                method,
                endpoint,
                params=params.model_dump() if params else None,
                json=data.model_dump() if data else None,
            )
        except (httpx.RequestError, SSLError) as err:
            raise ConnectError(
                f"Connection failed while sending request: {err}"
            ) from err
        _LOGGER.debug(
            "status_code: %s, response: %s", response.status_code, response.text
        )
        if httpx.codes.is_error(response.status_code):
            if response.status_code == httpx.codes.UNAUTHORIZED:
                raise UnauthorizedError(
                    "Unauthorized request. Ensure api key is correct"
                )
            if response.status_code == httpx.codes.NOT_FOUND:
                message = (
                    "Requested item does not exist or "
                    "your operator does not have the privilege to view it"
                )
            elif response.status_code == httpx.codes.SERVICE_UNAVAILABLE:
                message = "Service Unavailable"
            else:
                try:
                    message = cast(dict[str, Any], response.json()).get(
                        "message", "Invalid operation"
                    )
                except JSONDecodeError:
                    message = "Unknown error"
            raise RequestError(message)
        if response.status_code == httpx.codes.CREATED:
            return {"location": response.headers.get("location")}
        if response.status_code == httpx.codes.NO_CONTENT:
            return {}
        if "application/json" in response.headers.get("content-type"):
            return response.json()
        return {"results": response.content}

    async def initialize(self) -> None:
        """Connect to Server and construct the api features."""
        response = await self._async_request(
            models.HTTPMethods.GET, f"{self.server_url}/api/"
        )
        self.api_features = models.FTApiFeatures.model_validate(response["features"])
        self.version = response["version"]

    async def get_item_types(self) -> dict[str, str]:
        """Fetch item types from server.

        Returns:
            A dict mapping item type names to their IDs.
        """
        response = await self._async_request(
            models.HTTPMethods.GET, self.api_features.items("itemTypes")
        )
        if response.get("itemTypes"):
            self._item_types = {
                item_type["name"]: item_type["id"]
                for item_type in response["itemTypes"]
                if item_type["name"]
            }
        return self._item_types

    async def get_item(
        self,
        *,
        id: str | None = None,
        item_types: list[str] | None = None,
        name: str | None = None,
        response_fields: list[str] | None = None,
        division: list[str] | None = None,
        sort: models.SortMethod | None = None,
        top: int | None = None,
    ) -> list[models.FTItem]:
        """Retrieve items that don't have a dedicated method.

        Args:
            id: If provided, fetch a single item by ID.
            item_types: Filter by item type names; unknown types raise a ValueError.
                The names can be fetched using get_item_types().
            name: Filter by item name (substring match).
            response_fields:
                Specify the exact fields to include in the response.
                If you need the default fields to be included along with other requested fields, pass ['defaults']
                Additional fields that should be explicitly requested include ['statusFlags']
            division: Filter by division IDs.
                To get the list of divisions call this method with item_types=['Division'].
            sort: Sort the order of the results.
            top: Maximum number of results to return.

        Returns:
            A list of FTItem instances matching the filters.
        """
        if id:
            response = await self._async_request(
                models.HTTPMethods.GET,
                f"{self.api_features.items()}/{id}",
                params=models.ItemQuery(response_fields=response_fields),
            )
            return [models.FTItem.model_validate(response)]

        if item_types:
            if not self._item_types:
                await self.get_item_types()
            type_ids: list[str] = []
            for item_type in item_types or []:
                if (type_id := self._item_types.get(item_type)) is None:
                    raise ValueError(f"Unknown item type: {item_type}")
                type_ids.append(type_id)
        response = await self._async_request(
            models.HTTPMethods.GET,
            self.api_features.items(),
            params=models.ItemQuery(
                name=name,
                item_types=type_ids,
                division=division,
                response_fields=response_fields,
                sort=sort,
                top=top,
            ),
        )
        return [models.FTItem.model_validate(item) for item in response["results"]]

    # region Access zone methods
    async def get_access_zone(
        self,
        *,
        id: str | None = None,
        name: str | None = None,
        description: str | None = None,
        response_fields: list[str] | None = None,
        division: list[str] | None = None,
        sort: models.SortMethod | None = None,
        top: int | None = None,
    ) -> list[models.FTAccessZone]:
        """Retrieve the access zones configured in the system.

        If no filters are applied, all access zones will be returned.

        Args:
            id: If provided, fetch a single detailed access zone by ID.
            name: Filter by access zone name (substring match).
            description: Filter by access zone description (substring match).
            response_fields:
                Specify the exact fields to include in the response.
                If you need the default fields to be included along with other requested fields, pass ['defaults']
                Additional fields that should be explicitly requested include ['division', 'statusFlags', 'connectedController', 'doors', 'zoneCount', 'commands']
                Request these fields to get more detailed information about each access zone.
            division: Filter by division IDs.
                To get the list of divisions call get_items method with item_types=['Division'].
            sort: Sort the order of the results.
            top: Maximum number of results to return.

        Returns:
            A list of FTAccessZone objects matching the filters.
        """
        if id:
            response = await self._async_request(
                models.HTTPMethods.GET,
                f"{self.api_features.access_zones()}/{id}",
                params=models.QueryBase(response_fields=response_fields),
            )
            return [models.FTAccessZone.model_validate(response)]
        response = await self._async_request(
            models.HTTPMethods.GET,
            self.api_features.access_zones(),
            params=models.QueryBase(
                name=name,
                description=description,
                division=division,
                response_fields=response_fields,
                sort=sort,
                top=top,
            ),
        )
        return [
            models.FTAccessZone.model_validate(item) for item in response["results"]
        ]

    async def override_access_zone(
        self,
        command_href: str,
        *,
        end_time: datetime | None = None,
        zone_count: int | None = None,
    ) -> None:
        """Send a POST command to override an access zone.

        Get the command value from the commands field of the FTAccessZone object.
        Use get_access_zone() with specific id or pass 'commands' in response_fields  to get the access zone commands.

        Args:
            command_href: This is the href for the command.
            end_time: The end time for the overridden mode.
            zone_count: The zone count to set for this access zone.
        """
        await self._async_request(
            models.HTTPMethods.POST,
            command_href,
            data=models.FTAccessZoneCommandBody(
                end_time=end_time, zone_count=zone_count
            ),
        )

    # endregion Access zone methods

    # region Alarm zone methods
    async def get_alarm_zone(
        self,
        *,
        id: str | None = None,
        name: str | None = None,
        description: str | None = None,
        response_fields: list[str] | None = None,
        division: list[str] | None = None,
        sort: models.SortMethod | None = None,
        top: int | None = None,
    ) -> list[models.FTAlarmZone]:
        """Retrieve the alarm zones configured in the system.

        Args:
            id: If provided, fetch a single detailed alarm zone by ID.
            name: Filter by alarm zone name (substring match).
            description: Filter by alarm zone description (substring match).
            response_fields:
                Specify the exact fields to include in the response.
                If you need the default fields to be included along with other requested fields, pass ['defaults']
                Additional fields that should be explicitly requested include ['division', 'statusFlags', 'connectedController', 'commands']
            division: Filter by division IDs.
                To get the list of divisions call get_items method with item_types=['Division'].
            sort: Sort the order of the results.
            top: Maximum number of results to return.

        Returns:
            A list of FTAlarmZone objects matching the filters.
        """
        if id:
            response = await self._async_request(
                models.HTTPMethods.GET,
                f"{self.api_features.alarm_zones()}/{id}",
                params=models.QueryBase(response_fields=response_fields),
            )
            return [models.FTAlarmZone.model_validate(response)]

        response = await self._async_request(
            models.HTTPMethods.GET,
            self.api_features.alarm_zones(),
            params=models.QueryBase(
                name=name,
                description=description,
                division=division,
                response_fields=response_fields,
                sort=sort,
                top=top,
            ),
        )
        return [models.FTAlarmZone.model_validate(item) for item in response["results"]]

    async def override_alarm_zone(
        self, command_href: str, *, end_time: datetime | None = None
    ) -> None:
        """Send a POST command to override an alarm zone.

        Get the command value from the commands field of the FTAlarmZone object.
        Use get_alarm_zone() with specific id or pass 'commands' in response_fields  to get the alarm zone commands.

        Args:
            command_href: This is the href for the command.
            end_time: The end time for the overridden mode.
        """
        await self._async_request(
            models.HTTPMethods.POST,
            command_href,
            data=models.FTAlarmZoneCommandBody(end_time=end_time),
        )

    # endregion Alarm zone methods

    # region Fence zone methods
    async def get_fence_zone(
        self,
        *,
        id: str | None = None,
        name: str | None = None,
        description: str | None = None,
        response_fields: list[str] | None = None,
        division: list[str] | None = None,
        sort: models.SortMethod | None = None,
        top: int | None = None,
    ) -> list[models.FTFenceZone]:
        """Retrieve the fence zones configured in the system.

        Args:
            id: If provided, fetch a single detailed fence zone by ID.
            name: Filter by fence zone name (substring match).
            description: Filter by fence zone description (substring match).
            response_fields:
                Specify the exact fields to include in the response.
                If you need the default fields to be included along with other requested fields, pass ['defaults']
                Additional fields that should be explicitly requested include ['division', 'statusFlags', 'connectedController', 'voltage', 'commands']
            division: Filter by division IDs.
                To get the list of divisions call get_items method with item_types=['Division'].
            sort: Sort the order of the results.
            top: Maximum number of results to return.

        Returns:
            A list of FTFenceZone objects matching the filters.
        """
        if id:
            response = await self._async_request(
                models.HTTPMethods.GET,
                f"{self.api_features.fence_zones()}/{id}",
                params=models.QueryBase(response_fields=response_fields),
            )
            return [models.FTFenceZone.model_validate(response)]
        response = await self._async_request(
            models.HTTPMethods.GET,
            self.api_features.fence_zones(),
            params=models.QueryBase(
                name=name,
                description=description,
                division=division,
                response_fields=response_fields,
                sort=sort,
                top=top,
            ),
        )
        return [models.FTFenceZone.model_validate(item) for item in response["results"]]

    async def override_fence_zone(self, command_href: str) -> None:
        """Send a POST command to override a fence zone.

        Get the command value from the commands field of the FTFenceZone object.
        Use get_fence_zone() with specific id or pass 'commands' in response_fields  to get the fence zone commands.

        Args:
            command_href: This is the href for the command.
        """
        await self._async_request(models.HTTPMethods.POST, command_href)

    # endregion Fence zone methods

    # region Input methods
    async def get_input(
        self,
        *,
        id: str | None = None,
        name: str | None = None,
        description: str | None = None,
        response_fields: list[str] | None = None,
        division: list[str] | None = None,
        sort: models.SortMethod | None = None,
        top: int | None = None,
    ) -> list[models.FTInput]:
        """Retrieve the input items configured in the system.

        Args:
            id: If provided, fetch a single detailed input item by ID.
            name: Filter by input item name (substring match).
            description: Filter by input item description (substring match).
            response_fields:
                Specify the exact fields to include in the response.
                If you need the default fields to be included along with other requested fields, pass ['defaults']
                Additional fields that should be explicitly requested include
                ['division', 'statusFlags', 'connectedController', 'commands']
            division: Filter by division IDs.
                To get the list of divisions call get_items method with item_types=['Division'].
            sort: Sort the order of the results.
            top: Maximum number of results to return.

        Returns:
            A list of FTInput objects matching the filters.
        """
        if id:
            response = await self._async_request(
                models.HTTPMethods.GET,
                f"{self.api_features.inputs()}/{id}",
                params=models.QueryBase(response_fields=response_fields),
            )
            return [models.FTInput.model_validate(response)]
        response = await self._async_request(
            models.HTTPMethods.GET,
            self.api_features.inputs(),
            params=models.QueryBase(
                name=name,
                description=description,
                division=division,
                response_fields=response_fields,
                sort=sort,
                top=top,
            ),
        )
        return [models.FTInput.model_validate(item) for item in response["results"]]

    async def override_input(self, command_href: str) -> None:
        """Send a POST command to override an input item.

        Get the command value from the commands field of the FTInput object.
        Use get_input() with specific id or pass 'commands' in response_fields  to get the input commands.

        Args:
            command_href: This is the href for the command.
        """
        await self._async_request(models.HTTPMethods.POST, command_href)

    # endregion Input methods

    # region Output methods
    async def get_output(
        self,
        *,
        id: str | None = None,
        name: str | None = None,
        description: str | None = None,
        response_fields: list[str] | None = None,
        division: list[str] | None = None,
        sort: models.SortMethod | None = None,
        top: int | None = None,
    ) -> list[models.FTOutput]:
        """Retrieve the output items configured in the system.

        Args:
            id: If provided, fetch a single detailed output item by ID.
            name: Filter by output item name (substring match).
            description: Filter by output item description (substring match).
            response_fields:
                Specify the exact fields to include in the response.
                If you need the default fields to be included along with other requested fields, pass ['defaults']
                Additional fields that should be explicitly requested include
                ['division', 'statusFlags', 'connectedController', 'commands']
            division: Filter by division IDs.
                To get the list of divisions call get_items method with item_types=['Division'].
            sort: Sort the order of the results.
            top: Maximum number of results to return.

        Returns:
            A list of FTOutput objects matching the filters.
        """
        if id:
            response = await self._async_request(
                models.HTTPMethods.GET,
                f"{self.api_features.outputs()}/{id}",
                params=models.QueryBase(response_fields=response_fields),
            )
            return [models.FTOutput.model_validate(response)]

        response = await self._async_request(
            models.HTTPMethods.GET,
            self.api_features.outputs(),
            params=models.QueryBase(
                name=name,
                description=description,
                division=division,
                response_fields=response_fields,
                sort=sort,
                top=top,
            ),
        )
        return [models.FTOutput.model_validate(item) for item in response["results"]]

    async def override_output(
        self, command_href: str, *, end_time: datetime | timedelta | None = None
    ) -> None:
        """Send a POST command to override an input item.

        Get the command value from the commands field of the FTOutput object.
        Use get_output() with specific id or pass 'commands' in response_fields to get the output commands.

        Args:
            command_href: This is the href for the command.
            end_time: The end time for the overridden mode.
        """
        if isinstance(end_time, timedelta):
            end_time = datetime.now(timezone.utc) + end_time
        await self._async_request(
            models.HTTPMethods.POST,
            command_href,
            data=models.FTOutputCommandBody(end_time=end_time),
        )

    # endregion Output methods

    # region Door methods
    async def get_door(
        self,
        *,
        id: str | None = None,
        name: str | None = None,
        description: str | None = None,
        response_fields: list[str] | None = None,
        division: list[str] | None = None,
        sort: models.SortMethod | None = None,
        top: int | None = None,
    ) -> list[models.FTDoor]:
        """Retrieve the door items configured in the system.

        Args:
            id: If provided, fetch a single detailed door item by ID.
            name: Filter by door item name (substring match).
            description: Filter by door item description (substring match).
            response_fields:
                Specify the exact fields to include in the response.
                If you need the default fields to be included along with other requested fields, pass ['defaults']
                Additional fields that should be explicitly requested include
                ['division', 'statusFlags', 'connectedController', 'entryAccessZone', 'commands']
            division: Filter by division IDs.
                To get the list of divisions call get_items method with item_types=['Division'].
            sort: Sort the order of the results.
            top: Maximum number of results to return.

        Returns:
            A list of FTDoor objects matching the filters.
        """
        if id:
            response = await self._async_request(
                models.HTTPMethods.GET,
                f"{self.api_features.doors()}/{id}",
                params=models.QueryBase(response_fields=response_fields),
            )
            return [models.FTDoor.model_validate(response)]
        response = await self._async_request(
            models.HTTPMethods.GET,
            self.api_features.doors(),
            params=models.QueryBase(
                response_fields=response_fields,
                name=name,
                description=description,
                division=division,
                sort=sort,
                top=top,
            ),
        )
        return [models.FTDoor.model_validate(door) for door in response["results"]]

    async def override_door(self, command_href: str) -> None:
        """Send a POST command to override a door item.

        Get the command value from the commands field of the FTDoor object.
        Use get_door() with specific id or pass 'commands' in response_fields to get the door commands.

        Args:
            command_href: This is the href for the command.
        """
        await self._async_request(models.HTTPMethods.POST, command_href)

    # endregion Door methods

    # region Cardholder methods
    async def get_card_type(
        self,
        *,
        id: str | None = None,
        name: str | None = None,
        description: str | None = None,
        response_fields: list[str] | None = None,
        division: list[str] | None = None,
        sort: models.SortMethod | None = None,
        top: int | None = None,
    ) -> list[models.FTCardType]:
        """Retrieve the card type items configured in the system.

        Args:
            id: If provided, fetch a single detailed card type item by ID.
            name: Filter by card type item name (substring match).
            description: Filter by card type item description (substring match).
            response_fields:
                Specify the exact fields to include in the response.
                If you need the default fields to be included along with other requested fields, pass ['defaults']
                Additional fields that should be explicitly requested include
                ['division']
            division: Filter by division IDs.
                To get the list of divisions call get_items method with item_types=['Division'].
            sort: Sort the order of the results.
            top: Maximum number of results to return.

        Returns:
            A list of FTCardType objects matching the filters.
        """
        if id:
            response = await self._async_request(
                models.HTTPMethods.GET,
                f"{self.api_features.card_types()}/{id}",
                params=models.QueryBase(response_fields=response_fields),
            )
            return [models.FTCardType.model_validate(response)]

        response = await self._async_request(
            models.HTTPMethods.GET,
            self.api_features.card_types("assign"),
            params=models.QueryBase(
                name=name,
                description=description,
                division=division,
                response_fields=response_fields,
                sort=sort,
                top=top,
            ),
        )
        return [models.FTCardType.model_validate(item) for item in response["results"]]

    async def get_access_group(
        self,
        *,
        id: str | None = None,
        href: str | None = None,
        name: str | None = None,
        description: str | None = None,
        response_fields: list[str] | None = None,
        division: list[str] | None = None,
        sort: models.SortMethod | None = None,
        top: int | None = None,
    ) -> list[models.FTAccessGroup]:
        """Retrieve the access group items configured in the system.

        Args:
            id: If provided, fetch a single detailed access group item by ID.
            href: If provided, fetch a single detailed access group item by href.
            name: Filter by access group name (substring match).
            description: Filter by access group description (substring match).
            response_fields:
                Specify the exact fields to include in the response.
                If you need the default fields to be included along with other requested fields, pass ['defaults']
                Additional fields that should be explicitly requested include
                ['children', 'personalDataDefinitions', 'lockUnlockAccessZones',
                'enterDuringLockdown', 'firstCardUnlock', 'access', 'alarm_zones'].
            division: Filter by division IDs. To get the list of divisions
            call get_items method with item_types=['Division'].
            sort: Sort the order of the results.
            top: Maximum number of results to return.

        Returns:
            A list of FTAccessGroup objects matching the filters.
        """
        if id or href:
            response = await self._async_request(
                models.HTTPMethods.GET,
                href
                if href is not None
                else f"{self.api_features.access_groups()}/{id}",
                params=models.QueryBase(response_fields=response_fields),
            )
            return [models.FTAccessGroup.model_validate(response)]

        response = await self._async_request(
            models.HTTPMethods.GET,
            self.api_features.access_groups(),
            params=models.QueryBase(
                name=name,
                description=description,
                division=division,
                response_fields=response_fields,
                sort=sort,
                top=top,
            ),
        )
        return [
            models.FTAccessGroup.model_validate(item) for item in response["results"]
        ]

    async def get_access_group_members(
        self, href: str
    ) -> list[models.FTAccessGroupMembership]:
        """Retrieve the list of cardholders that are members of this access group.

        Args:
            href: The href to the access group members. This is the 'cardholders' field of the FTAccessGroup object.

        Returns:
            A list of FTAccessGroupMembership objects for the access group.
        """
        response = await self._async_request(models.HTTPMethods.GET, href)
        return [
            models.FTAccessGroupMembership.model_validate(item)
            for item in response["cardholders"]
        ]

    async def get_operator_group(
        self,
        *,
        name: str | None = None,
        description: str | None = None,
        response_fields: list[str] | None = None,
        division: list[str] | None = None,
        sort: models.SortMethod | None = None,
        top: int | None = None,
    ) -> list[models.FTOperatorGroup]:
        """Retrieve the operator group items configured in the system.

        Args:
            id: If provided, fetch a single detailed operator group item by ID.
            name: Filter by operator group item name (substring match).
            description: Filter by operator group item description (substring match).
            response_fields:
                Specify the exact fields to include in the response.
                If you need the default fields to be included along with other requested fields, pass ['defaults']
                Additional fields that should be explicitly requested include
                ['division', 'cardholders', 'divisions'].
            division: Filter by division IDs.
                To get the list of divisions call get_items method with item_types=['Division'].
            sort: Sort the order of the results.
            top: Maximum number of results to return.

        Returns:
            A list of FTAccessGroup objects matching the filters.
        """
        response = await self._async_request(
            models.HTTPMethods.GET,
            self.api_features.operator_groups(),
            params=models.QueryBase(
                name=name,
                description=description,
                division=division,
                response_fields=response_fields,
                sort=sort,
                top=top,
            ),
        )
        return [
            models.FTOperatorGroup.model_validate(item) for item in response["results"]
        ]

    async def get_operator_group_members(
        self, href: str, *, response_fields: list[str] | None = None
    ) -> list[models.FTOperatorGroupMembership]:
        """Retrieve the list of operators that are members of this operator group.

        Args:
            href: The href to the operator group members. this is the 'cardholders' field of the FTOperatorGroup object.
            response_fields: To get the href field in FTOperatorGroupMembership use ['cardholder', 'href'] in response_fields.

        Returns:
            A list of FTOperatorGroupMembership objects matching the filters.
        """
        response = await self._async_request(
            models.HTTPMethods.GET,
            href,
            params=models.QueryBase(response_fields=response_fields),
        )
        return [
            models.FTOperatorGroupMembership.model_validate(item)
            for item in response["cardholders"]
        ]

    async def get_personal_data_field(
        self,
        *,
        id: str | None = None,
        name: str | None = None,
        description: str | None = None,
        response_fields: list[str] | None = None,
        division: list[str] | None = None,
        sort: models.SortMethod | None = None,
        top: int | None = None,
    ) -> list[models.FTPersonalDataFieldDefinition]:
        """Retrieve the personal data field items configured in the system.

        Args:
            id: If provided, fetch a single detailed personal data field item by ID.
            name: Filter by personal data field item name (substring match).
            description: Filter by personal data field item description (substring match).
            response_fields:
                Specify the exact fields to include in the response.
                If you need the default fields to be included along with other requested fields, pass ['defaults']
                Additional fields that should be explicitly requested include
                ['description', 'division', 'type', 'accessGroups,
                'isProfileImage', 'unique'].
            division: Filter by division IDs.
                To get the list of divisions call get_items method with item_types=['Division'].
            sort: Sort the order of the results.
            top: Maximum number of results to return.

        Returns:
            A list of FTPersonalDataFieldDefinition objects matching the filters.
        """
        if id:
            response = await self._async_request(
                models.HTTPMethods.GET,
                f"{self.api_features.personal_data_fields()}/{id}",
                params=models.QueryBase(response_fields=response_fields),
            )
            return [models.FTPersonalDataFieldDefinition.model_validate(response)]

        response = await self._async_request(
            models.HTTPMethods.GET,
            self.api_features.personal_data_fields(),
            params=models.QueryBase(
                name=name,
                description=description,
                response_fields=response_fields,
                division=division,
                sort=sort,
                top=top,
            ),
        )
        return [
            models.FTPersonalDataFieldDefinition.model_validate(pdf)
            for pdf in response["results"]
        ]

    async def get_cardholder_personal_data_definitions(
        self, cardholder_id: str
    ) -> list[models.FTLinkItem]:
        """
        Return all PersonalDataFieldDefinition objects for a cardholder, including those inherited from all direct and indirect access groups.

        Args:
            cardholder_id: The ID of the cardholder.

        Returns:
            List of FTLinkItem objects.
        """
        # Step 1: Get cardholder with accessGroups field
        if not (
            cardholders := await self.get_cardholder(
                id=cardholder_id, response_fields=["accessGroups"]
            )
        ):
            return []
        cardholder = cardholders[0]
        if not cardholder.access_groups:
            return []

        # Step 2: Collect all access group hrefs (direct and indirect)
        seen = set()
        to_visit: list[str] = []
        for agm in cast(list[models.FTAccessGroupMembership], cardholder.access_groups):
            if agm.access_group and agm.access_group.href:
                to_visit.append(agm.access_group.href)

        pdf_defs: dict[str, models.FTLinkItem] = {}
        while to_visit:
            if (href := to_visit.pop()) in seen:
                continue
            seen.add(href)
            # Fetch group with personalDataDefinitions and parent
            groups = await self.get_access_group(
                response_fields=["personalDataDefinitions", "parent"], href=href
            )
            if not groups:
                continue
            group = groups[0]
            # Store full PDF objects from this group, keyed by href for uniqueness
            for pdf_def in group.personal_data_definitions:
                pdf_defs[cast(str, pdf_def.href)] = pdf_def
            # If parent is a list (multiple parents), add all
            if group.parent:
                to_visit.append(cast(str, group.parent.href))

        # Step 4: Return all unique PDF definition objects
        return list(pdf_defs.values())

    async def get_image_pdf(
        self, pdf_href: str, b64: bool = False
    ) -> bytes | str | None:
        """Return the image content from the PDF href.

        Args:
            pdf_href: The href to the personal data field that contains the image.
            b64: If True, return the image as a base64 string. If False, return as bytes.

        Returns:
            The image content as bytes or base64 string, or None if not found.
        """
        if response := await self._async_request(models.HTTPMethods.GET, pdf_href):
            if not isinstance(response.get("results"), bytes):
                raise ValueError(f"{pdf_href} is not an image href")
            return (
                base64.b64encode(response["results"]).decode("utf-8")
                if b64
                else response["results"]
            )
        return None

    async def _search_cardholders(
        self, query: models.CardholderQuery
    ) -> dict[str, Any]:
        """Retrieve the cardholder items configured in the system.

        This is in internal method. use get_cardholder() or yield_cardholders() methods.

        Args:
            query: The CardholderQuery object containing the search parameters.

        Returns:
            A response dict from the query.
        """
        if query.pdfs:
            pdf_dict: dict[str, str] = {}
            for name, value in query.pdfs.items():
                if str(name).isdigit():
                    pdf_id = str(name)
                else:
                    pdf_field = await self.get_personal_data_field(
                        name=name, response_fields=["id"]
                    )
                    if not pdf_field:
                        raise GllApiError(f"pdf field: {name} not found")
                    assert pdf_field[0].id
                    pdf_id = pdf_field[0].id
                pdf_dict[f"pdf_{pdf_id}"] = value
            query.pdfs = pdf_dict

        return await self._async_request(
            models.HTTPMethods.GET, self.api_features.cardholders(), params=query
        )

    async def get_cardholder(
        self,
        *,
        id: str | None = None,
        name: str | None = None,
        description: str | None = None,
        access_zones: str | list[str] | None = None,
        pdfs: dict[str, str] | None = None,
        response_fields: list[str] | None = None,
        division: list[str] | None = None,
        sort: models.SortMethod | None = None,
        top: int | None = None,
    ) -> list[models.FTCardholder]:
        """Retrieve the cardholder items configured in the system.

        This will return the top 100 or 1000 results (depending on the version of CC) or what you specify in top parameter.
        If you want to get all cardholders consider using yield_cardholders() method.

        Args:
            id: If provided, fetch a single detailed cardholder item by ID.
            name: Filter by cardholder item name (substring match).
            description: Filter by cardholder item description (substring match).
            access_zones: Filter cardholders that are currently registered inside an access zone.
                Pass a list of access zone ids. To get the list of access zones call get_access_zone() method.
                Pass '*' to get cardholders that registered inside any access zone.
                Ignore it to not filter by access zones presence.
                pass "lastSuccessfulAccessZone" in response_fields to get the name of the registered access zone.
            pdfs: Provide a dict of personal field ID or name and value to filter by personal data fields.
                Example: {'1': 'John'} or {'EmployeeID': '12345'}
            response_fields:
                Specify the exact fields to include in the response.
                If you need the default fields to be included along with other requested fields, pass ['defaults']
                Additional fields that should be explicitly requested include
                ['division', 'personalDataFields', 'cards', 'accessGroups']. Refer to the FTCardholder model for other available fields
            division: Filter by division IDs.
                For example, to get the personal fields in the results pass ["personalDataFields"].
                To get the list of divisions call get_items method with item_types=['Division'].
            sort: Sort the order of the results.
            top: Maximum number of results to return.

        Returns:
            A list of FTCardholder objects matching the filters.
        """
        if id:
            response = await self._async_request(
                models.HTTPMethods.GET,
                f"{self.api_features.cardholders()}/{id}",
                params=models.QueryBase(response_fields=response_fields),
            )
            return [models.FTCardholder.model_validate(response)]

        query = models.CardholderQuery(
            name=name,
            description=description,
            access_zones=access_zones,
            pdfs=pdfs,
            response_fields=response_fields,
            division=division,
            sort=sort,
            top=top,
        )
        response = await self._search_cardholders(query)
        return [
            models.FTCardholder.model_validate(cardholder)
            for cardholder in response["results"]
        ]

    async def yield_cardholders(
        self,
        *,
        name: str | None = None,
        description: str | None = None,
        access_zones: str | list[str] | None = None,
        pdfs: dict[str, str] | None = None,
        response_fields: list[str] | None = None,
        division: list[str] | None = None,
        sort: models.SortMethod | None = None,
        top: int | None = None,
    ) -> AsyncGenerator[list[models.FTCardholder]]:
        """Returns an Iterator over the cardholder items configured in the system.

        This is useful for looping over cardholder in batches. Each iteration returns the number of cardholders specified in the top parameter (default 100 or 1000 depending on the version of CC).

        Args:
            name: Filter by cardholder item name (substring match).
            description: Filter by cardholder item description (substring match).
            description: Filter by cardholder item description (substring match).
            access_zones: Filter cardholders that are currently registered inside an access zone.
                Pass a list of access zone ids. To get the list of access zones call get_access_zone() method.
                Pass '*' to get cardholders that registered inside any access zone.
                Ignore it to not filter by access zones presence.
                pass "lastSuccessfulAccessZone" in response_fields to get the name of the registered access zone.
            pdfs: Provide a dict of personal field ID or name and value to filter by personal data fields.
                Example: {'1': 'John'} or {'EmployeeID': '12345'}
            response_fields:
                Specify the exact fields to include in the response.
                If you need the default fields to be included along with other requested fields, pass ['defaults']
                Additional fields that should be explicitly requested include
                ['division', 'personalDataFields', 'cards', 'accessGroups']. Refer to the FTCardholder model for other available fields
            division: Filter by division IDs.
                To get the list of divisions call get_items method with item_types=['Division'].
            sort: Sort the order of the results.
            top: Maximum number of results to return.

        Returns:
            An Async Iterator of FTCardholder objects matching the filters.
        """
        query = models.CardholderQuery(
            name=name,
            description=description,
            access_zones=access_zones,
            pdfs=pdfs,
            response_fields=response_fields,
            division=division,
            sort=sort,
            top=top or 100,
        )
        response = await self._search_cardholders(query)
        while True:
            _LOGGER.debug(response)
            yield [
                models.FTCardholder.model_validate(cardholder)
                for cardholder in response["results"]
            ]
            await asyncio.sleep(1)
            if not (next_link := response.get("next")):
                break
            response = await self._async_request(
                models.HTTPMethods.GET, next_link["href"]
            )

    async def get_cardholder_changes(
        self, changes_href: str
    ) -> tuple[list[models.CardholderChange], str]:
        """Return list of cardholder changes.

        Args:
            changes_href: The href to get the cardholder changes. Get this href from get_cardholder_changes_href method.

        Returns:
            A tuple of list of CardholderChange objects and the next href to get new changes.
        """
        response = await self._async_request(models.HTTPMethods.GET, changes_href)
        changes = [
            models.CardholderChange.model_validate(change)
            for change in response["results"]
        ]
        return changes, response["next"]["href"]

    async def get_cardholder_changes_href(
        self,
        *,
        filter: list[str] | None = None,
        cardholder_fields: list[str] | None = None,
        response_fields: list[str] | None = None,
        top: int | None = None,
    ) -> str:
        """Construct the filtered cardholder changes that you want to monitor.

        Args:
            filter: List of cardholder fields that you want to monitor. Refer to the FTCardholder model for available fields.
                Example: ['name', 'cards','cards.from', 'accessGroups']
            cardholder_fields: List of cardholder fields to include in the response.
                Example: ['id', 'name', 'cards', 'cards.from', 'accessGroups', 'division', 'personalDataDefinitions']. Refer to the FTCardholder model for other available fields
            response_fields:
                Specify the fields to include in the response.
                Possible values are
                ['href', 'operator', 'operator.href', 'operator.name',
                'time', 'type', 'item', 'oldValues', 'newValues', 'cardholder']
            top: Maximum number of results to return.

        Returns:
            The href string to get the cardholder changes.
        """
        response = await self._async_request(
            models.HTTPMethods.GET,
            self.api_features.cardholders("changes"),
            params=models.CardholderChangesQuery(
                filter=filter,
                cardholder_fields=cardholder_fields,
                response_fields=response_fields,
                top=top,
            ),
        )
        return response["next"]["href"]

    async def add_cardholder(
        self, cardholder: models.FTNewCardholder
    ) -> models.FTItemReference:
        """Add a new cardholder in Gallagher.

        Args:
            cardholder: The constructed FTCardholder object containing the cardholder details. Or a dict with the cardholder data which will be used to construct the object.

        Returns:
            The FTItemReference to the newly created cardholder.
        """
        response = await self._async_request(
            models.HTTPMethods.POST, self.api_features.cardholders(), data=cardholder
        )
        return models.FTItemReference(href=response.get("location", ""))

    async def update_cardholder(
        self,
        cardholder_href: str,
        patched_cardholder: models.FTCardholderPatch,
    ) -> None:
        """Update existing cardholder in the system.

        Args:
            cardholder_href: The href of the cardholder to update.
            patched_cardholder: The patched FTCardholder object containing the updated cardholder details.
        """
        await self._async_request(
            models.HTTPMethods.PATCH, cardholder_href, data=patched_cardholder
        )

    async def remove_cardholder(self, cardholder_href: str) -> None:
        """Remove existing cardholder in Gallagher.

        Args:
            cardholder_href: The href of the cardholder to remove.
        """
        await self._async_request(models.HTTPMethods.DELETE, cardholder_href)

    # endregion Cardholder methods

    # region Event methods

    async def _fetch_event_types_and_groups(self) -> None:
        """Internal method to fetch event groups and types from server."""
        response = await self._async_request(
            models.HTTPMethods.GET, self.api_features.events("eventGroups")
        )

        for item in response["eventGroups"]:
            event_group = models.FTEventGroup.model_validate(item)
            self.event_groups[event_group.name] = event_group

        for event_group in self.event_groups.values():
            self.event_types.update(
                {event_type.name: event_type for event_type in event_group.event_types}
            )

    async def get_event_types(self) -> dict[str, models.FTEventType]:
        """Return the dictionary of event types."""
        if not self.event_types:
            await self._fetch_event_types_and_groups()
        return self.event_types

    async def get_event_groups(self) -> dict[str, models.FTEventGroup]:
        """Return the dictionary of event groups."""
        if not self.event_groups:
            await self._fetch_event_types_and_groups()
        return self.event_groups

    async def get_events(
        self, event_filter: models.EventQuery | None = None
    ) -> list[models.FTEvent]:
        """Return list of events filtered by params.

        By default the result will contain no more than 1000 events.
        For efficient transfer of large numbers of events you can increase this using the 'top' field in the event query.

        Args:
            event_filter: The EventQuery object containing the filter parameters.

        Returns:
            A list of FTEvent objects matching the filters.
        """
        response = await self._async_request(
            models.HTTPMethods.GET, self.api_features.events(), params=event_filter
        )
        return [models.FTEvent.model_validate(event) for event in response["events"]]

    async def yield_events(
        self,
        event_filter: models.EventQuery | None = None,
    ) -> AsyncGenerator[list[models.FTEvent]]:
        """This method yields all events based on the filter.

        This method calls the 'next' link until all events are retrieved.

        Args:
            event_filter: The EventQuery object containing the filter parameters.

        Yields:
            A list of FTEvent objects matching the filters.
        """
        response = await self._async_request(
            models.HTTPMethods.GET, self.api_features.events(), params=event_filter
        )
        while True:
            _LOGGER.debug(response)
            events = [
                models.FTEvent.model_validate(event) for event in response["events"]
            ]
            if not events:
                break
            yield events
            response = await self._async_request(
                models.HTTPMethods.GET, response["next"]["href"]
            )

    async def yield_new_events(
        self, event_filter: models.EventQuery | None = None, from_past: bool = False
    ) -> AsyncGenerator[list[models.FTEvent]]:
        """Yield a list of new events filtered by params.

        This creates a generator for new events that match the specified filters.

        Args:
            event_filter: The EventQuery object containing the filter parameters.
            from_past: If True, fetch events from past matching the filter before yielding new events.

        Yields:
            A list of FTEvent objects matching the filters.
        """
        response = await self._async_request(
            models.HTTPMethods.GET,
            self.api_features.events("updates" if not from_past else None),
            params=event_filter,
        )
        while True:
            _LOGGER.debug(response)
            yield [models.FTEvent.model_validate(event) for event in response["events"]]
            await asyncio.sleep(1)
            response = await self._async_request(
                models.HTTPMethods.GET, response["updates"]["href"]
            )

    async def push_event(self, event: models.EventPost) -> models.FTItemReference:
        """Push a new event to Gallagher and return the event href.

        Args:
            event: The EventPost object containing the event details.

        Returns:
            The FTItemReference to the newly created event, or None if not available.
        """
        response = await self._async_request(
            models.HTTPMethods.POST, self.api_features.events(), data=event
        )
        return models.FTItemReference(href=response.get("location", ""))

    # endregion Event methods

    # region Alarm methods

    async def get_alarms(
        self, response_fields: list[str] | None = None
    ) -> list[models.FTAlarm]:
        """Return list of alarms.

        Args:
            response_fields:
                Specify the exact fields to include in the response.
                If you need the default fields to be included along with other requested fields, pass ['defaults']
                Additional fields that should be explicitly requested include
                ['details', 'history', 'instruction', 'cardholder']

        Returns:
            A list of FTAlarm objects.
        """
        alarms: list[models.FTAlarm] = []
        if response := await self._async_request(
            models.HTTPMethods.GET,
            self.api_features.alarms(),
            params=models.QueryBase(response_fields=response_fields),
        ):
            alarms = [
                models.FTAlarm.model_validate(alarm) for alarm in response["alarms"]
            ]
            while "next" in response:
                if response2 := await self._async_request(
                    models.HTTPMethods.GET,
                    response["next"]["href"],
                    params=models.QueryBase(response_fields=response_fields),
                ):
                    alarms.extend(
                        models.FTAlarm.model_validate(alarm)
                        for alarm in response2["alarms"]
                    )
        return alarms

    async def yield_new_alarms(
        self, response_fields: list[str] | None = None
    ) -> AsyncGenerator[list[models.FTAlarm]]:
        """Yield a list of new alarms.

        Args:
            response_fields:
                Specify the exact fields to include in the response.
                If you need the default fields to be included along with other requested fields, pass ['defaults']
                Additional fields that should be explicitly requested include
                ['details', 'history', 'instruction', 'cardholder']

        Yields:
            A list of FTAlarm objects.
        """
        response = await self._async_request(
            models.HTTPMethods.GET,
            self.api_features.alarms("updates"),
            params=models.QueryBase(response_fields=response_fields),
        )
        while True:
            _LOGGER.debug(response)
            yield [
                models.FTAlarm.model_validate(alarm) for alarm in response["updates"]
            ]
            await asyncio.sleep(1)
            response = await self._async_request(
                models.HTTPMethods.GET,
                response["next"]["href"],
                params=models.QueryBase(response_fields=response_fields),
            )

    async def alarm_action(self, action_href: str, comment: str | None) -> None:
        """Post an alarm action (with optional comment).

        Args:
            action_href: The FTItemReference for the alarm action command.
                This must be obtained from the FTAlarm object commands field. To get the alarm object use get_alarms method.
            comment: Optional comment to include with the alarm action.
                This is supported for ['comment', 'acknowledgeWithComment', 'processWithComment'] commands only.
        """
        await self._async_request(
            models.HTTPMethods.POST,
            action_href,
            data=models.FTAlarmCommandBody(comment=comment),
        )

    # endregion Alarm methods

    # region Status and override methods
    async def get_item_status(
        self,
        item_ids: list[str] | None = None,
        next_link: str | None = None,
    ) -> tuple[list[models.FTItemStatus], models.FTItemReference]:
        """Subscribe to items status and return list of item updates with next link.

        Args:
            item_ids: List of item IDs to get status for.
                The first call should only include the item IDs.
            next_link: The next link href to get new updates.
                This is returned from a previous call to this method.
                No need to pass the item_ids when passing the next_link.

        Returns:
            A tuple of list of FTItemStatus objects and the next FTItemReference link to get new updates.
        """
        if next_link:
            response = await self._async_request(models.HTTPMethods.GET, next_link)
        elif item_ids:
            response = await self._async_request(
                models.HTTPMethods.POST,
                self.api_features.items("updates"),
                data=models.ItemStatusQuery(item_ids=item_ids),
            )
        else:
            raise ValueError("item ids or a next link must be provided")
        return (
            [models.FTItemStatus.model_validate(item) for item in response["updates"]],
            models.FTItemReference.model_validate(response["next"]),
        )

    # endregion Status and override methods

    # region Lockers methods
    async def get_locker_bank(
        self,
        *,
        id: str | None = None,
        name: str | None = None,
        description: str | None = None,
        response_fields: list[str] | None = None,
        division: list[str] | None = None,
        sort: models.SortMethod | None = None,
        top: int | None = None,
    ) -> list[models.FTLockerBank]:
        """Retrieve the list of locker bank items configured in the system.

        Args:
            id: If provided, fetch a single detailed locker bank item by ID.
            name: Filter by locker bank item name (substring match).
            description: Filter by locker bank item description (substring match).
            response_fields:
                Specify the exact fields to include in the response.
                If you need the default fields to be included along with other requested fields, pass ['defaults']
                Additional fields that should be explicitly requested include
                ['connectedController', 'lockers']
            division: Filter by division IDs.
                To get the list of divisions call get_items method with item_types=['Division'].
            sort: Sort the order of the results.
            top: Maximum number of results to return.

        Returns:
            A list of FTLockerBank objects matching the filters.
        """
        if id:
            response = await self._async_request(
                models.HTTPMethods.GET,
                f"{self.api_features.locker_banks()}/{id}",
                params=models.QueryBase(response_fields=response_fields),
            )
            return [models.FTLockerBank.model_validate(response)]

        response = await self._async_request(
            models.HTTPMethods.GET,
            self.api_features.locker_banks(),
            params=models.QueryBase(
                name=name,
                description=description,
                division=division,
                response_fields=response_fields,
                sort=sort,
                top=top,
            ),
        )
        return [
            models.FTLockerBank.model_validate(locker) for locker in response["results"]
        ]

    async def get_locker(self, id: str | None = None) -> models.FTLocker | None:
        """Return locker item by id.

        Args:
            id: The locker ID.

        Returns:
            The FTLocker object if found, else None.
        """
        try:
            response: dict[str, Any] = await self._async_request(
                models.HTTPMethods.GET, f"{self.server_url}/api/lockers/{id}"
            )
        except RequestError as err:
            _LOGGER.warning(str(err))
            return None
        return models.FTLocker.model_validate(response)

    async def override_locker(self, command_href: str) -> None:
        """override locker.

        Args:
            command_href: The FTItemReference for the override locker command.
                This must be obtained from the FTLockerBank commands field.
        """
        await self._async_request(models.HTTPMethods.POST, command_href)

    # endregion Lockers methods
