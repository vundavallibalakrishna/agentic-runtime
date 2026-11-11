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
import os
import sys

from ar_domain.bootstrap import bootstrap


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create one tenant and its first admin.")
    parser.add_argument("--slug", required=True, help="tenant slug, for example acme")
    parser.add_argument("--name", required=True, help="tenant display name")
    parser.add_argument("--admin-email", required=True, help="email address of the first admin")
    parser.add_argument("--admin-name", required=True, help="full name of the first admin")
    parser.add_argument(
        "--second-email",
        default=os.environ.get("AR_SECOND_EMAIL", ""),
        help="optional second person (AR_SECOND_EMAIL). Live certification uses this.",
    )
    parser.add_argument(
        "--second-name",
        default=os.environ.get("AR_SECOND_NAME", ""),
        help="display name of the second person",
    )
    parser.add_argument(
        "--second-role",
        default=os.environ.get("AR_SECOND_ROLE", "approver"),
        help="role key for the second person (default approver)",
    )
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
    second_password = os.environ.get("AR_SECOND_PASSWORD", "").strip() or None
    slug = await bootstrap(
        slug=args.slug,
        name=args.name,
        admin_email=args.admin_email,
        admin_name=args.admin_name,
        admin_password=password,
        second_email=args.second_email or None,
        second_name=args.second_name or None,
        second_password=second_password,
        second_role=args.second_role or None,
    )
    print(f"Tenant {slug} is ready. Admin: {args.admin_email.strip().lower()}")
    if args.second_email:
        print(f"Second user: {args.second_email.strip().lower()} ({args.second_role})")


def main() -> None:
    """Console entry."""
    asyncio.run(_run(_arguments()))


if __name__ == "__main__":
    main()
