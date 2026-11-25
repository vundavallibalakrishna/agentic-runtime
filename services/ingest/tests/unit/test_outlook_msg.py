"""A generated Outlook message: headers, body, a file, and a nested message.

Label: unit
"""

# The OLE layout is easier to read when a stream name stays on one line.
# ruff: noqa: E501

from __future__ import annotations

import itertools
import struct

import pytest

from ar_ingest.outlook import parse_outlook

_FREE = 0xFFFFFFFF
_EOC = 0xFFFFFFFE
_FAT = 0xFFFFFFFD
_NONE = 0xFFFFFFFF


def test_a_message_keeps_headers_body_attachment_and_the_nested_message() -> None:
    data = _message(
        subject="Quarterly note",
        sender="Ada Lovelace",
        recipient="Grace Hopper",
        body="The attachment is the schedule.",
        attachments=[
            ("schedule.txt", b"Monday 09:00"),
            (
                "nested.msg",
                _message(
                    subject="Inner note",
                    sender="Ada Lovelace",
                    recipient="Grace Hopper",
                    body="Nested body",
                ),
            ),
        ],
    )
    parsed = parse_outlook(data)
    headers = parsed["headers"]
    assert isinstance(headers, dict)
    assert headers["subject"] == "Quarterly note"
    assert headers["from"] == "Ada Lovelace"
    assert headers["to"] == "Grace Hopper"
    assert "The attachment is the schedule." in str(parsed["text"])
    attachments = parsed["attachments"]
    assert isinstance(attachments, list)
    file_row = next(item for item in attachments if item["kind"] == "file")
    assert file_row["filename"] == "schedule.txt"
    assert file_row["data"] == b"Monday 09:00"
    assert file_row["parent"] == "Quarterly note"
    nested = next(item for item in attachments if item["kind"] == "message")
    inner = nested["message"]
    assert isinstance(inner, dict)
    assert inner["headers"]["subject"] == "Inner note"
    assert "Nested body" in str(inner["text"])
    assert inner["parent"] == "Quarterly note"


def test_too_many_attachments_is_refused() -> None:
    data = _message(
        subject="Too many",
        sender="Ada",
        recipient="Grace",
        body="body",
        attachments=[("a.txt", b"a"), ("b.txt", b"b")],
    )
    with pytest.raises(ValueError, match="attachments"):
        parse_outlook(data, max_attachments=1)


def _message(
    *,
    subject: str,
    sender: str,
    recipient: str,
    body: str,
    attachments: list[tuple[str, bytes]] | None = None,
) -> bytes:
    """A small OLE .msg. File attachments are bytes. A nested message is more .msg bytes."""
    streams: list[tuple[list[str], bytes]] = [
        (["__properties_version1.0"], b"\x00" * 32),
        (["__nameid_version1.0", "__substg1.0_00020102"], b""),
        (["__nameid_version1.0", "__substg1.0_00030102"], b""),
        (["__nameid_version1.0", "__substg1.0_00040102"], b""),
        (["__substg1.0_001A001F"], _utf("IPM.Note")),
        (
            ["__substg1.0_007D001F"],
            _utf(f"From: {sender}\r\nTo: {recipient}\r\nSubject: {subject}\r\n"),
        ),
        (["__substg1.0_0037001F"], _utf(subject)),
        (["__substg1.0_0C1A001F"], _utf(sender)),
        (["__substg1.0_0E04001F"], _utf(recipient)),
        (["__substg1.0_1000001F"], _utf(body)),
    ]
    for index, (name, payload) in enumerate(attachments or []):
        folder = f"__attach_version1.0_#{index:08d}"
        if name.endswith(".msg"):
            streams.append(([folder, "__properties_version1.0"], b"\x00" * 8))
            streams.append(
                ([folder, "__substg1.0_3701000D", "__properties_version1.0"], b"\x00" * 32)
            )
            streams.append(
                (
                    [folder, "__substg1.0_3701000D", "__substg1.0_0037001F"],
                    _stream(payload, "__substg1.0_0037001F"),
                )
            )
            streams.append(
                (
                    [folder, "__substg1.0_3701000D", "__substg1.0_1000001F"],
                    _stream(payload, "__substg1.0_1000001F"),
                )
            )
            streams.append(
                (
                    [folder, "__substg1.0_3701000D", "__substg1.0_0C1A001F"],
                    _stream(payload, "__substg1.0_0C1A001F"),
                )
            )
            streams.append(
                (
                    [folder, "__substg1.0_3701000D", "__substg1.0_0E04001F"],
                    _stream(payload, "__substg1.0_0E04001F"),
                )
            )
            streams.append(
                (
                    [folder, "__substg1.0_3701000D", "__substg1.0_001A001F"],
                    _stream(payload, "__substg1.0_001A001F"),
                )
            )
        else:
            streams.append(([folder, "__substg1.0_37010102"], payload))
            streams.append(([folder, "__substg1.0_3707001F"], _utf(name)))
    return _ole(streams)


