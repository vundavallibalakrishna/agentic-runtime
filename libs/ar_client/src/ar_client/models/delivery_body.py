from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast

if TYPE_CHECKING:
    from ..models.delivery_body_config import DeliveryBodyConfig


T = TypeVar("T", bound="DeliveryBody")


@_attrs_define
class DeliveryBody:
    """
    Attributes:
        type_ (str):
        integration (None | str | Unset):
        channel (None | str | Unset):
        pre_approved (bool | Unset):  Default: False.
        config (DeliveryBodyConfig | Unset):
    """

    type_: str
    integration: None | str | Unset = UNSET
    channel: None | str | Unset = UNSET
    pre_approved: bool | Unset = False
    config: DeliveryBodyConfig | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        from ..models.delivery_body_config import DeliveryBodyConfig  # noqa: PLC0415

        type_ = self.type_

        integration: None | str | Unset
        if isinstance(self.integration, Unset):
            integration = UNSET
        else:
            integration = self.integration

        channel: None | str | Unset
        if isinstance(self.channel, Unset):
            channel = UNSET
        else:
            channel = self.channel

        pre_approved = self.pre_approved

        config: dict[str, Any] | Unset = UNSET
        if not isinstance(self.config, Unset):
            config = self.config.to_dict()

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "type": type_,
            }
        )
        if integration is not UNSET:
            field_dict["integration"] = integration
        if channel is not UNSET:
            field_dict["channel"] = channel
        if pre_approved is not UNSET:
            field_dict["preApproved"] = pre_approved
        if config is not UNSET:
            field_dict["config"] = config

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.delivery_body_config import DeliveryBodyConfig  # noqa: PLC0415

        d = dict(src_dict)
        type_ = d.pop("type")

        def _parse_integration(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        integration = _parse_integration(d.pop("integration", UNSET))

        def _parse_channel(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        channel = _parse_channel(d.pop("channel", UNSET))

        pre_approved = d.pop("preApproved", UNSET)

        _config = d.pop("config", UNSET)
        config: DeliveryBodyConfig | Unset
        if isinstance(_config, Unset):
            config = UNSET
        else:
            config = DeliveryBodyConfig.from_dict(_config)

        delivery_body = cls(
            type_=type_,
            integration=integration,
            channel=channel,
            pre_approved=pre_approved,
            config=config,
        )

        return delivery_body
