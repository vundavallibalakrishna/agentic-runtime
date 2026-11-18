"""One-slide PPTX that carries a chart PNG plus a short narrative.

The deck is written by the presentation writer in ``documents.create``, so a
chart slide and a created presentation share one package layout.
"""

from __future__ import annotations

from ar_domain.documents.create.pptx import package, picture_slide
from ar_domain.documents.create.spec import theme_for
from ar_domain.documents.create.xmlpack import PRODUCER

_IMAGE = "chart.png"
_MAX_LINES = 12


def render_slide(*, title: str, narrative: str, png: bytes) -> bytes:
    """Return a one-slide deck. The chart image is ``ppt/media/chart.png``."""
    lines = [line.strip() for line in narrative.splitlines() if line.strip()]
    if not lines:
        lines = ["Chart."]
    theme = theme_for("report")
    slide = picture_slide(title=title, lines=lines[:_MAX_LINES], image=_IMAGE, png=png, theme=theme)
    return package(
        title=title,
        subtitle="",
        author=PRODUCER,
        theme=theme,
        slides=[slide],
        media={_IMAGE: png},
    )
