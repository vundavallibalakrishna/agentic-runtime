"""Create one tenant and its first admin: the database rows and the sign-in account.

    uv run python scripts/seed_tenant.py --slug acme --name "Acme" \\
        --admin-email ada@acme.example --admin-name "Ada Lovelace"

It creates the plans and system roles, the tenant, one tenant admin, and the two agents
every tenant has (the assistant and the builder), owned by that admin. It creates no model
provider and no example data. Unless ``--skip-idp`` is given it also creates the
tenant's organization and the admin's account in the identity provider named by
``AR_OIDC_ISSUER``, so the admin can sign in with a password.

The admin's password is read from standard input, or asked for on a terminal. The identity
provider's own admin sign-in is read from ``KC_BOOTSTRAP_ADMIN_USERNAME`` and
``KC_BOOTSTRAP_ADMIN_PASSWORD``, the variables the provider itself uses.
"""

import argparse
import asyncio
import getpass
import os
import sys

import httpx

from ar_common.settings import BaseServiceSettings
from ar_domain.bootstrap import bootstrap
from ar_domain.identity.keycloak_admin import (
    IdpError,
    KeycloakAdmin,
    admin_token,
    split_issuer,
)


class _SignIn(BaseServiceSettings):
    """The issuer the API signs people in with (``AR_OIDC_ISSUER``)."""

    oidc_issuer: str


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create one tenant and its first admin.")
    parser.add_argument("--slug", required=True, help="tenant slug, for example acme")
    parser.add_argument("--name", required=True, help="tenant display name")
    parser.add_argument("--admin-email", required=True, help="email address of the first admin")
    parser.add_argument("--admin-name", required=True, help="full name of the first admin")
    parser.add_argument(
        "--skip-idp",
        action="store_true",
        help="create no sign-in account: the person already exists in your identity provider",
    )
    return parser.parse_args()


def _password() -> str:
    if sys.stdin.isatty():
        first = getpass.getpass("Password for the admin: ")
        if first != getpass.getpass("Repeat the password: "):
            raise SystemExit("The two passwords differ.")
        return first
    return sys.stdin.readline().rstrip("\n")


async def _sign_in_account(args: argparse.Namespace, password: str) -> None:
    username = os.environ.get("KC_BOOTSTRAP_ADMIN_USERNAME", "")
    secret = os.environ.get("KC_BOOTSTRAP_ADMIN_PASSWORD", "")
    if not username or not secret:
        raise SystemExit(
            "Set KC_BOOTSTRAP_ADMIN_USERNAME and KC_BOOTSTRAP_ADMIN_PASSWORD, or pass --skip-idp."
        )
    base_url, realm = split_issuer(_SignIn().oidc_issuer)
    admin = KeycloakAdmin(base_url, realm, await admin_token(base_url, username, secret))
    email = args.admin_email.strip().lower()
    first_name, _, last_name = args.admin_name.strip().partition(" ")
    organization = await admin.ensure_organization(args.name, args.slug, email.split("@", 1)[1])
    user = await admin.ensure_user(email, first_name, last_name or first_name)
    await admin.add_member(organization, user)
    await admin.set_password(user, password)


async def _run(args: argparse.Namespace) -> None:
    password = "" if args.skip_idp else _password()
    if not args.skip_idp and not password:
        raise SystemExit("The admin needs a password. Pipe it in or type it when asked.")
    slug = await bootstrap(
        slug=args.slug,
        name=args.name,
        admin_email=args.admin_email,
        admin_name=args.admin_name,
    )
    if not args.skip_idp:
        try:
            await _sign_in_account(args, password)
        except httpx.HTTPError as exc:
            raise SystemExit(
                f"The tenant is in the database, but the identity provider did not answer "
                f"({type(exc).__name__}). Start it and run this command again."
            ) from exc
        except IdpError as exc:
            raise SystemExit(f"The tenant is in the database, but the {exc}.") from exc
    print(f"Tenant {slug} is ready. Admin: {args.admin_email.strip().lower()}")


def main() -> None:
    """Console entry."""
    asyncio.run(_run(_arguments()))


if __name__ == "__main__":
    main()
