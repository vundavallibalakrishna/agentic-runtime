from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast
from uuid import UUID

if TYPE_CHECKING:
    from ..models.evidence_body_provenance_type_0 import EvidenceBodyProvenanceType0


T = TypeVar("T", bound="EvidenceBody")


@_attrs_define
class EvidenceBody:
    """
    Attributes:
        file_id (None | Unset | UUID):
        text (str | Unset):  Default: ''.
        media_type (str | Unset):  Default: 'text/plain'.
        source_system (str | Unset):  Default: 'api'.
        collection_method (str | Unset):  Default: 'api'.
        provenance (EvidenceBodyProvenanceType0 | None | Unset):
        collector_run_id (None | Unset | UUID):
    """

    file_id: None | Unset | UUID = UNSET
    text: str | Unset = ""
    media_type: str | Unset = "text/plain"
    source_system: str | Unset = "api"
    collection_method: str | Unset = "api"
    provenance: EvidenceBodyProvenanceType0 | None | Unset = UNSET
    collector_run_id: None | Unset | UUID = UNSET

    def to_dict(self) -> dict[str, Any]:
        from ..models.evidence_body_provenance_type_0 import EvidenceBodyProvenanceType0  # noqa: PLC0415

        file_id: None | str | Unset
        if isinstance(self.file_id, Unset):
            file_id = UNSET
        elif isinstance(self.file_id, UUID):
            file_id = str(self.file_id)
        else:
            file_id = self.file_id

        text = self.text

        media_type = self.media_type

        source_system = self.source_system

        collection_method = self.collection_method

        provenance: dict[str, Any] | None | Unset
        if isinstance(self.provenance, Unset):
            provenance = UNSET
        elif isinstance(self.provenance, EvidenceBodyProvenanceType0):
            provenance = self.provenance.to_dict()
        else:
            provenance = self.provenance

        collector_run_id: None | str | Unset
        if isinstance(self.collector_run_id, Unset):
            collector_run_id = UNSET
        elif isinstance(self.collector_run_id, UUID):
            collector_run_id = str(self.collector_run_id)
        else:
            collector_run_id = self.collector_run_id

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if file_id is not UNSET:
            field_dict["fileId"] = file_id
        if text is not UNSET:
            field_dict["text"] = text
        if media_type is not UNSET:
            field_dict["mediaType"] = media_type
        if source_system is not UNSET:
            field_dict["sourceSystem"] = source_system
        if collection_method is not UNSET:
            field_dict["collectionMethod"] = collection_method
        if provenance is not UNSET:
            field_dict["provenance"] = provenance
        if collector_run_id is not UNSET:
            field_dict["collectorRunId"] = collector_run_id

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.evidence_body_provenance_type_0 import EvidenceBodyProvenanceType0  # noqa: PLC0415

        d = dict(src_dict)

        def _parse_file_id(data: object) -> None | Unset | UUID:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                file_id_type_0 = UUID(data)

                return file_id_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(None | Unset | UUID, data)

        file_id = _parse_file_id(d.pop("fileId", UNSET))

        text = d.pop("text", UNSET)

        media_type = d.pop("mediaType", UNSET)

        source_system = d.pop("sourceSystem", UNSET)

        collection_method = d.pop("collectionMethod", UNSET)

        def _parse_provenance(data: object) -> EvidenceBodyProvenanceType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                provenance_type_0 = EvidenceBodyProvenanceType0.from_dict(data)

                return provenance_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(EvidenceBodyProvenanceType0 | None | Unset, data)

        provenance = _parse_provenance(d.pop("provenance", UNSET))

        def _parse_collector_run_id(data: object) -> None | Unset | UUID:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                collector_run_id_type_0 = UUID(data)

                return collector_run_id_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(None | Unset | UUID, data)

        collector_run_id = _parse_collector_run_id(d.pop("collectorRunId", UNSET))

        evidence_body = cls(
            file_id=file_id,
            text=text,
            media_type=media_type,
            source_system=source_system,
            collection_method=collection_method,
            provenance=provenance,
            collector_run_id=collector_run_id,
        )

        return evidence_body
