"""What a tenant masks: its ``privacy`` settings as a ``Masking`` and as a list to show.

Spec: docs/06-security/data-protection.md §5. Decision: OQ-97.
"""

from __future__ import annotations

from ar_domain.pii.analyzer import (
    DEFAULT_ENTITIES,
    DEFAULT_MIN_SCORE,
    Masking,
    entity_sources,
)


def masking_from(privacy: dict[str, object]) -> Masking:
    """The masking a tenant's ``privacy`` settings ask for.

    ``redaction_entities`` lists the kinds and ``redaction_min_score`` says how sure a
    match must be. A tenant that set neither follows the product default. Kinds under
    the older ``redaction_skip_entities`` are taken out of whichever list applies.
    """
    listed = privacy.get("redaction_entities")
    names = listed if isinstance(listed, list) else DEFAULT_ENTITIES
    skipped = privacy.get("redaction_skip_entities")
    skip = {str(item).lower() for item in skipped} if isinstance(skipped, list) else set()
    score = privacy.get("redaction_min_score")
    return Masking(
        entities=frozenset(str(item).lower() for item in names) - skip,
        min_score=float(score) if isinstance(score, (int, float)) else DEFAULT_MIN_SCORE,
    )


def masking_view(settings: dict[str, object]) -> dict[str, object]:
    """Every kind the product can recognise, and what this tenant does with each."""
    privacy = settings.get("privacy")
    privacy = privacy if isinstance(privacy, dict) else {}
    features = settings.get("features")
    enabled = features.get("pii_redaction", True) if isinstance(features, dict) else True
    chosen = masking_from(privacy)
    defaults = set(DEFAULT_ENTITIES)
    return {
        "enabled": bool(enabled),
        "uses_default": not isinstance(privacy.get("redaction_entities"), list),
        "min_score": chosen.min_score,
        "default_min_score": DEFAULT_MIN_SCORE,
        "kinds": [
            {
                "name": name,
                "source": source,
                "masked": name in chosen.entities,
                "default": name in defaults,
            }
            for name, source in sorted(entity_sources().items())
        ],
    }
