"""Gallagher item models."""

from __future__ import annotations, division

from collections.abc import Callable
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from .exceptions import LicenseError

MOVEMENT_EVENT_TYPES = ["20001", "20002", "20003", "20047", "20107", "42415"]


class HTTPMethods(StrEnum):
    """HTTP Methods class."""

    GET = "GET"
    POST = "POST"
    PATCH = "PATCH"
    DELETE = "DELETE"


class SortMethod(StrEnum):
    """Enumerate item sorting."""

    ID_ASC = "id"
    ID_DSC = "-id"
    NAME_ASC = "name"
    NAME_DSC = "-name"


class FTModel(BaseModel):
    """Base model for FTItem models."""

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        """Override BaseModel.model_dump to exclude unset and None values by default."""
        return super().model_dump(
            **kwargs, mode="json", by_alias=True, exclude_unset=True, exclude_none=True
        )


class FTCommandsBase(FTModel):
    """Base class for command objects.

    Normalizes API responses where commands may be disabled. The API can
    return:
      - an object like {"disabled": "Not available"}
      - a dict of command names -> command refs

    If any command is disabled (either form) we treat the whole commands
    object as unavailable and return None so fields typed
    `Optional[FTCommandsBase]` become None.
    """

    @model_validator(mode="before")
    @classmethod
    def _commands_disabled_to_none(cls, values: dict[str, Any]) -> Any:
        """Guard against disabled commands."""
        # If it's a dict of commands, and any command is disabled, return None
        new_values = values.copy()
        for k, v in values.items():
            if isinstance(v, dict) and "disabled" in v:
                new_values[k] = None
        return new_values


class Feature:
    """
    A wrapper around a dictionary of feature details.
    """

    def __init__(self, name: str, features: dict[str, Any]) -> None:
        self._name = name
        self._features = features

    def _href(self, sub_feature: str | None = None) -> str:
        """
        Return href for a sub_feature. If no sub_feature is provided,
        the href for the feature itself is returned.
        """
        if not self._features:
            raise LicenseError(f"Feature '{self._name}' is not licensed.")

        lookup_key = sub_feature or self._name

        if not (detail := self._features.get(lookup_key)):
            raise ValueError(
                f"'{lookup_key}' is not a valid sub-feature of '{self._name}'"
            )
        return detail["href"]

    def __call__(self, sub_feature: str | None = None) -> str:
        """Allow calling the Feature instance like a function to get the href.

        Example: self.api_features.items('items/itemTypes') -> href
        """
        return self._href(sub_feature)


