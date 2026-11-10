"""Replace personal data with tokens, found by Presidio and the recognisers beside it.

What is replaced is a setting (OQ-97). A match has a kind and a score: how sure the
recogniser is. A card number that passes its checksum scores 1.0. A nine-digit number
that could be a passport scores 0.05 until a word such as "passport" stands near it.
Masking every match whatever its score turned ordinary results into wrong ones: a sum
became ``[US_DRIVER_LICENSE]`` and the region East became ``[NRP]``. So a kind is masked
only when the tenant lists it and the match is at least as sure as the tenant asks.
"""

import importlib.util
import os
import re
import threading
from dataclasses import dataclass
from typing import Any, Protocol, cast

from ar_domain.pii.recognizers_in import find_indian

# Masked unless the tenant says otherwise: kinds whose format identifies them, and kinds
# that are only matched with supporting words once the score is applied. Not in it:
# names, places, dates and groups, which are guessed from the sentence and are what most
# text is about; web and machine addresses; and a health-service number, which is ten
# digits with one check digit, so one ordinary ten-digit number in eleven passes for it.
DEFAULT_ENTITIES: tuple[str, ...] = (
    "aadhaar",
    "credit_card",
    "crypto",
    "email_address",
    "iban_code",
    "ifsc",
    "medical_license",
    "mobile",
    "pan",
    "phone_number",
    "upi",
    "us_bank_number",
    "us_driver_license",
    "us_itin",
    "us_passport",
    "us_ssn",
)
DEFAULT_MIN_SCORE = 0.6
# What a weak match scores once a word nearby says what it is: just over the default bar.
_NAMED_SCORE = 0.65
_OWN_ENTITIES = ("aadhaar", "ifsc", "mobile", "pan", "upi")
# A person who asks for a document to be redacted wants everything that might be
# personal gone, so that request takes weaker matches than a tool result does.
_THOROUGH_MIN_SCORE = 0.35


@dataclass(frozen=True, slots=True)
class Masking:
    """Which kinds of personal data are replaced, and how sure a match must be."""

    entities: frozenset[str] = frozenset(DEFAULT_ENTITIES)
    min_score: float = DEFAULT_MIN_SCORE

    @classmethod
    def thorough(cls) -> Masking:
        """Every kind the recognisers know, at a low bar: for an explicit redaction."""
        return cls(entities=frozenset(maskable_entities()), min_score=_THOROUGH_MIN_SCORE)

    def without(self, names: frozenset[str]) -> Masking:
        return Masking(entities=self.entities - names, min_score=self.min_score)


def maskable_entities() -> list[str]:
    """Every kind a tenant can choose to mask, in lower case."""
    return sorted(entity_sources())


def entity_sources() -> dict[str, str]:
    """Each maskable kind and how it is found.

    ``format`` is a pattern, often with a checksum or supporting words. ``language`` is
    a guess from the sentence by the language model: names, places, dates, groups. A
    guessed kind is offered only when the installed model can produce it.
    """
    engine = cast("Any", _cached_engine())
    sources = dict.fromkeys(_OWN_ENTITIES, "format")
    labels = set(engine.nlp_engine.nlp["en"].pipe_labels.get("ner", []))
    mapping = engine.nlp_engine.ner_model_configuration.model_to_presidio_entity_mapping
    guessable = {str(kind).lower() for label, kind in mapping.items() if label in labels}
    for recogniser in engine.registry.get_recognizers(language="en", all_fields=True):
        guessed = recogniser.name == "SpacyRecognizer"
        for name in recogniser.supported_entities:
            kind = str(name).lower()
            if not guessed:
                sources[kind] = "format"
            elif kind in guessable:
                sources.setdefault(kind, "language")
    return sources


# Dates, places and licence-shaped tokens are evidence in a policy or a DPA.
# Presidio labels "90 days" as DATE_TIME, "Ireland" as LOCATION and "P6" inside
# a control id as US_DRIVER_LICENSE. Analysis keeps those spans.
_EVIDENCE = frozenset(
    {
        "date_time",
        "location",
        "nrp",
        "person",
        "url",
        "us_driver_license",
    }
)


