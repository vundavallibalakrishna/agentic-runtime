"""Compose smoke. Full chat flow arrives with the public API (OQ-22)."""

import argparse
import sys
import time
import urllib.request

from ar_common.host_ports import health_urls

# Cold images need a moment after `compose up -d` before the process binds.
_WAIT_S = 90
_INTERVAL_S = 1.0


def _get(url: str) -> tuple[bool, str]:
    with urllib.request.urlopen(url, timeout=5) as response:  # noqa: S310
        body = response.read().decode()
        return response.status == 200 and "ok" in body, body


def _probe(url: str) -> tuple[bool, str]:
    try:
        return _get(url)
    except OSError as exc:
        return False, str(exc)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--health-only", action="store_true")
    parser.add_argument("--url", action="append", dest="urls")
    parser.add_argument("--wait-seconds", type=float, default=_WAIT_S)
    parser.add_argument("--interval-seconds", type=float, default=_INTERVAL_S)
    args = parser.parse_args()
    urls = args.urls or health_urls()
    if not args.health_only:
        print("conversation smoke is not available until M2; use --health-only", file=sys.stderr)
        raise SystemExit(2)
    results: dict[str, tuple[bool, str]] = {}
    pending: list[str] = []
    for url in urls:
        if url.startswith(("http://", "https://")):
            pending.append(url)
        else:
            results[url] = (False, "refusing non-http url")
    deadline = time.monotonic() + max(args.wait_seconds, 0.0)
    while pending:
        still_pending: list[str] = []
        for url in pending:
            ok, body = _probe(url)
            results[url] = (ok, body)
            if not ok:
                still_pending.append(url)
        pending = still_pending
        if not pending or time.monotonic() >= deadline:
            break
        time.sleep(args.interval_seconds)
    failed = False
    for url in urls:
        ok, body = results[url]
        print(f"{'ok' if ok else 'FAIL'} {url} {body}")
        failed = failed or not ok
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