class FTApiFeatures(FTModel):
    """FTApiFeatures class."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    access_groups: Feature = Field(alias="accessGroups")
    access_zones: Feature = Field(alias="accessZones")
    alarms: Feature = Field(alias="alarms")
    alarm_zones: Feature = Field(alias="alarmZones")
    cardholders: Feature = Field(alias="cardholders")
    card_types: Feature = Field(alias="cardTypes")
    competencies: Feature = Field(alias="competencies")
    day_categories: Feature = Field(alias="dayCategories")
    divisions: Feature = Field(alias="divisions")
    doors: Feature = Field(alias="doors")
    elevators: Feature = Field(alias="elevators")
    events: Feature = Field(alias="events")
    fence_zones: Feature = Field(alias="fenceZones")
    inputs: Feature = Field(alias="inputs")
    interlock_groups: Feature = Field(alias="interlockGroups")
    items: Feature = Field(alias="items")
    locker_banks: Feature = Field(alias="lockerBanks")
    macros: Feature = Field(alias="macros")
    operator_groups: Feature = Field(alias="operatorGroups")
    outputs: Feature = Field(alias="outputs")
    personal_data_fields: Feature = Field(alias="personalDataFields")
    receptions: Feature = Field(alias="receptions")
    roles: Feature = Field(alias="roles")
    schedules: Feature = Field(alias="schedules")
    visits: Feature = Field(alias="visits")
    lockers: Feature = Field(alias="lockers")

    @model_validator(mode="before")
    @classmethod
    def _wrap_features(cls, values: dict[str, Any]) -> dict[str, Any]:
        """
        Convert each feature dict in values to a Feature instance.
        """
        wrapped_values = {}
        # Use cls.model_fields to iterate over all declared fields
        for field_name, field_info in cls.model_fields.items():
            # Pydantic uses alias for mapping, so we should too.
            alias = field_info.alias or field_name
            wrapped_values[alias] = Feature(alias, values.get(alias, {}))
        return wrapped_values


class FTItemReference(FTModel):
    """FTItem reference class."""

    href: str


class FTItemIdReference(FTModel):
    """FTItem reference class."""

    href: str
    id: str


class FTStatus(FTModel):
    """FTStatus class."""

    value: str
    type: str | None = None


class FTItemType(FTModel):
    """FTItemType class."""

    id: str
    name: str


class FTItem(FTModel):
    """FTItem class."""

    model_config = ConfigDict(extra="allow")

    href: str | None = None
    id: str | None = None
    name: str | None = None
    type: FTItemType | None = None
    division: FTItemIdReference | None = None


class FTLinkItem(FTModel):
    """FTLinkItem class."""

    href: str | None = None
    name: str | None = None


class FTBaseItem(FTModel):
    """Base class for all item classes."""

    href: str | None = None
    id: str | None = None
    name: str | None = None
    division: FTItem | None = None
    description: str | None = None
    short_name: str | None = Field(None, alias="shortName")
    notes: str | None = None
    status_flags: list[str] | None = Field(alias="statusFlags", default_factory=list)
    updates: FTItemReference | None = None
    connected_controller: FTItem | None = Field(None, alias="connectedController")


# region Access zone models


class FTAccessZoneCommandBody(FTModel):
    """FTAccessZone command body class."""

    end_time: datetime | None = Field(None, alias="endTime")
    zone_count: int | None = Field(None, alias="zoneCount")


class FTAccessZoneCommands(FTCommandsBase):
    """FTAccessZone commands base class."""

    free: FTItemReference | None = None
    free_pin: FTItemReference | None = Field(None, alias="freePin")
    secure: FTItemReference | None = None
    secure_pin: FTItemReference | None = Field(None, alias="securePin")
    code_only: FTItemReference | None = Field(None, alias="codeOnly")
    code_only_pin: FTItemReference | None = Field(None, alias="codeOnlyPin")
    dual_auth: FTItemReference | None = Field(None, alias="dualAuth")
    dual_auth_pin: FTItemReference | None = Field(None, alias="dualAuthPin")
    forgive_anti_passback: FTItemReference | None = Field(
        None, alias="forgiveAntiPassback"
    )
    set_zone_count: FTItemReference | None = Field(None, alias="setZoneCount")
    lock_down: FTItemReference | None = Field(None, alias="lockDown")
    cancel_lock_down: FTItemReference | None = Field(None, alias="cancelLockDown")
    cancel: FTItemReference | None = None


class FTAccessZone(FTBaseItem):
    """FTAccessZone item base class."""

    doors: list[FTLinkItem] = Field(default_factory=list)
    zone_count: int | None = Field(None, alias="zoneCount")
    commands: FTAccessZoneCommands | None = None


# endregion Access zone models

# region Alarm zone models


class FTAlarmZoneCommandBody(FTModel):
    """FTAlarmZone command body class."""

    end_time: datetime | None = Field(None, alias="endTime")


class FTAlarmZoneCommands(FTCommandsBase):
    """FTAlarmZone commands base class."""

    arm: FTItemReference | None = None
    disarm: FTItemReference | None = None
    user1: FTItemReference | None = None
    user2: FTItemReference | None = None
    arm_high_voltage: FTItemReference | None = Field(None, alias="armHighVoltage")
    arm_low_feel: FTItemReference | None = Field(None, alias="armLowFeel")
    cancel: FTItemReference | None = None


class FTAlarmZone(FTBaseItem):
    """FTAlarmZone item base class."""

    commands: FTAlarmZoneCommands | None = None


# endregion Alarm zone models

# region Fence zone models


class FTFenceZoneCommands(FTCommandsBase):
    """FTFenceZone commands base class."""

    on: FTItemReference | None = None
    off: FTItemReference | None = None
    shunt: FTItemReference | None = None
    unshunt: FTItemReference | None = None
    high_voltage: FTItemReference | None = Field(None, alias="highVoltage")
    low_feel: FTItemReference | None = Field(None, alias="lowFeel")
    cancel: FTItemReference | None = None


class FTFenceZone(FTBaseItem):
    """FTFenceZone item base class."""

    voltage: int | None = None
    commands: FTFenceZoneCommands | None = None


# endregion Fence zone models


# region Input/Output models
class FTInputCommands(FTCommandsBase):
    """FTInput commands base class."""

    shunt: FTItemReference | None = None
    unshunt: FTItemReference | None = None
    isolate: FTItemReference | None = None
    deisolate: FTItemReference | None = None


class FTOutputCommandBody(FTModel):
    """FTOutput command body class."""

    end_time: datetime | None = Field(None, alias="endTime")


class FTOutputCommands(FTCommandsBase):
    """FTOutput commands base class."""

    on: FTItemReference | None = None
    off: FTItemReference | None = None
    pulse: FTItemReference | None = None
    cancel: FTItemReference | None = None


class FTInput(FTBaseItem):
    """FTInput item class."""

    commands: FTInputCommands | None = None


class FTOutput(FTBaseItem):
    """FTOutput item class."""

    commands: FTOutputCommands | None = None


# endregion Inputs/Output models

# region Access groups models


class FTAccessGroupAccessZone(FTModel):
    """Access zone assigned to the access group."""

    access_zone: FTLinkItem = Field(alias="accessZone")
    schedule: FTLinkItem


class FTAccessGroupAlarmZone(FTModel):
    """Alarm zone assigned to the access group."""

    alarm_zone: FTLinkItem = Field(alias="alarmZone")


class FTAccessGroup(FTModel):
    """FTAccessGroup item base class."""

    href: str | None = None
    id: str | None = None
    name: str | None = None
    description: str | None = None
    division: FTItem | None = None
    parent: FTLinkItem | None = None
    cardholders: FTItemReference | None = None
    server_display_name: str | None = Field(None, alias="serverDisplayName")
    children: list[FTLinkItem] = Field(default_factory=list)
    personal_data_definitions: list[FTLinkItem] = Field(
        alias="personalDataDefinitions", default_factory=list
    )
    visitor: bool | None = None
    escort_visitors: bool | None = Field(None, alias="escortVisitors")
    lock_unlock_access_zones: bool | None = Field(None, alias="lockUnlockAccessZones")
    enter_during_lockdown: bool | None = Field(None, alias="enterDuringLockdown")
    first_card_unlock: bool | None = Field(None, alias="firstCardUnlock")
    override_aperio_privacy: bool | None = Field(None, alias="overrideAperioPrivacy")
    aperio_offline_access: bool | None = Field(None, alias="aperioOfflineAccess")
    disarm_alarm_zones: bool | None = Field(None, alias="disarmAlarmZones")
    arm_alarm_zones: bool | None = Field(None, alias="armAlarmZones")
    hv_lf_fence_zones: bool | None = Field(None, alias="hvLfFenceZones")
    view_alarms: bool | None = Field(None, alias="viewAlarms")
    shunt: bool | None = Field(None, alias="shunt")
    lock_out_fence_zones: bool | None = Field(None, alias="lockOutFenceZones")
    cancel_fence_zone_lockout: bool | None = Field(None, alias="cancelFenceZoneLockout")
    ack_all: bool | None = Field(None, alias="ackAll")
    ack_below_high: bool | None = Field(None, alias="ackBelowHigh")
    select_alarm_zone: bool | None = Field(None, alias="selectAlarmZone")
    arm_while_alarm: bool | None = Field(None, alias="armWhileAlarm")
    arm_while_active_alarm: bool | None = Field(None, alias="armWhileActiveAlarm")
    isolate_alarm_zones: bool | None = Field(None, alias="isolateAlarmZones")
    access: list[FTAccessGroupAccessZone] | None = Field(
        None, description="list of access zones assigned to the access group"
    )
    alarm_zones: list[FTAccessGroupAlarmZone] | None = Field(
        None, description="Alarm zones", alias="alarmZones"
    )


class FTAccessGroupMembership(FTModel):
    """FTAccessGroupMembership base class.

    To add a new membership construct the class with accessGroup and keep href None.
    To update an existing membership, construct the class with href without accessGroup
    """

    href: str | None = None
    status: FTStatus | None = None
    access_group: FTAccessGroup | None = Field(None, alias="accessGroup")
    cardholder: FTLinkItem | None = None
    active_from: datetime | None = Field(None, alias="from")
    active_until: datetime | None = Field(None, alias="until")


# endregion Access groups models

# region Operator groups models


class FTOperatorGroupMembership(FTModel):
    """FTOperatorGroupMembership item base class."""

    href: str | None = None
    cardholder: FTLinkItem


class FTOperatorGroup(FTModel):
    """FTOperatorGroup item base class."""

    id: str | None = None
    href: str | None = None
    name: str | None = None
    description: str | None = None
    division: FTItem | None = None
    cardholders: FTItemReference | None = None
    server_display_name: str | None = Field(None, alias="serverDisplayName")
    divisions: list[dict[str, FTLinkItem]] = Field(default_factory=list)


# endregion Operator groups models


# region Card type models
class FTCardType(FTModel):
    """FTCardType item base class."""

    href: str | None = None
    id: str | None = None
    name: str | None = None
    division: FTItem | None = None
    notes: str | None = None
    facility_code: str | None = Field(None, alias="facilityCode")
    available_card_states: list[str] | None = Field(
        alias="availableCardStates", default_factory=list
    )
    credential_class: str | None = Field(None, alias="credentialClass")
    minimum_number: str | None = Field(None, alias="minimumNumber")
    maximum_number: str | None = Field(None, alias="maximumNumber")
    server_display_name: str | None = Field(None, alias="serverDisplayName")
    regex: str | None = Field(None, alias="regex")
    regex_description: str | None = Field(None, alias="regexDescription")


# endregion Card type models

# region Cardholder card models


class FTCardholderCard(FTModel):
    """FTCardholder card base class."""

    href: str | None = None
    number: str | None = None
    card_serial_number: str | None = Field(None, alias="cardSerialNumber")
    issue_level: int | None = Field(None, alias="issueLevel")
    status: FTStatus | None = None
    type: FTLinkItem
    # invitation: TODO Add invitation model
    active_from: datetime | None = Field(None, alias="from")
    active_until: datetime | None = Field(None, alias="until")
    credentialClass: str | None = None
    trace: bool | None = None
    last_used_time: datetime | None = Field(None, alias="lastUsedTime")
    # pin TODO add pin field


# endregion Cardholder card models

# region PDF definition models


class PDFType(StrEnum):
    """PDF types class."""

    STRING = "string"
    IMAGE = "image"
    STRENUM = "strEnum"
    NUMERIC = "numeric"
    DATE = "date"
    ADDRESS = "address"
    PHONE = "phone"
    EMAIL = "email"
    MOBILE = "mobile"


class FTPersonalDataFieldDefinition(FTModel):
    """FTPersonalDataFieldDefinition class."""

    href: str | None = None
    id: str | None = None
    name: str | None = None
    server_display_name: str | None = Field(None, alias="serverDisplayName")
    description: str | None = None
    type: PDFType | None = None
    division: FTItem | None = None
    default: str | None = None
    default_access: str | None = Field(None, alias="defaultAccess")
    operator_access: str | None = Field(None, alias="operatorAccess")
    sort_priority: int | None = Field(None, alias="sortPriority")
    access_groups: list[FTLinkItem] = Field(alias="accessGroups", default_factory=list)
    regex: str | None = None
    regex_description: str | None = Field(None, alias="regexDescription")
    content_type: str | None = Field(None, alias="contentType")
    is_profile_image: bool | None = Field(None, alias="isProfileImage")
    required: bool | None = Field(None, alias="required")
    unique: bool | None = Field(None, alias="unique")
    str_enum_list: list[str] = Field(alias="strEnumList", default_factory=list)


# endregion pdf definition models


# region Lockers models
class FTLockerCommands(FTCommandsBase):
    """FTLocker commands base class."""

    open: FTItemReference
    quarantine: FTItemReference
    quarantine_until: FTItemReference | None = Field(None, alias="quarantineUntil")
    cancel_quarantine: FTItemReference | None = Field(None, alias="cancelQuarantine")


class LockerAssignment(FTModel):
    """Locker assignment class."""

    href: str
    cardholder: FTLinkItem
    active_from: datetime | None = Field(None, alias="from")
    active_until: datetime | None = Field(None, alias="until")


class FTLockerMembership(FTModel):
    """Locker membership class."""

    href: str | None = None
    locker: FTLocker | None = None
    active_from: datetime | None = Field(None, alias="from")
    active_until: datetime | None = Field(None, alias="until")


class FTLocker(FTModel):
    """Locker class."""

    href: str
    name: str
    short_name: str | None = Field(None, alias="shortName")
    description: str | None = None
    division: FTItem | None = None
    notes: str | None = None
    connected_controller: FTItem | None = Field(None, alias="connectedController")
    assignments: list[LockerAssignment] | None = None
    commands: FTLockerCommands | None = None
    updates: FTItemReference | None = Field(None, exclude=True)


class FTLockerBank(FTBaseItem):
    """Locker Bank class."""

    lockers: list[FTLocker] | None = None


# endregion Lockers models


# region Elevator groups models


class ElevatorGroups(FTModel):
    """Cardholder elevator group assignment class."""

    href: str
    elevator_group: FTLinkItem = Field(alias="elevatorGroup")
    access_zone: FTLinkItem = Field(alias="accessZone")
    enable_capture_features: bool = Field(alias="enableCaptureFeatures")
    enable_code_blue_features: bool = Field(alias="enableCodeBlueFeatures")
    enable_express_features: bool = Field(alias="enableExpressFeatures")
    enable_service_features: bool = Field(alias="enableServiceFeatures")
    enable_service2_features: bool = Field(alias="enableService2Features")
    enable_service3_features: bool = Field(alias="enableService3Features")


# endregion Elevator groups models


# region Cardholder models
class FTCardholderPdfDefinition(FTModel):
    """FTCardholderPdfDefinition class."""

    id: str
    name: str
    href: str
    type: str


class FTCardholderPdfValue(FTModel):
    """FTCardholderPdfValue class."""

    href: str | None = None
    definition: FTCardholderPdfDefinition | None = None
    value: int | str | FTItemReference | None = None
    notifications: bool | None = None


class FTCardholderCardsPatch(FTModel):
    """Patch section for FTCardholder.cards."""

    add: list[FTCardholderCard] | None = None
    update: list[FTCardholderCard] | None = None
    remove: list[FTCardholderCard] | None = None


class FTCardholderAccessGroupsPatch(BaseModel):
    """Patch section for FTCardholder.accessGroups."""

    add: list[FTAccessGroupMembership] | None = Field(default_factory=list)
    update: list[FTAccessGroupMembership] | None = Field(default_factory=list)
    remove: list[FTAccessGroupMembership] | None = Field(default_factory=list)


class FTCardholderLockersPatch(FTModel):
    """Patch section for FTCardholder.lockers."""

    add: list[FTLockerMembership] | None = None
    update: list[FTLockerMembership] | None = None
    remove: list[FTLockerMembership] | None = None


class FTCardholder(FTModel):
    """FTCardholder details class."""

    href: str | None = None
    id: str | None = None
    division: FTItem | None = None
    notes: str | None = None
    first_name: str | None = Field(None, alias="firstName")
    last_name: str | None = Field(None, alias="lastName")
    short_name: str | None = Field(None, alias="shortName")
    description: str | None = Field(None, alias="description")
    last_successful_access_time: datetime | None = Field(
        None, alias="lastSuccessfulAccessTime"
    )
    last_successful_access_zone: FTLinkItem | None = Field(
        None, alias="lastSuccessfulAccessZone"
    )
    server_display_name: str | None = Field(None, alias="serverDisplayName")
    disable_cipher_pad: bool | None = Field(None, alias="disableCipherPad")
    user_code: str | None = Field(None, alias="usercode")
    operator_username: str | None = Field(None, alias="operatorUsername")
    operator_password: str | None = Field(None, alias="operatorPassword")
    windows_username: str | None = Field(None, alias="windowsUsername")

    # for POST or PATCH the dict str value should start with @,
    # the value is "notifications": true/false
    personal_data_definitions: list[dict[str, FTCardholderPdfValue]] | None = Field(
        None, alias="personalDataDefinitions"
    )
    cards: list[FTCardholderCard] | FTCardholderCardsPatch | None = None
    access_groups: (
        list[FTAccessGroupMembership] | FTCardholderAccessGroupsPatch | None
    ) = Field(None, alias="accessGroups")
    # operator_groups: str
    # competencies: str
    # edit: str
    update_location: FTItemReference | None = Field(None, alias="updateLocation")
    # relationships: Any | None
    lockers: list[FTLockerMembership] | FTCardholderLockersPatch | None = None
    elevator_groups: list[ElevatorGroups] | None = Field(None, alias="elevatorGroups")
    last_printed_or_encoded_time: datetime | None = Field(
        None, alias="lastPrintedOrEncodedTime"
    )
    last_printed_or_encoded_issue_level: int | None = Field(
        None, alias="lastPrintedOrEncodedIssueLevel"
    )
    # redactions: Any | None

    # pdfs is constructed internally and must not be populated from JSON input
    pdfs: dict[str, str | int | FTItemReference] = Field(default_factory=dict)

    authorised: bool | None = None
    operator_login_enabled: bool | None = Field(None, alias="operatorLoginEnabled")
    operator_password_expired: bool | None = Field(
        None, alias="operatorPasswordExpired"
    )
    use_extended_access_time: bool | None = Field(None, alias="useExtendedAccessTime")
    windows_login_enabled: bool | None = Field(None, alias="windowsLoginEnabled")

    def model_dump(self, **kwargs) -> Any:
        """Ensure private PDFs are included when serializing via model_dump.

        We call the parent model_dump then inject any entries from the
        private `_pdfs` attribute as keys prefixed with '@'. Nested
        FTModel instances are serialized via their own model_dump.
        """
        raw = super().model_dump(**kwargs)
        raw.update({f"@{name}": value for name, value in self.pdfs.items()})

        return raw

    @model_validator(mode="before")
    @classmethod
    def _parse_pdf_values(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Extract pdf values and store then in pdf attribute."""
        for key in list(values.keys()):
            if key.startswith("@"):
                value = values.pop(key)
                value = (
                    FTItemReference.model_validate(value)
                    if isinstance(value, dict)
                    else value
                )
                values.setdefault("pdfs", {})[key[1:]] = value

        return values


