"""Identity provider routes live next to domains and are re-exported."""

from ar_api.routers.domains import idp_router as router

__all__ = ["router"]
