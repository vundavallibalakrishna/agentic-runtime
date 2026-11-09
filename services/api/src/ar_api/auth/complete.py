"""Sign-in errors. Spec: docs/03-specs/01-api-bff.md §3."""


class LoginError(Exception):
    """A sign-in failure. The login endpoint turns its ``code`` into an error response."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code