class FTNewCardholder(FTCardholder):
    """FTCardholder model for adding new cardholders.

    Requires at least one name field (first_name or last_name) and division.
    """

    division: FTItem  # Required for POST

    @model_validator(mode="after")
    def _validate_name_required(self) -> FTNewCardholder:
        """Ensure at least first_name or last_name is provided."""
        if not self.first_name and not self.last_name:
            raise ValueError(
                "At least one of 'first_name' or 'last_name' must be provided"
            )
        return self


class FTCardholderPatch(FTCardholder):
    """FTCardholder model for patching existing cardholders."""

    cards: FTCardholderCardsPatch | None = None
    access_groups: FTCardholderAccessGroupsPatch | None = None
    lockers: FTCardholderLockersPatch | None = None


class CardholderChangeType(StrEnum):
    """Cardholder change types."""

    ADD = "add"
    UPDATE = "update"
    REMOVE = "remove"


class CardholderChange(FTModel):
    """Cardholder changes object class."""

    time: datetime | None = None
    operator: FTLinkItem | None = None
    type: CardholderChangeType | None = None
    item: FTItemReference | None = None
    old_values: dict[str, Any] | None = Field(None, alias="oldValues")
    new_values: dict[str, Any] | None = Field(None, alias="newValues")
    cardholder: FTCardholder | None = None


