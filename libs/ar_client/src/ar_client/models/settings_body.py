from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast

if TYPE_CHECKING:
    from ..models.settings_body_document import SettingsBodyDocument
    from ..models.settings_body_settings_schema_type_0 import SettingsBodySettingsSchemaType0


T = TypeVar("T", bound="SettingsBody")


@_attrs_define
class SettingsBody:
    """
    Attributes:
        document (SettingsBodyDocument):
        settings_schema (None | SettingsBodySettingsSchemaType0 | Unset):
    """

    document: SettingsBodyDocument
    settings_schema: None | SettingsBodySettingsSchemaType0 | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        from ..models.settings_body_document import SettingsBodyDocument  # noqa: PLC0415
        from ..models.settings_body_settings_schema_type_0 import SettingsBodySettingsSchemaType0  # noqa: PLC0415

        document = self.document.to_dict()

        settings_schema: dict[str, Any] | None | Unset
        if isinstance(self.settings_schema, Unset):
            settings_schema = UNSET
        elif isinstance(self.settings_schema, SettingsBodySettingsSchemaType0):
            settings_schema = self.settings_schema.to_dict()
        else:
            settings_schema = self.settings_schema

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "document": document,
            }
        )
        if settings_schema is not UNSET:
            field_dict["settingsSchema"] = settings_schema

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.settings_body_document import SettingsBodyDocument  # noqa: PLC0415
        from ..models.settings_body_settings_schema_type_0 import SettingsBodySettingsSchemaType0  # noqa: PLC0415

        d = dict(src_dict)
        document = SettingsBodyDocument.from_dict(d.pop("document"))

        def _parse_settings_schema(data: object) -> None | SettingsBodySettingsSchemaType0 | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                settings_schema_type_0 = SettingsBodySettingsSchemaType0.from_dict(data)

                return settings_schema_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(None | SettingsBodySettingsSchemaType0 | Unset, data)

        settings_schema = _parse_settings_schema(d.pop("settingsSchema", UNSET))

        settings_body = cls(
            document=document,
            settings_schema=settings_schema,
        )

        return settings_body
