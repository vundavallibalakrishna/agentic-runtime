"""In-process fake-llm application."""

from typing import TYPE_CHECKING

import pytest

from ar_fake_llm.app import create_application

if TYPE_CHECKING:
    from fastapi import FastAPI


@pytest.fixture
def fake_llm_app() -> FastAPI:
    """Return a fake-llm ASGI app with the built-in script sets."""
    return create_application()
