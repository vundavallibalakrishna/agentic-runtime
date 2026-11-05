# M37 checklist

Proof date: 2026-11-05. No model call. No third-party site. Labels say what actually ran.

The browser tools are the M6 `browser.*` server. The page engine in unit tests is in-process HTML with a per-run cookie jar (`engine: fixture`). Chromium is not installed for the unit job and is not added to `images/sandbox/Dockerfile` (OQ-37, OQ-87). CI does not build that image.

## Fixture (ran in unit tests)

- [x] `browser.navigate` opens a local page and `browser.snapshot` returns an accessibility tree with `[ref=eN]`
- [x] `browser.click` follows a same-host link. The next page shows no cookie until this session has one
- [x] `browser.type` fills `note` and `browser.submit_form` POSTs it. The response includes the typed text and sets `desk=armed`
- [x] A later navigation in the same run sends that cookie. A second run, a second conversation, and a second tenant do not
- [x] `browser.press` and `browser.scroll` return the page. Scroll offset moves
- [x] `browser.screenshot` stores a PNG artifact and emits `browser.screenshot`. The bitmap is the existing chart PNG, not a Chromium capture (`engine: fixture`)
- [x] The public sandbox view omits the page, the cookie jar and `browser_sessions`
- [x] `https://off-list.example/desk` is W2 and waits for approval. Nothing is fetched before approval. After approval the mock page loads
- [x] `http://169.254.169.254/` is `egress_denied` even when the call is marked cleared
- [x] A direct `browser.navigate` to an off-list host, without the pipeline clearance, does not fetch
- [x] Chromium canary returns `live` only when a headless binary dumps the fixture. Otherwise `not_live`. A `google-chrome` on PATH that does not finish `--dump-dom` stays `not_live` and is not treated as a rendered page

Command:

```bash
uv run pytest libs/ar_domain/tests/unit/test_m37_browser.py -q
```

## Not live

- [ ] Headless Chromium or Playwright rendering the fixture (no browser binary on the unit image)
- [ ] `images/sandbox/Dockerfile` with Chromium installed. CI does not build that Dockerfile. Adding Chromium means a new apt package and a published digest; the API path does not need it
- [ ] Chat with a real model that chooses `browser.navigate` on a site with no connector
- [ ] A signed-in browser click-through of the Computers page
- [ ] Egress through the Squid proxy inside a sandbox container

Follow-up: install `chromium` on a host that already runs the API, set nothing else, and re-run the unit file. `chromium_canary` reports `live` when `--headless=new --dump-dom` prints the fixture. Publishing Chromium in the sandbox image is a separate image build, not this unit job.
