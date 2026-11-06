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


# A bare ten-digit number or a ``name@word`` token is not personal data by itself: an
# order number and ``git@github`` look the same. They count when the words around them
# say what they are, as the other recognisers do (OQ-97).
_SURE = 1.0
_FIXED_FORMAT = 0.85
_WEAK = 0.4
_WITH_CONTEXT = 0.75
_CONTEXT_CHARS = 48
_CONTEXT = {
    "aadhaar": ("aadhaar", "aadhar", "uidai", "uid"),
    "mobile": ("mobile", "phone", "cell", "whatsapp", "contact", "call", "tel"),
    "upi": ("upi", "vpa", "pay"),
}


def find_indian(text: str) -> list[dict[str, object]]:
    """Return spans for the Indian recognisers, each with how sure the match is.

    An Aadhaar number must pass its checksum, and one in ten twelve-digit numbers does,
    so it is a sure match only when it is written in groups of four or a word nearby
    names it. PAN and IFSC have a fixed format. A mobile number and a UPI id are weak
    matches unless a word nearby says what they are.
    """
    found: list[dict[str, object]] = []
    for match in _AADHAAR.finditer(text):
        digits = re.sub(r"\D", "", match.group())
        if len(digits) == 12 and not digits.startswith(("0", "1")) and verhoeff_ok(digits):
            grouped = " " in match.group()
            sure = grouped or _named(text, match, "aadhaar")
            found.append(_hit("aadhaar", match, _SURE if sure else _WEAK))
    for pattern, name in ((_PAN, "pan"), (_IFSC, "ifsc")):
        found.extend(_hit(name, match, _FIXED_FORMAT) for match in pattern.finditer(text))
    for pattern, name in ((_MOBILE, "mobile"), (_UPI, "upi")):
        for match in pattern.finditer(text):
            sure = _named(text, match, name)
            found.append(_hit(name, match, _WITH_CONTEXT if sure else _WEAK))
    return found


def _named(text: str, match: re.Match[str], kind: str) -> bool:
    """True when a word just before the match says what kind of value it is."""
    near = text[max(0, match.start() - _CONTEXT_CHARS) : match.start()].lower()
    return any(word in near for word in _CONTEXT[kind])


def _hit(kind: str, match: re.Match[str], score: float) -> dict[str, object]:
    return {
        "entity": kind,
        "start": match.start(),
        "end": match.end(),
        "text": match.group(),
        "score": score,
    }
