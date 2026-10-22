from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast


T = TypeVar("T", bound="TemplatePatch")


@_attrs_define
class TemplatePatch:
    """
    Attributes:
        name (None | str | Unset):
        image_ref (None | str | Unset):
        runtime_class (None | str | Unset):
        cpu_millis (int | None | Unset):
        memory_mb (int | None | Unset):
        disk_gb (int | None | Unset):
        allow_browser (bool | None | Unset):
        allow_packages (bool | None | Unset):
        egress_allowlist (list[str] | None | Unset):
        max_classification (None | str | Unset):
        idle_suspend_s (int | None | Unset):
        max_lifetime_s (int | None | Unset):
        exec_timeout_s (int | None | Unset):
        retention_days (int | None | Unset):
        status (None | str | Unset):
    """

    name: None | str | Unset = UNSET
    image_ref: None | str | Unset = UNSET
    runtime_class: None | str | Unset = UNSET
    cpu_millis: int | None | Unset = UNSET
    memory_mb: int | None | Unset = UNSET
    disk_gb: int | None | Unset = UNSET
    allow_browser: bool | None | Unset = UNSET
    allow_packages: bool | None | Unset = UNSET
    egress_allowlist: list[str] | None | Unset = UNSET
    max_classification: None | str | Unset = UNSET
    idle_suspend_s: int | None | Unset = UNSET
    max_lifetime_s: int | None | Unset = UNSET
    exec_timeout_s: int | None | Unset = UNSET
    retention_days: int | None | Unset = UNSET
    status: None | str | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        name: None | str | Unset
        if isinstance(self.name, Unset):
            name = UNSET
        else:
            name = self.name

        image_ref: None | str | Unset
        if isinstance(self.image_ref, Unset):
            image_ref = UNSET
        else:
            image_ref = self.image_ref

        runtime_class: None | str | Unset
        if isinstance(self.runtime_class, Unset):
            runtime_class = UNSET
        else:
            runtime_class = self.runtime_class

        cpu_millis: int | None | Unset
        if isinstance(self.cpu_millis, Unset):
            cpu_millis = UNSET
        else:
            cpu_millis = self.cpu_millis

        memory_mb: int | None | Unset
        if isinstance(self.memory_mb, Unset):
            memory_mb = UNSET
        else:
            memory_mb = self.memory_mb

        disk_gb: int | None | Unset
        if isinstance(self.disk_gb, Unset):
            disk_gb = UNSET
        else:
            disk_gb = self.disk_gb

        allow_browser: bool | None | Unset
        if isinstance(self.allow_browser, Unset):
            allow_browser = UNSET
        else:
            allow_browser = self.allow_browser

        allow_packages: bool | None | Unset
        if isinstance(self.allow_packages, Unset):
            allow_packages = UNSET
        else:
            allow_packages = self.allow_packages

        egress_allowlist: list[str] | None | Unset
        if isinstance(self.egress_allowlist, Unset):
            egress_allowlist = UNSET
        elif isinstance(self.egress_allowlist, list):
            egress_allowlist = self.egress_allowlist

        else:
            egress_allowlist = self.egress_allowlist

        max_classification: None | str | Unset
        if isinstance(self.max_classification, Unset):
            max_classification = UNSET
        else:
            max_classification = self.max_classification

        idle_suspend_s: int | None | Unset
        if isinstance(self.idle_suspend_s, Unset):
            idle_suspend_s = UNSET
        else:
            idle_suspend_s = self.idle_suspend_s

        max_lifetime_s: int | None | Unset
        if isinstance(self.max_lifetime_s, Unset):
            max_lifetime_s = UNSET
        else:
            max_lifetime_s = self.max_lifetime_s

        exec_timeout_s: int | None | Unset
        if isinstance(self.exec_timeout_s, Unset):
            exec_timeout_s = UNSET
        else:
            exec_timeout_s = self.exec_timeout_s

        retention_days: int | None | Unset
        if isinstance(self.retention_days, Unset):
            retention_days = UNSET
        else:
            retention_days = self.retention_days

        status: None | str | Unset
        if isinstance(self.status, Unset):
            status = UNSET
        else:
            status = self.status

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if name is not UNSET:
            field_dict["name"] = name
        if image_ref is not UNSET:
            field_dict["imageRef"] = image_ref
        if runtime_class is not UNSET:
            field_dict["runtimeClass"] = runtime_class
        if cpu_millis is not UNSET:
            field_dict["cpuMillis"] = cpu_millis
        if memory_mb is not UNSET:
            field_dict["memoryMb"] = memory_mb
        if disk_gb is not UNSET:
            field_dict["diskGb"] = disk_gb
        if allow_browser is not UNSET:
            field_dict["allowBrowser"] = allow_browser
        if allow_packages is not UNSET:
            field_dict["allowPackages"] = allow_packages
        if egress_allowlist is not UNSET:
            field_dict["egressAllowlist"] = egress_allowlist
        if max_classification is not UNSET:
            field_dict["maxClassification"] = max_classification
        if idle_suspend_s is not UNSET:
            field_dict["idleSuspendS"] = idle_suspend_s
        if max_lifetime_s is not UNSET:
            field_dict["maxLifetimeS"] = max_lifetime_s
        if exec_timeout_s is not UNSET:
            field_dict["execTimeoutS"] = exec_timeout_s
        if retention_days is not UNSET:
            field_dict["retentionDays"] = retention_days
        if status is not UNSET:
            field_dict["status"] = status

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)

        def _parse_name(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        name = _parse_name(d.pop("name", UNSET))

        def _parse_image_ref(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        image_ref = _parse_image_ref(d.pop("imageRef", UNSET))

        def _parse_runtime_class(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        runtime_class = _parse_runtime_class(d.pop("runtimeClass", UNSET))

        def _parse_cpu_millis(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        cpu_millis = _parse_cpu_millis(d.pop("cpuMillis", UNSET))

        def _parse_memory_mb(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        memory_mb = _parse_memory_mb(d.pop("memoryMb", UNSET))

        def _parse_disk_gb(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        disk_gb = _parse_disk_gb(d.pop("diskGb", UNSET))

        def _parse_allow_browser(data: object) -> bool | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        allow_browser = _parse_allow_browser(d.pop("allowBrowser", UNSET))

        def _parse_allow_packages(data: object) -> bool | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        allow_packages = _parse_allow_packages(d.pop("allowPackages", UNSET))

        def _parse_egress_allowlist(data: object) -> list[str] | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                egress_allowlist_type_0 = cast(list[str], data)

                return egress_allowlist_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(list[str] | None | Unset, data)

        egress_allowlist = _parse_egress_allowlist(d.pop("egressAllowlist", UNSET))

        def _parse_max_classification(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        max_classification = _parse_max_classification(d.pop("maxClassification", UNSET))

        def _parse_idle_suspend_s(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        idle_suspend_s = _parse_idle_suspend_s(d.pop("idleSuspendS", UNSET))

        def _parse_max_lifetime_s(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        max_lifetime_s = _parse_max_lifetime_s(d.pop("maxLifetimeS", UNSET))

        def _parse_exec_timeout_s(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        exec_timeout_s = _parse_exec_timeout_s(d.pop("execTimeoutS", UNSET))

        def _parse_retention_days(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        retention_days = _parse_retention_days(d.pop("retentionDays", UNSET))

        def _parse_status(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        status = _parse_status(d.pop("status", UNSET))

        template_patch = cls(
            name=name,
            image_ref=image_ref,
            runtime_class=runtime_class,
            cpu_millis=cpu_millis,
            memory_mb=memory_mb,
            disk_gb=disk_gb,
            allow_browser=allow_browser,
            allow_packages=allow_packages,
            egress_allowlist=egress_allowlist,
            max_classification=max_classification,
            idle_suspend_s=idle_suspend_s,
            max_lifetime_s=max_lifetime_s,
            exec_timeout_s=exec_timeout_s,
            retention_days=retention_days,
            status=status,
        )

        return template_patch