# endregion Cardholder models


# region Alarm and event models


class FTAlarmState(StrEnum):
    """Alarm states."""

    UNACKNOWLEDGED = "unacknowledged"
    ACKNOWLEDGED = "acknowledged"
    PROCESSED = "processed"


class FTEventAlarm(FTModel):
    """FTAlarm summary class"""

    href: str | None = None
    state: FTAlarmState


class FTEventCard(FTModel):
    """Event card details."""

    number: str
    issue_level: int = Field(alias="issueLevel")
    facility_code: str = Field(alias="facilityCode")


class FTEventType(FTModel):
    """FTEvent type class."""

    id: str
    name: str
    href: str


class FTEventGroup(FTModel):
    """FTEvent group class."""

    id: str
    name: str
    href: str
    event_types: list[FTEventType] = Field(alias="eventTypes")


class EventField(FTModel):
    """Class to represent Event field."""

    key: str
    name: str
    value: Callable[[Any], Any] = lambda val: val


class FTEventBase(FTModel):
    """FTEventBase class."""

    href: str
    id: str
    time: datetime
    message: str
    source: FTItem
    type: FTItemType | str
    event_type: FTItemType | None = Field(None, alias="eventType")
    priority: int
    division: FTItem | None = None


class FTAlarm(FTEventBase):
    """FTAlarm class."""

    state: FTAlarmState
    active: bool
    event: FTItemReference | None = None
    note_presets: list[str] | None = Field(None, alias="notePresets")
    view: FTItemReference
    comment: FTItemReference
    acknowledge: FTItemReference | None = None
    acknowledge_with_comment: FTItemReference | None = Field(
        None, alias="acknowledgeWithComment"
    )
    process: FTItemReference | None = None
    process_with_comment: FTItemReference | None = Field(
        None, alias="processWithComment"
    )
    force_process: FTItemReference | None = Field(None, alias="forceProcess")


