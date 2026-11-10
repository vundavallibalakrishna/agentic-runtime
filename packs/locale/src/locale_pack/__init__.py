"""Opt-in personal-data finders. Core's default list does not include them."""

from __future__ import annotations

from ar_domain.pii.analyzer import register_recogniser
from locale_pack.recognizers_in import find_indian

ENTITIES = ("aadhaar", "ifsc", "medical_license", "mobile", "pan", "upi")


def activate() -> None:
    """Register the finders. A tenant still has to list a kind before it is masked."""
    register_recogniser(ENTITIES, find_indian)


def mount(app: object) -> None:
    """Entry point used by the pack loader. The app is not modified."""
    del app
    activate()
