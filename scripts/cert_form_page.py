"""A page with a form, for the browser cases of ``tool_certification.py``.

The browser tools that type, upload, download and submit need a page that has those
things, on a host the tenant allows. This serves one:

    python scripts/cert_form_page.py --port 18777

Run it where the computers of the install can reach it by a public name, add that host
to the tenant's allowed list, and pass the address as ``AR_CERT_FORM_URL``. A private
address will not do: the browser tools refuse one whatever the allowed list says, so a
page on the machine the check runs on is refused (checked with the ``docker`` driver on
20 November 2026). The page holds nothing but what is typed into it, and it is not part
of the product.
"""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

PAGE = """<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>Certification form</title></head>
<body>
<h1>Certification form</h1>
<p>{notice}</p>
<form method="post" action="/submit" enctype="multipart/form-data">
  <label>Full name <input type="text" name="full_name" aria-label="Full name"></label>
  <label>Attachment <input type="file" name="attachment" aria-label="Attachment"></label>
  <button type="submit">Send the form</button>
</form>
<p><a href="/download" download="certification-note.txt">Download the note</a></p>
<h2>Sign in</h2>
<form method="post" action="/sign-in">
  <label>User name <input type="text" name="username" aria-label="User name"></label>
  <label>Password <input type="password" name="password" aria-label="Password"></label>
  <button type="submit">Sign in</button>
</form>
</body>
</html>
"""
NOTE = b"This note was downloaded from the certification form page.\n"


class Handler(BaseHTTPRequestHandler):
    """Three addresses: the page, the note to download, and where the forms post."""

    def do_GET(self) -> None:
        if self.path.startswith("/download"):
            self._send(
                NOTE,
                "text/plain; charset=utf-8",
                {"Content-Disposition": 'attachment; filename="certification-note.txt"'},
            )
            return
        self._page("Nothing has been sent yet.")

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length)
        if self.path.startswith("/sign-in"):
            fields = parse_qs(body.decode("utf-8", errors="replace"))
            name = (fields.get("username") or [""])[0]
            given = bool((fields.get("password") or [""])[0])
            # Any user name with any password signs in. The password is never shown.
            said = f"Signed in as {name}." if name and given else "User name and password needed."
            self._page(said)
            return
        self._page(f"The form was received: {len(body)} bytes.")

    def _page(self, notice: str) -> None:
        self._send(PAGE.format(notice=_text(notice)).encode(), "text/html; charset=utf-8", {})

    def _send(self, body: bytes, kind: str, headers: dict[str, str]) -> None:
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        for name, value in headers.items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        """Say nothing: what was typed into the page does not belong in a log."""


def _text(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=18777)
    parser.add_argument("--host", default="0.0.0.0")  # noqa: S104 — a container must reach it
    options = parser.parse_args()
    ThreadingHTTPServer((options.host, options.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
