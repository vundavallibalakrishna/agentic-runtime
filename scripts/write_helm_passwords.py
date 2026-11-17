"""Write a throwaway Helm overlay with generated database passwords.

Dev keys and this overlay both call ``ar_common.database_roles.generated_password``.
"""

from __future__ import annotations

import sys
from pathlib import Path

from ar_common.database_roles import write_helm_passwords


def main() -> None:
    if len(sys.argv) != 2:
        message = "usage: write_helm_passwords.py PATH"
        raise SystemExit(message)
    write_helm_passwords(Path(sys.argv[1]))


if __name__ == "__main__":
    main()
