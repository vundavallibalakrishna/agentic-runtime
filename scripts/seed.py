"""Apply the identity seed. Migrations must already be at head."""

import asyncio

from ar_domain.seed import apply


def main() -> None:
    asyncio.run(apply())


if __name__ == "__main__":
    main()
