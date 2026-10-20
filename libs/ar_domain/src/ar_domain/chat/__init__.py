"""In-process chat store used by the API until a tenant session is configured."""

from ar_domain.chat.service import ChatService

__all__ = ["ChatService"]