class FTEvent(FTEventBase):
    """FTEvent class."""

    server_display_name: str | None = Field(None, alias="serverDisplayName")
    occurrences: int | None = None
    alarm: FTEventAlarm | None = None
    operator: FTLinkItem | None = None
    group: FTItemType | None = None
    cardholder: FTCardholder | None = None
    entry_access_zone: FTItem | None = Field(None, alias="entryAccessZone")
    exit_access_zone: FTItem | None = Field(None, alias="exitAccessZone")
    door: FTLinkItem | None = None
    access_group: FTItemReference | None = Field(None, alias="accessGroup")
    card: FTEventCard | None = None
    last_occurrence_time: datetime | None = Field(None, alias="lastOccurrenceTime")
    details: str | None = None
    previous: FTItemReference | None = None
    next: FTItemReference | None = None
    updates: FTItemReference | None = None


class EventPost(FTModel):
    """FTEvent summary class.

    Supported on version 8.90+
    """

    event_type: FTItem = Field(alias="eventType")
    priority: int | None = None
    time: datetime | None = None
    message: str | None = None
    details: str | None = None
    source: FTItemReference | None = None
    cardholder: FTItemReference | None = None
    operator: FTItemReference | None = None
    entry_access_zone: FTItemReference | None = Field(None, alias="entryAccessZone")
    access_group: FTItemReference | None = Field(None, alias="accessGroup")
    locker_bank: FTItemReference | None = Field(None, alias="lockerBank")
    locker: FTItemReference | None = None
    door: FTItemReference | None = None


