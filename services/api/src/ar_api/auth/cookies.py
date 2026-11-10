"""Browser session cookies.

Outside dev and CI the cookies are ``Secure``. ``ar_session`` is always
``HttpOnly`` and ``SameSite=Lax``. ``ar_csrf`` is readable by the page and
``SameSite=Strict``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ar_api.auth.mode import cookies_are_secure

if TYPE_CHECKING:
    from fastapi.responses import Response

    from ar_api.main import Settings


def write_session_cookies(
    response: Response, settings: Settings, session_id: str, csrf: str
) -> None:
    """Set the two sign-in cookies."""
    secure = cookies_are_secure(settings)
    response.set_cookie(
        "ar_session",
        session_id,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        "ar_csrf",
        csrf,
        httponly=False,
        secure=secure,
        samesite="strict",
        path="/",
    )


def clear_session_cookies(response: Response, settings: Settings) -> None:
    """Drop the sign-in cookies. The flags match the ones used to set them."""
    secure = cookies_are_secure(settings)
    response.delete_cookie("ar_session", path="/", secure=secure, httponly=True, samesite="lax")
    response.delete_cookie("ar_csrf", path="/", secure=secure, httponly=False, samesite="strict")
