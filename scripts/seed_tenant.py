"""Create one tenant and its first admin: the database rows and the sign-in password.

    uv run python scripts/seed_tenant.py --slug acme --name "Acme" \\
        --admin-email ada@acme.example --admin-name "Ada Lovelace"

It creates the plans and system roles, the tenant, one tenant admin (with the password you
give), and the two agents every tenant has (the assistant and the builder), owned by that
admin. It creates no model provider and no example data: the admin adds those in the product.

Sign-in is in-app, so the admin signs in with their email and this password. The password is
read from standard input, or asked for on a terminal, and is stored only as an argon2id hash.
"""

import argparse
import asyncio
import getpass
import sys

from ar_domain.bootstrap import bootstrap


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create one tenant and its first admin.")
    parser.add_argument("--slug", required=True, help="tenant slug, for example acme")
    parser.add_argument("--name", required=True, help="tenant display name")
    parser.add_argument("--admin-email", required=True, help="email address of the first admin")
    parser.add_argument("--admin-name", required=True, help="full name of the first admin")
    return parser.parse_args()


def _password() -> str:
    if sys.stdin.isatty():
        first = getpass.getpass("Password for the admin: ")
        if first != getpass.getpass("Repeat the password: "):
            raise SystemExit("The two passwords differ.")
        return first
    return sys.stdin.readline().rstrip("\n")


async def _run(args: argparse.Namespace) -> None:
    password = _password()
    if not password:
        raise SystemExit("The admin needs a password. Pipe it in or type it when asked.")
    slug = await bootstrap(
        slug=args.slug,
        name=args.name,
        admin_email=args.admin_email,
        admin_name=args.admin_name,
        admin_password=password,
    )
    print(f"Tenant {slug} is ready. Admin: {args.admin_email.strip().lower()}")


def main() -> None:
    """Console entry."""
    asyncio.run(_run(_arguments()))


if __name__ == "__main__":
    main()