class FTAlarmCommandBody(FTModel):
    """FTAlarm command body class."""

    comment: str | None = None


# endregion Alarm and event models


# region Door models
class FTDoorCommands(FTCommandsBase):
    """FTDoor commands base class."""

    open: FTItemReference


class FTDoor(FTBaseItem):
    """FTDoor details class."""

    entry_access_zone: FTLinkItem | None = Field(None, alias="entryAccessZone")
    commands: FTDoorCommands | None = None


# endregion Door models


# region Item status and overrides
class FTItemStatus(FTModel):
    """Item status class."""

    id: str
    status: str
    status_text: str = Field(alias="statusText")
    status_flags: list[str] = Field(alias="statusFlags", default_factory=list)


# endregion Item status and overrides


# region query params models


class QueryBase(FTModel):
    """Base query params model."""

    name: str | None = None
    description: str | None = None
    division: list[str] | None = None
    sort: SortMethod | None = None
    response_fields: list[str] | None = Field(None, alias="fields")
    top: int | None = None

    @field_serializer("division", "response_fields")
    def _serialize_fields(self, v: list[str] | None) -> str | None:
        """Serialize fields to comma-separated string."""
        return ",".join(v) if v else None


class ItemQuery(QueryBase):
    """Item query params model."""

    item_types: list[str] | None = Field(None, alias="type")

    @field_serializer("item_types")
    def _serialize_item_fields(self, v):
        return super()._serialize_fields(v)


