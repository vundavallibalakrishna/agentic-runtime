from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.import_body_bundle_type_0 import ImportBodyBundleType0


T = TypeVar("T", bound="ImportBody")


@_attrs_define
class ImportBody:
    """
    Attributes:
        bundle (ImportBodyBundleType0 | None | Unset):
        yaml_text (None | str | Unset):
        dry_run (bool | Unset):  Default: False.
    """

    bundle: ImportBodyBundleType0 | Unset | None = UNSET
    yaml_text: str | Unset | None = UNSET
    dry_run: bool | Unset = False

    def to_dict(self) -> dict[str, Any]:
        from ..models.import_body_bundle_type_0 import ImportBodyBundleType0  # noqa: PLC0415

        bundle: dict[str, Any] | Unset | None
        if isinstance(self.bundle, Unset):
            bundle = UNSET
        elif isinstance(self.bundle, ImportBodyBundleType0):
            bundle = self.bundle.to_dict()
        else:
            bundle = self.bundle

        yaml_text: str | Unset | None
        if isinstance(self.yaml_text, Unset):
            yaml_text = UNSET
        else:
            yaml_text = self.yaml_text

        dry_run = self.dry_run

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if bundle is not UNSET:
            field_dict["bundle"] = bundle
        if yaml_text is not UNSET:
            field_dict["yamlText"] = yaml_text
        if dry_run is not UNSET:
            field_dict["dryRun"] = dry_run

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.import_body_bundle_type_0 import ImportBodyBundleType0  # noqa: PLC0415

        d = dict(src_dict)

        def _parse_bundle(data: object) -> ImportBodyBundleType0 | Unset | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                bundle_type_0 = ImportBodyBundleType0.from_dict(data)

                return bundle_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast("ImportBodyBundleType0 | None | Unset", data)

        bundle = _parse_bundle(d.pop("bundle", UNSET))

        def _parse_yaml_text(data: object) -> str | Unset | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast("None | str | Unset", data)

        yaml_text = _parse_yaml_text(d.pop("yamlText", UNSET))

        dry_run = d.pop("dryRun", UNSET)

        import_body = cls(
            bundle=bundle,
            yaml_text=yaml_text,
            dry_run=dry_run,
        )

        return import_body