def _stream(blob: bytes, name: str) -> bytes:
    ole = _Ole(blob)
    return ole.stream(name)


def _utf(text: str) -> bytes:
    return text.encode("utf-16-le")


def _ole(streams: list[tuple[list[str], bytes]]) -> bytes:
    return _Ole.from_streams(streams).blob


class _Ole:
    """Enough of a compound file for extract-msg to read the streams we write."""

    def __init__(self, blob: bytes) -> None:
        self.blob = blob

    def stream(self, name: str) -> bytes:
        import olefile

        ole = olefile.OleFileIO(self.blob)
        try:
            for path in ole.listdir():
                if path[-1] == name:
                    return ole.openstream(path).read()
        finally:
            ole.close()
        return b""

    @classmethod
    def from_streams(cls, streams: list[tuple[list[str], bytes]]) -> _Ole:
        nodes = _nodes(streams)
        mini_data = bytearray()
        mini_fat: list[int] = []
        for node in nodes:
            if node["data"] is None:
                node["start"] = _EOC
                node["size"] = 0
                continue
            payload = node["data"]
            assert isinstance(payload, bytes)
            if not payload:
                node["start"] = _EOC
                node["size"] = 0
                continue
            start = len(mini_fat)
            padded = payload + b"\x00" * ((64 - len(payload) % 64) % 64)
            if not padded:
                padded = b"\x00" * 64
            count = len(padded) // 64
            mini_fat.extend(start + offset + 1 for offset in range(count - 1))
            mini_fat.append(_EOC)
            node["start"] = start
            node["size"] = len(payload)
            mini_data.extend(padded)
        while len(mini_fat) % 8:
            mini_fat.append(_FREE)
        directory = _directory(nodes)
        # Sectors: 0 mini-stream, 1 mini-fat, 2.. directory, last fat
        mini_sectors = max(1, (len(mini_data) + 511) // 512)
        mini_fat_sectors = max(1, (len(mini_fat) * 4 + 511) // 512)
        directory_sectors = max(1, (len(directory) + 511) // 512)
        fat_sectors = 1
        total = mini_sectors + mini_fat_sectors + directory_sectors + fat_sectors
        fat = [_FREE] * 128
        cursor = 0
        mini_start = cursor
        for _index in range(mini_sectors - 1):
            fat[cursor] = cursor + 1
            cursor += 1
        fat[cursor] = _EOC
        cursor += 1
        mini_fat_start = cursor
        for _ in range(mini_fat_sectors):
            fat[cursor] = _FAT
            cursor += 1
        directory_start = cursor
        for _index in range(directory_sectors - 1):
            fat[cursor] = cursor + 1
            cursor += 1
        fat[cursor] = _EOC
        cursor += 1
        fat_start = cursor
        fat[cursor] = _FAT
        header = bytearray(512)
        header[0:8] = bytes.fromhex("D0CF11E0A1B11AE1")
        struct.pack_into("<HHHHHH", header, 24, 0x003E, 3, 0xFFFE, 9, 6, 0)
        struct.pack_into(
            "<LLLLLLLLLL",
            header,
            36,
            0,
            0,
            fat_sectors,
            directory_start,
            0,
            4096,
            mini_fat_start,
            mini_fat_sectors,
            _EOC,
            0,
        )
        for index in range(109):
            struct.pack_into("<I", header, 76 + index * 4, _FREE)
        struct.pack_into("<I", header, 76, fat_start)
        body = bytearray()
        body.extend(mini_data.ljust(mini_sectors * 512, b"\x00"))
        mini_fat_bytes = b"".join(struct.pack("<I", item) for item in mini_fat).ljust(
            mini_fat_sectors * 512, b"\xff"
        )
        body.extend(mini_fat_bytes)
        body.extend(directory.ljust(directory_sectors * 512, b"\x00"))
        body.extend(b"".join(struct.pack("<I", item) for item in fat))
        # Root entry start and size point at the mini stream.
        directory_offset = mini_sectors * 512 + mini_fat_sectors * 512
        struct.pack_into("<I", body, directory_offset + 116, mini_start)
        struct.pack_into("<I", body, directory_offset + 120, len(mini_data))
        del total
        return cls(bytes(header) + bytes(body))


def _nodes(streams: list[tuple[list[str], bytes]]) -> list[dict[str, object]]:
    return _link(streams)


def _link(streams: list[tuple[list[str], bytes]]) -> list[dict[str, object]]:
    nodes: list[dict[str, object]] = [
        {
            "name": "Root Entry",
            "data": b"",
            "storage": True,
            "child": _NONE,
            "left": _NONE,
            "right": _NONE,
        }
    ]
    index_of: dict[tuple[str, ...], int] = {(): 0}

    def ensure(path: tuple[str, ...], data: bytes | None) -> int:
        if path in index_of:
            return index_of[path]
        index_of[path] = len(nodes)
        nodes.append(
            {
                "name": path[-1],
                "data": data,
                "storage": data is None,
                "child": _NONE,
                "left": _NONE,
                "right": _NONE,
            }
        )
        return index_of[path]

    children: dict[tuple[str, ...], list[tuple[str, ...]]] = {(): []}
    for path, payload in streams:
        for depth in range(1, len(path)):
            key = tuple(path[:depth])
            parent = tuple(path[: depth - 1])
            ensure(key, None)
            children.setdefault(parent, [])
            if key not in children[parent]:
                children[parent].append(key)
            children.setdefault(key, [])
        full = tuple(path)
        ensure(full, payload)
        parent = tuple(path[:-1])
        children.setdefault(parent, [])
        if full not in children[parent]:
            children[parent].append(full)
    for parent, kids in children.items():
        if not kids:
            continue
        nodes[index_of[parent]]["child"] = index_of[kids[0]]
        for left, right in itertools.pairwise(kids):
            nodes[index_of[left]]["right"] = index_of[right]
    return nodes


def _directory(nodes: list[dict[str, object]]) -> bytes:
    blob = bytearray()
    for node in nodes:
        name = str(node["name"]).encode("utf-16-le")
        entry = bytearray(128)
        entry[0 : len(name)] = name[:64]
        struct.pack_into("<H", entry, 64, min(len(name) + 2, 64))
        entry[66] = 1 if node["storage"] or node["name"] == "Root Entry" else 2
        if node["name"] == "Root Entry":
            entry[66] = 5
        struct.pack_into("<I", entry, 68, int(node["left"]))
        struct.pack_into("<I", entry, 72, int(node["right"]))
        struct.pack_into("<I", entry, 76, int(node["child"]))
        struct.pack_into("<I", entry, 116, int(node.get("start") or 0))
        struct.pack_into("<I", entry, 120, int(node.get("size") or 0))
        blob.extend(entry)
    return bytes(blob)
