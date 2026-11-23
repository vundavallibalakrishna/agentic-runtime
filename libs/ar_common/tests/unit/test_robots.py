"""A site's robots.txt, read the way RFC 9309 says."""

from ar_common import robots

AGENT = "agentic-runtime/1.0 (+https://example.org/contact)"


def test_a_rule_for_one_folder_leaves_the_rest_of_the_site_open() -> None:
    rules = robots.Robots("User-agent: *\nDisallow: /private\n", AGENT)
    assert rules.allows("https://example.org/news/1")
    assert not rules.allows("https://example.org/private/1")


def test_a_group_for_this_product_wins_over_the_group_for_everyone() -> None:
    text = "User-agent: *\nDisallow: /\n\nUser-agent: agentic-runtime\nAllow: /\n"
    assert robots.Robots(text, AGENT).allows("https://example.org/a")
    assert not robots.Robots(text, "another-reader/2").allows("https://example.org/a")


def test_the_pause_and_the_sitemaps_a_site_names_are_read() -> None:
    text = "User-agent: *\nCrawl-delay: 5\nSitemap: https://example.org/sitemap.xml\n"
    rules = robots.Robots(text, AGENT)
    assert rules.delay_s() == 5.0
    assert rules.sitemaps() == ["https://example.org/sitemap.xml"]
    assert robots.Robots("", AGENT).delay_s() is None


def test_a_missing_file_allows_and_an_unreadable_one_does_not() -> None:
    assert robots.Robots(robots.text_for(404, "<html>none</html>"), AGENT).allows("https://e.org/")
    assert not robots.Robots(robots.text_for(500, ""), AGENT).allows("https://e.org/")
    assert not robots.Robots(robots.text_for(None, ""), AGENT).allows("https://e.org/")
    assert robots.text_for(200, "User-agent: *\n") == "User-agent: *\n"


def test_the_file_lives_at_the_root_of_the_host_and_port() -> None:
    assert robots.address("http://127.0.0.1:8080/a/b?c=1") == "http://127.0.0.1:8080/robots.txt"
