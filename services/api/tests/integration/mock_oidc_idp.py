"""Local mock OIDC provider for the Stage 3 contract test.

The process generates its signing key when it starts. The client secret comes
from the environment for that run. Nothing here is a credential to commit.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_PRIVATE = _KEY.private_bytes(
    serialization.Encoding.PEM,
    serialization.PrivateFormat.PKCS8,
    serialization.NoEncryption(),
)
_PUBLIC = jwt.algorithms.RSAAlgorithm.to_jwk(_KEY.public_key(), as_dict=True)
_PUBLIC["kid"] = "mock"
_PUBLIC["alg"] = "RS256"
_PUBLIC["use"] = "sig"
_CODES: dict[str, dict[str, str]] = {}
_CLIENT_ID = os.environ.get("OIDC_CLIENT_ID", "ar-api")
_CLIENT_SECRET = os.environ["OIDC_CLIENT_SECRET"]
_EMAIL = os.environ.get("OIDC_EMAIL", "admin@dev.local")


def _issuer(host: str) -> str:
    return f"http://{host}"


def _token(host: str, nonce: str, *, audience: str, mfa: bool) -> str:
    claims: dict[str, object] = {
        "iss": _issuer(host),
        "aud": audience,
        "sub": _EMAIL,
        "email": _EMAIL,
        "exp": int(time.time()) + 300,
    }
    if nonce:
        claims["nonce"] = nonce
    if mfa:
        claims["amr"] = ["mfa"]
    return jwt.encode(claims, _PRIVATE, algorithm="RS256", headers={"kid": "mock"})


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        host = self.headers.get("Host", "127.0.0.1")
        if parsed.path == "/.well-known/openid-configuration":
            issuer = _issuer(host)
            self._json(
                {
                    "issuer": issuer,
                    "authorization_endpoint": f"{issuer}/authorize",
                    "token_endpoint": f"{issuer}/token",
                    "jwks_uri": f"{issuer}/jwks",
                }
            )
            return
        if parsed.path in {"/jwks", "/.well-known/jwks.json"}:
            self._json({"keys": [_PUBLIC]})
            return
        if parsed.path == "/authorize":
            query = parse_qs(parsed.query)
            code = secrets.token_urlsafe(18)
            _CODES[code] = {
                "nonce": (query.get("nonce") or [""])[0],
                "challenge": (query.get("code_challenge") or [""])[0],
                "redirect": (query.get("redirect_uri") or [""])[0],
            }
            target = _CODES[code]["redirect"]
            state = (query.get("state") or [""])[0]
            location = f"{target}?{urlencode({'code': code, 'state': state})}"
            self.send_response(302)
            self.send_header("Location", location)
            self.end_headers()
            return
        if parsed.path == "/access-token":
            mfa = (parse_qs(parsed.query).get("mfa") or ["1"])[0] != "0"
            self._json({"access_token": _token(host, "", audience="ar-api", mfa=mfa)})
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        form = parse_qs(self.rfile.read(length).decode())
        host = self.headers.get("Host", "127.0.0.1")
        if (form.get("client_secret") or [""])[0] != _CLIENT_SECRET:
            self.send_response(401)
            self.end_headers()
            return
        code = (form.get("code") or [""])[0]
        saved = _CODES.pop(code, None)
        verifier = (form.get("code_verifier") or [""])[0]
        digest = hashlib.sha256(verifier.encode()).digest()
        challenge = base64.urlsafe_b64encode(digest).decode().rstrip("=")
        if saved is None or (saved["challenge"] and challenge != saved["challenge"]):
            self.send_response(400)
            self.end_headers()
            return
        self._json(
            {
                "id_token": _token(host, saved["nonce"], audience=_CLIENT_ID, mfa=True),
                "access_token": _token(host, "", audience="ar-api", mfa=True),
                "token_type": "Bearer",
            }
        )

    def _json(self, payload: dict[str, object]) -> None:
        raw = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, fmt: str, *args: object) -> None:
        del fmt, args


def main() -> None:
    server = ThreadingHTTPServer(("0.0.0.0", 8080), Handler)  # noqa: S104
    server.serve_forever()


if __name__ == "__main__":
    main()
