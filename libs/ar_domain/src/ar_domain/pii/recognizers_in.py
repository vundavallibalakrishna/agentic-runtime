"""Indian identifiers. Spec: docs/06-security/data-protection.md §5."""

import re

_D = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    (1, 2, 3, 4, 0, 6, 7, 8, 9, 5),
    (2, 3, 4, 0, 1, 7, 8, 9, 5, 6),
    (3, 4, 0, 1, 2, 8, 9, 5, 6, 7),
    (4, 0, 1, 2, 3, 9, 5, 6, 7, 8),
    (5, 9, 8, 7, 6, 0, 4, 3, 2, 1),
    (6, 5, 9, 8, 7, 1, 0, 4, 3, 2),
    (7, 6, 5, 9, 8, 2, 1, 0, 4, 3),
    (8, 7, 6, 5, 9, 3, 2, 1, 0, 4),
    (9, 8, 7, 6, 5, 4, 3, 2, 1, 0),
)
_P = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    (1, 5, 7, 6, 2, 8, 3, 0, 9, 4),
    (5, 8, 0, 3, 7, 9, 6, 1, 4, 2),
    (8, 9, 1, 6, 0, 4, 3, 5, 2, 7),
    (9, 4, 5, 3, 1, 2, 6, 8, 7, 0),
    (4, 2, 8, 6, 5, 7, 3, 9, 0, 1),
    (2, 7, 9, 3, 8, 0, 6, 4, 1, 5),
    (7, 0, 4, 6, 9, 1, 3, 2, 5, 8),
)
_PAN = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")
_MOBILE = re.compile(r"(?:\+91[\-\s]?)?[6-9]\d{9}")
_UPI = re.compile(r"\b[\w.\-]{2,256}@[a-zA-Z]{2,64}\b")
_IFSC = re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b")
_AADHAAR = re.compile(r"\b[2-9]\d{11}\b|\b[2-9]\d{3}\s\d{4}\s\d{4}\b")


def verhoeff_ok(number: str) -> bool:
    """True when the digits pass the Verhoeff checksum."""
    checksum = 0
    for index, char in enumerate(reversed(number)):
        checksum = _D[checksum][_P[index % 8][int(char)]]
    return checksum == 0


def find_indian(text: str) -> list[dict[str, object]]:
    """Return spans for the Indian recognisers. Invalid Aadhaar checksums are ignored."""
    found: list[dict[str, object]] = []
    for match in _AADHAAR.finditer(text):
        digits = re.sub(r"\D", "", match.group())
        if len(digits) == 12 and not digits.startswith(("0", "1")) and verhoeff_ok(digits):
            found.append(_hit("aadhaar", match.start(), match.end(), match.group()))
    for pattern, name in ((_PAN, "pan"), (_MOBILE, "mobile"), (_UPI, "upi"), (_IFSC, "ifsc")):
        found.extend(
            _hit(name, match.start(), match.end(), match.group())
            for match in pattern.finditer(text)
        )
    return found


def _hit(kind: str, start: int, end: int, value: str) -> dict[str, object]:
    return {"entity": kind, "start": start, "end": end, "text": value}