class _Span(Protocol):
    entity_type: str
    start: int
    end: int
    score: float


class _Engine(Protocol):
    def analyze(
        self, text: str, language: str, entities: list[str] | None = None
    ) -> list[_Span]: ...

    def get_supported_entities(self, language: str) -> list[str]: ...


_engine_cache: list[object] = []
_engine_lock = threading.Lock()

# A sandbox path is not a licence. Presidio's US driver-licence pattern matches
# hex groups inside a UUID (``01a1ab39-[US_DRIVER_LICENSE]-…``), and the model
# then cannot reuse the path. The whole path, and any UUID in it, stays.
_UUID = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
_WORKSPACE_PATH = re.compile(
    r"(?:[A-Za-z]:)?(?:/[\w.+\-]+)*?/ar-sandboxes(?:/[\w.+\-]+)+|/workspace(?:/[\w.+\-]+)*"
)


def strict_outbound_masking(masking: Masking | None = None) -> Masking:
    """The mask for text that leaves the tenant.

    The tenant may add kinds and may lower the score bar. It may not drop a
    default kind or raise the bar above the product default: both would let
    personal data out.
    """
    chosen = masking or Masking()
    return Masking(
        entities=chosen.entities | frozenset(DEFAULT_ENTITIES),
        min_score=min(float(chosen.min_score), DEFAULT_MIN_SCORE),
    )


def mask_outbound(text: str, *, masking: Masking | None = None) -> str:
    """Replace personal data in text that is about to leave the tenant."""
    if not text:
        return text
    return redact(text, enabled=True, profile="outbound", masking=strict_outbound_masking(masking))


def redact(
    text: str,
    *,
    enabled: bool = True,
    profile: str = "outbound",
    masking: Masking | None = None,
) -> str:
    """Replace personal data with ``[KIND]`` tokens.

    ``masking`` says which kinds and how sure a match must be; without one the product
    default applies. ``analysis`` also leaves dates, places, names and control-id shaped
    tokens in place so a compliance check can read them, whatever the tenant lists.
    Matches that overlap become one token, named after the surest of them. Run-workspace
    paths and UUID segments inside them are left as written (OQ-66). Disabled callers
    receive the original text.
    """
    if not enabled or not text:
        return text
    chosen = masking or Masking()
    if profile == "analysis":
        chosen = chosen.without(_EVIDENCE)
    if not chosen.entities:
        return text
    protected = _protected_ranges(text)
    spans = [
        span
        for span in (*find_indian(text), *_presidio(text, chosen.entities))
        if str(span["entity"]).lower() in chosen.entities
        and _score(span) >= chosen.min_score
        and _closed_span(text, span)
        and not _overlaps_protected(span, protected)
    ]
    updated = text
    for start, end, kind in reversed(_merged(spans)):
        updated = f"{updated[:start]}[{kind.upper()}]{updated[end:]}"
    return updated


def _score(span: dict[str, object]) -> float:
    value = span.get("score")
    return float(value) if isinstance(value, (int, float)) else 0.0


def _merged(spans: list[dict[str, object]]) -> list[tuple[int, int, str]]:
    """Overlapping matches as one range each, in order, named after the surest match."""
    ordered = sorted(spans, key=lambda item: (int(str(item["start"])), -int(str(item["end"]))))
    merged: list[tuple[int, int, str, float]] = []
    for span in ordered:
        start, end = int(str(span["start"])), int(str(span["end"]))
        kind, score = str(span["entity"]), _score(span)
        if merged and start < merged[-1][1]:
            begun, ended, best, best_score = merged[-1]
            if score > best_score:
                best, best_score = kind, score
            merged[-1] = (begun, max(ended, end), best, best_score)
        else:
            merged.append((start, end, kind, score))
    return [(start, end, kind) for start, end, kind, _score_ in merged]