class CardholderQuery(QueryBase):
    """Cardholder query params model."""

    pdfs: dict[str, str] | None = None
    access_zones: str | list[str] | None = Field(None, alias="accessZone")

    @field_validator("access_zones", mode="before")
    @classmethod
    def check_str_value(cls, value: Any) -> Any:
        """Validate that access_zones is '*' or a list of strings."""
        if isinstance(value, str) and value != "*":
            raise ValueError("access_zones must be '*' or a list of strings")
        return value

    @field_serializer("access_zones")
    def _serialize_cardholder_fields(self, v):
        return super()._serialize_fields(v)


class CardholderChangesQuery(QueryBase):
    """Cardholder changes query params model.

    Initialize with `cardholder_fields` and/or `response_fields`.
    On serialization (model_dump), only a combined `fields` entry is emitted,
    and `cardholder_fields`/`response_fields` are excluded.
    """

    filter: list[str] | None = None
    cardholder_fields: list[str] | None = Field(None, exclude=True)

    @model_validator(mode="after")
    def _merge_cardholder_into_extra_fields(self) -> CardholderChangesQuery:
        """After construction, merge cardholder_fields into response_fields.

        - Prefix each cardholder field with "cardholder." to match API schema
        - If response_fields is None, set it to the prefixed list
        - Otherwise, append the prefixed list to existing response_fields
        """
        if self.cardholder_fields:
            cardholder_fields = [f"cardholder.{f}" for f in self.cardholder_fields]
            self.response_fields = (self.response_fields or []) + cardholder_fields
        return self


class EventQuery(QueryBase):
    """Event filter class."""

    after: datetime | None = None
    before: datetime | None = None
    source: list[str] | None = Field(
        None, description="List of source item IDs that generated the events."
    )
    event_types: list[str] | None = Field(None, alias="type")
    event_groups: list[str] | None = Field(None, alias="group")
    cardholders: list[str] | None = None
    related_items: list[str] | None = Field(
        None,
        alias="relatedItem",
        description="Restrict events to those associated with these item IDs.",
    )
    previous: bool | None = Field(
        None, description="Set this to true to get the events starting from the newest."
    )

    @field_serializer(
        "source",
        "event_types",
        "event_groups",
        "cardholders",
        "related_items",
    )
    def _serialize_event_fields(self, v):
        return super()._serialize_fields(v)


class ItemStatusQuery(QueryBase):
    """Item status query params model."""

    item_ids: list[str] | None = Field(None, alias="itemIds")


# endregion query params models
