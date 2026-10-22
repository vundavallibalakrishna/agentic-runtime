from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast


T = TypeVar("T", bound="TemplateBody")


@_attrs_define
class TemplateBody:
    """
    Attributes:
        slug (str | Unset):  Default: ''.
        name (str | Unset):  Default: ''.
        image_ref (str | Unset):  Default: ''.
        runtime_class (str | Unset):  Default: 'gvisor'.
        cpu_millis (int | Unset):  Default: 2000.
        memory_mb (int | Unset):  Default: 4096.
        disk_gb (int | Unset):  Default: 10.
        allow_browser (bool | Unset):  Default: False.
        allow_packages (bool | Unset):  Default: False.
        egress_allowlist (list[str] | Unset):
        max_classification (str | Unset):  Default: 'confidential'.
        idle_suspend_s (int | Unset):  Default: 900.
        max_lifetime_s (int | Unset):  Default: 86400.
        exec_timeout_s (int | Unset):  Default: 120.
        retention_days (int | Unset):  Default: 7.
    """

    slug: str | Unset = ""
    name: str | Unset = ""
    image_ref: str | Unset = ""
    runtime_class: str | Unset = "gvisor"
    cpu_millis: int | Unset = 2000
    memory_mb: int | Unset = 4096
    disk_gb: int | Unset = 10
    allow_browser: bool | Unset = False
    allow_packages: bool | Unset = False
    egress_allowlist: list[str] | Unset = UNSET
    max_classification: str | Unset = "confidential"
    idle_suspend_s: int | Unset = 900
    max_lifetime_s: int | Unset = 86400
    exec_timeout_s: int | Unset = 120
    retention_days: int | Unset = 7

    def to_dict(self) -> dict[str, Any]:
        slug = self.slug

        name = self.name

        image_ref = self.image_ref

        runtime_class = self.runtime_class

        cpu_millis = self.cpu_millis

        memory_mb = self.memory_mb

        disk_gb = self.disk_gb

        allow_browser = self.allow_browser

        allow_packages = self.allow_packages

        egress_allowlist: list[str] | Unset = UNSET
        if not isinstance(self.egress_allowlist, Unset):
            egress_allowlist = self.egress_allowlist

        max_classification = self.max_classification

        idle_suspend_s = self.idle_suspend_s

        max_lifetime_s = self.max_lifetime_s

        exec_timeout_s = self.exec_timeout_s

        retention_days = self.retention_days

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if slug is not UNSET:
            field_dict["slug"] = slug
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

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        slug = d.pop("slug", UNSET)

        name = d.pop("name", UNSET)

        image_ref = d.pop("imageRef", UNSET)

        runtime_class = d.pop("runtimeClass", UNSET)

        cpu_millis = d.pop("cpuMillis", UNSET)

        memory_mb = d.pop("memoryMb", UNSET)

        disk_gb = d.pop("diskGb", UNSET)

        allow_browser = d.pop("allowBrowser", UNSET)

        allow_packages = d.pop("allowPackages", UNSET)

        egress_allowlist = cast(list[str], d.pop("egressAllowlist", UNSET))

        max_classification = d.pop("maxClassification", UNSET)

        idle_suspend_s = d.pop("idleSuspendS", UNSET)

        max_lifetime_s = d.pop("maxLifetimeS", UNSET)

        exec_timeout_s = d.pop("execTimeoutS", UNSET)

        retention_days = d.pop("retentionDays", UNSET)

        template_body = cls(
            slug=slug,
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
        )

        return template_body