def _protected_ranges(text: str) -> list[tuple[int, int]]:
    """Character ranges that redaction must leave alone."""
    ranges = [(match.start(), match.end()) for match in _UUID.finditer(text)]
    ranges.extend((match.start(), match.end()) for match in _WORKSPACE_PATH.finditer(text))
    return ranges


def _overlaps_protected(span: dict[str, object], ranges: list[tuple[int, int]]) -> bool:
    start = int(str(span["start"]))
    end = int(str(span["end"]))
    return any(start < stop and end > begin for begin, stop in ranges)


def _closed_span(text: str, span: dict[str, object]) -> bool:
    """Keep a hit that ends on a token boundary.

    Presidio's URL pattern treats ``pn`` as a TLD, so ``revenue-by-month.png``
    is reported as ``revenue-by-month.pn`` and the final letter is left behind.
    """
    if str(span.get("entity")) != "url":
        return True
    end = int(str(span["end"]))
    return end >= len(text) or not text[end].isalnum()


def _presidio(text: str, entities: frozenset[str]) -> list[dict[str, object]]:
    """Matches for the kinds asked for. Recognisers for other kinds do not run."""
    engine = cast("_Engine", _cached_engine())
    known = {name.lower(): name for name in engine.get_supported_entities("en")}
    wanted = sorted(known[name] for name in entities if name in known)
    if not wanted:
        return []
    return [
        {
            "entity": result.entity_type.lower(),
            "start": result.start,
            "end": result.end,
            "score": result.score,
        }
        for result in engine.analyze(text=text, language="en", entities=wanted)
    ]


# The language model shipped with the product. It is small, which is enough for the
# words around a number. A deployment that masks names and places installs a larger
# model and names it in ``AR_PII_LANGUAGE_MODEL``.
_LANGUAGE_MODEL = "en_core_web_sm"


def _cached_engine() -> object:
    """Build the recogniser engine once, with the language model the product ships.

    The model is a dependency of this package, so nothing is fetched when the product
    runs. Presidio would otherwise download its default model at first use.
    """
    if _engine_cache:
        return _engine_cache[0]
    with _engine_lock:
        if not _engine_cache:
            _engine_cache.append(_build_engine())
    return _engine_cache[0]


def warm_up() -> None:
    """Build the engine now, on a thread of its own.

    It takes a few seconds, mostly loading the language model. A process that runs tool
    calls does this when it starts, so the first tool result is not the one that waits.
    """
    if not _engine_cache:
        threading.Thread(target=_cached_engine, name="pii-engine", daemon=True).start()


def _build_engine() -> object:
    from presidio_analyzer import AnalyzerEngine  # noqa: PLC0415
    from presidio_analyzer.context_aware_enhancers import (  # noqa: PLC0415
        LemmaContextAwareEnhancer,
    )
    from presidio_analyzer.nlp_engine import NlpEngineProvider  # noqa: PLC0415

    provider = NlpEngineProvider(
        nlp_configuration={
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "en", "model_name": _language_model()}],
        }
    )
    # A weak pattern (a run of digits that could be a passport number) scores far below
    # the bar on its own. With a supporting word nearby it is lifted just above the
    # default bar, so "needs supporting words" is one rule for every such kind.
    named = LemmaContextAwareEnhancer(
        context_similarity_factor=0.45, min_score_with_context_similarity=_NAMED_SCORE
    )
    return AnalyzerEngine(
        nlp_engine=provider.create_engine(),
        supported_languages=["en"],
        context_aware_enhancer=named,
    )


def _language_model() -> str:
    """The installed model to use. A name that is not installed is an error, not a download."""
    name = os.environ.get("AR_PII_LANGUAGE_MODEL", "").strip() or _LANGUAGE_MODEL
    if importlib.util.find_spec(name) is None:
        raise RuntimeError(
            f"The language model {name} named in AR_PII_LANGUAGE_MODEL is not installed."
        )
    return name
