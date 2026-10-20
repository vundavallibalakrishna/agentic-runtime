"""Compose smoke. Full chat flow arrives with the public API (OQ-22)."""

import argparse
import sys
import urllib.request

DEFAULT_URLS = [
    "http://localhost:8000/healthz",
    "http://localhost:8001/healthz",
    "http://localhost:8002/healthz",
    "http://localhost:8003/healthz",
    "http://localhost:8004/healthz",
    "http://localhost:8010/healthz",
    "http://localhost:8011/healthz",
    "http://localhost:8012/healthz",
    "http://localhost:8013/healthz",
    "http://localhost:8014/healthz",
    "http://localhost:8080/healthz",
    "http://localhost:8099/healthz",
    "http://localhost:3000/healthz",
]


def _get(url: str) -> tuple[bool, str]:
    with urllib.request.urlopen(url, timeout=5) as response:  # noqa: S310
        body = response.read().decode()
        return response.status == 200 and "ok" in body, body


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--health-only", action="store_true")
    parser.add_argument("--url", action="append", dest="urls")
    args = parser.parse_args()
    urls = args.urls or DEFAULT_URLS
    if not args.health_only:
        print("conversation smoke is not available until M2; use --health-only", file=sys.stderr)
        raise SystemExit(2)
    failed = False
    for url in urls:
        try:
            if not url.startswith(("http://", "https://")):
                ok = False
                body = "refusing non-http url"
            else:
                ok, body = _get(url)
        except OSError as exc:
            ok = False
            body = str(exc)
        print(f"{'ok' if ok else 'FAIL'} {url} {body}")
        failed = failed or not ok
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
