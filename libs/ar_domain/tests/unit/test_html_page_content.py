"""A web page is read for what it says, not for the site around it."""

from ar_domain.documents.extract import extract_bytes


def _text(html: str) -> str:
    extracted = extract_bytes(html.encode(), filename="page.html", media_type="text/html")
    return " ".join(passage.text for passage in extracted.passages)


_ARTICLE = (
    "Operational resilience is the ability to keep delivering important services through "
    "disruption. Firms define impact tolerances, map dependencies and test severe but "
    "plausible scenarios, then use what they learn to change how services are run."
)

_PAGE = f"""<!doctype html><html><head><title>Resilience</title></head><body>
<header><a href="/">Logo</a>
  <ul><li><a href="/">Home</a></li><li><a href="/about">About</a></li></ul></header>
<div class="cookie-banner" role="dialog"><p>Manage cookie consent</p></div>
<main>
  <ul class="sidebar"><li><a href="/a">Recent post one</a> October 2, 2026</li>
      <li><a href="/b">Another recent post title</a></li></ul>
  <select><option>2026</option><option>2025</option></select>
  <article>
    <header><h1>What resilience is</h1></header>
    <p>{_ARTICLE}</p>
    <ul><li>Map the services customers rely on, with <a href="/guide">our guide</a>.</li></ul>
    <p><a href="/share">Share</a></p>
  </article>
</main>
<footer>
  <ul><li><a href="/privacy">Privacy policy</a></li><li><a href="https://x.example">LinkedIn</a></li></ul>
  <ul><li>Get in touch: <a href="mailto:sales@example.com">sales@example.com</a></li></ul>
</footer>
</body></html>"""


def test_the_menu_banner_and_sidebar_are_left_out_and_the_content_kept() -> None:
    text = _text(_PAGE)

    assert "impact tolerances" in text
    assert "What resilience is" in text  # the article's own header is its title
    assert "Map the services customers rely on" in text  # a list item with a link in it
    for furniture in (
        "Home",
        "About",
        "cookie",
        "Recent post",
        "Another recent",
        "2025",
        "Privacy",
        "LinkedIn",
    ):
        assert furniture not in text, furniture


def test_the_footer_keeps_the_contact_details() -> None:
    assert "sales@example.com" in _text(_PAGE)


def test_a_page_without_marked_content_keeps_its_text_and_still_drops_the_menu() -> None:
    page = (
        "<html><body><nav><ul><li><a href='/'>Home</a></li></ul></nav>"
        f"<h2>Hours</h2><p>{_ARTICLE}</p><aside><p>Related reading</p></aside></body></html>"
    )

    text = _text(page)

    assert "impact tolerances" in text
    assert "Home" not in text
    assert "Related reading" not in text


def test_content_marked_but_nearly_empty_does_not_hide_the_page() -> None:
    page = (
        "<html><body><main><p>Hi</p></main>"
        f"<div><h2>Hours</h2><p>{_ARTICLE}</p></div></body></html>"
    )

    assert "impact tolerances" in _text(page)


def test_hidden_parts_are_left_out() -> None:
    page = (
        f"<html><body><main><p>{_ARTICLE}</p><p hidden>Draft wording</p>"
        "<div aria-hidden='true'><p>Decorative</p></div></main></body></html>"
    )

    text = _text(page)

    assert "Draft wording" not in text
    assert "Decorative" not in text
