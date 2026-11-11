"""OpenAI-compatible URL joining.

A provider base already includes its version prefix, for example
``https://host/v1`` or ``https://api.deepinfra.com/v1/openai``. The chat route
is ``/chat/completions`` on that base. Appending ``/v1/chat/completions`` again
is a different URL and 404s.
"""

from __future__ import annotations


def chat_completions_url(base_url: str) -> str:
    """The chat-completions URL for an OpenAI-compatible base."""
    base = base_url.rstrip("/")
    suffix = "/chat/completions"
    if base.endswith(suffix):
        return base
    return base + suffix
